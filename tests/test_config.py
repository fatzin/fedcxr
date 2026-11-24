"""Overrides do config, nomes das execuções, rótulos e grades do artigo."""
from pathlib import Path

import pytest

from fedcxr.config import BASE_CONFIG, load_config, method_key, run_name
from fedcxr.grids import grids
from fedcxr.runlog import load_grid

RUNS_FINAL = Path(__file__).resolve().parents[1] / "runs_final"


def test_overrides_parse_yaml_values():
    cfg = load_config(BASE_CONFIG, ["fl.lr=0.003", "acquisition.harmonize=true", "partition.alpha=0.1"])
    assert cfg["fl"]["lr"] == 0.003 and cfg["acquisition"]["harmonize"] is True and cfg["partition"]["alpha"] == 0.1


def test_unknown_key_is_rejected():
    with pytest.raises(KeyError):
        load_config(BASE_CONFIG, ["fl.lrr=0.1"])


def test_run_name_encodes_the_setting():
    cfg = load_config(BASE_CONFIG, ["fl.method=scaffold", "partition.alpha=0.1", "seed=3"])
    assert run_name(cfg) == "scaffold-full_dir0.1_sev0.0_s3"


def test_paper_grids_name_exactly_the_runs_of_the_paper():
    """Cada job das grades do artigo tem o nome de um diretório de runs_final/, e vice-versa."""
    for name, jobs in grids("paper"):
        names = [run_name(load_config(BASE_CONFIG, ov)) for ov in jobs]
        real = [d.name for d in (RUNS_FINAL / name).iterdir() if d.is_dir() and d.name != "_logs"]
        assert sorted(names) == sorted(real), name


def test_method_key_reads_old_and_new_logged_configs():
    """As primeiras execuções não gravaram fl.scaffold_variant; as variantes gravaram."""
    h2 = load_grid(RUNS_FINAL, "h2")
    assert method_key(h2["scaffold-full_dir0.1_sev0.0_s0"]["cfg"]) == "scaffold-full"
    keys = {method_key(r["cfg"]) for g in ("scaffold_var", "abl_mu", "abl_lora") for r in
            load_grid(RUNS_FINAL, g).values()}
    assert keys == {"scaffold-full-cweighted", "scaffold-full-uniform", "scaffold-full-clip", "fedprox-full-mu0.001",
                    "fedprox-full-mu0.1", "fedavg-lora-r4", "fedavg-lora-r16"}
