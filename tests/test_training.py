"""Treino curto, com dados sintéticos, de todos os métodos e variantes."""
import json
from pathlib import Path

import pytest

from fedcxr.config import BASE_CONFIG, load_config, run_name
from fedcxr.train import run

SMALL = ["data.synthetic=true", "model.name=vit_tiny_patch16_224", "model.pretrained=false", "fl.rounds=2",
         "partition.num_clients=3", "partition.alpha=0.5", "partition.min_size=5", "eval.test_every=1",
         "train.amp=none", "train.save_model=false"]


@pytest.mark.parametrize("method,peft", [("fedavg", "full"), ("fedprox", "full"), ("scaffold", "full"),
                                         ("fedavg", "lora")])
def test_methods_run_and_count_bytes(tmp_path, method, peft):
    cfg = load_config(BASE_CONFIG, [*SMALL, f"fl.method={method}", f"model.peft={peft}",
                                            "acquisition.severity=0.5", "acquisition.harmonize=true",
                                            f"train.out_dir={tmp_path}"])
    summary = run(cfg)
    assert summary["rounds_run"] == 2 and summary["total_bytes"] > 0
    if peft == "lora":
        assert summary["params"]["trainable"] < summary["params"]["total"] / 10


@pytest.mark.parametrize("variant", ["cweighted", "uniform", "clip"])
def test_scaffold_variants_run(tmp_path, variant):
    cfg = load_config(BASE_CONFIG, [*SMALL, "fl.method=scaffold", f"fl.scaffold_variant={variant}",
                                            f"train.out_dir={tmp_path}"])
    assert run(cfg)["rounds_run"] == 2


# caminho numérico congelado: cada caso exercita um ramo de fl.py (aquisição + harmonização, correção do
# SCAFFOLD com recorte, termo proximal, LoRA) e é comparado com tests/golden/sintetico.json
GOLDEN = Path(__file__).parent / "golden" / "sintetico.json"
GOLDEN_CASES = {
    "scaffold_aquisicao": ["fl.method=scaffold", "acquisition.severity=0.5", "acquisition.harmonize=true"],
    "scaffold_clip": ["fl.method=scaffold", "fl.scaffold_variant=clip"],
    "fedprox": ["fl.method=fedprox", "fl.mu=0.1"],
    "lora": ["model.peft=lora"],
}


def numbers(case, out_dir):
    cfg = load_config(BASE_CONFIG, [*SMALL, *GOLDEN_CASES[case], f"train.out_dir={out_dir}"])
    run(cfg)
    lines = (Path(out_dir) / run_name(cfg) / "rounds.jsonl").read_text().splitlines()
    return [{"val_bacc": r["val_bacc"], "val_loss": r["val_loss"], "cum_bytes": r["cum_bytes"],
             "clients": [[c["steps"], c["loss"], c["upd_norm"]] for c in r["client_stats"]]}
            for r in map(json.loads, lines)]


@pytest.mark.parametrize("case", GOLDEN_CASES)
def test_training_reproduces_the_frozen_numbers(tmp_path, case):
    """Gerado em CPU com as versões de requirements.txt; para regravar: PYTHONPATH=. python tests/test_training.py."""
    got, want = numbers(case, tmp_path), json.loads(GOLDEN.read_text())[case]
    assert [r["cum_bytes"] for r in got] == [r["cum_bytes"] for r in want]
    assert [[c[0] for c in r["clients"]] for r in got] == [[c[0] for c in r["clients"]] for r in want]
    for g, w in zip(got, want):
        assert g["val_bacc"] == pytest.approx(w["val_bacc"], abs=1e-6)
        assert g["val_loss"] == pytest.approx(w["val_loss"], rel=1e-5)
        assert [x for c in g["clients"] for x in c[1:]] == pytest.approx([x for c in w["clients"] for x in c[1:]],
                                                                         abs=2e-4)


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        GOLDEN.write_text(json.dumps({case: numbers(case, Path(tmp, case)) for case in GOLDEN_CASES}, indent=1) + "\n")
    print("gravado", GOLDEN)
