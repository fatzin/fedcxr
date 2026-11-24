"""Roda as grades no Modal, várias execuções por GPU ao mesmo tempo.

    modal run modal_run.py::prepare                       # baixa o Kermany (Mendeley) e prepara no Volume
    modal run modal_run.py::calibrate                     # mede o throughput com 1, 4 e 8 execuções juntas
    modal run modal_run.py::grid --name sens --k 3        # grade curta, com o terminal aberto
    # grades longas: deploy + spawn, para não depender da máquina local ligada
    modal deploy modal_run.py
    python modal_run.py paper 8                           # dispara no app implantado e retorna na hora
    modal volume get fedcxr-vol runs/h2 runs_final/

Grades (fedcxr/grids.py): python scripts/run_grid.py --list ("paper" = todas as do artigo, 199 execuções).

Os resultados ficam no Volume fedcxr-vol (runs/<grade>/<execução>/). Execuções com summary.json
são puladas, então dá para interromper e retomar.
"""
import modal

from scripts.launch import MODAL_DEFAULT_K, MODAL_VOLUME

GPU = "RTX-PRO-6000"
VOL = "/vol"
DATA = f"{VOL}/data/prepared/kermany.pt"
CONFIG = "/root/configs/base.yaml"

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("torch==2.9.1", "torchvision==0.24.1", index_url="https://download.pytorch.org/whl/cu128")
    .pip_install("timm==1.0.31", "numpy==2.5.5", "scikit-learn==1.9.1", "scikit-image==0.26.0", "PyYAML==6.0.4",
                 "matplotlib==3.11.2", "pillow==13.0.0")
    .env({"HF_HOME": f"{VOL}/hf", "OMP_NUM_THREADS": "2"})
    .add_local_python_source("fedcxr", "scripts")
    .add_local_dir("configs", "/root/configs")
)
vol = modal.Volume.from_name(MODAL_VOLUME, create_if_missing=True)
app = modal.App("fedcxr", image=image, volumes={VOL: vol})


@app.function(cpu=8, memory=16384, timeout=3 * 3600)
def prepare():
    import os

    import timm

    from fedcxr.config import load_config
    from fedcxr.data import download_kermany, prepare_kermany, summarize
    # baixa os pesos do ViT uma vez para o Volume (HF_HOME), para os processos em paralelo não disputarem o download
    timm.create_model(load_config(CONFIG)["model"]["name"], pretrained=True)
    vol.commit()
    if os.path.exists(DATA):
        print("já preparado:", DATA)
        return
    download_kermany("/tmp/raw")
    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    data = prepare_kermany("/tmp/raw", DATA, val_frac=0.1, workers=8)
    print(summarize(data))
    vol.commit()


def _run_jobs(jobs, out_dir, k):
    """Roda jobs (listas de overrides) com k processos simultâneos na mesma GPU. Devolve o tempo total."""
    from scripts.run_grid import pending, run_jobs

    todo = pending(jobs, out_dir, CONFIG, [f"data.path={DATA}"])
    print(f"{len(todo)} jobs pendentes em {out_dir}, {k} por vez", flush=True)
    # os pesos já estão no Volume; offline evita que vários processos consultem o HF Hub ao mesmo tempo
    secs = run_jobs(todo, CONFIG, [(f"modal {i}", {"HF_HUB_OFFLINE": "1"}) for i in range(k)],
                    after_each=vol.commit)  # run_jobs nunca chama em paralelo: a doc do Modal pede commits em série
    vol.commit()
    return secs


@app.function(gpu=GPU, cpu=12, memory=49152, timeout=24 * 3600)
def run_grid(name, k):
    from fedcxr.grids import grid as make_grid
    return _run_jobs(make_grid(name), f"{VOL}/runs/{name}", k)


@app.function(gpu=GPU, cpu=12, memory=49152, timeout=2 * 3600)
def calibrate_k(k, rounds):
    from fedcxr.grids import job

    # FedAvg completo com α = 0,1, o caso mais comum da h2; seeds diferentes só para não pular jobs
    jobs = [job("fedavg", "full", 0.1, 100 + i, f"fl.rounds={rounds}", "train.save_model=false") for i in range(k)]
    secs = _run_jobs(jobs, f"{VOL}/runs/calib_k{k}", k)
    return {"k": k, "rounds": rounds, "min": secs / 60}


@app.local_entrypoint()
def calibrate(rounds: int = 20):
    rows = [calibrate_k.remote(k, rounds) for k in (1, 4, 8)]
    print("\nk  rounds  minutos  execuções-de-100-rounds/h")
    for r in rows:
        per_hour = r["k"] * (r["rounds"] / 100) / (r["min"] / 60)
        print(f"{r['k']:<2} {r['rounds']:<7} {r['min']:<8.1f} {per_hour:.1f}")


@app.local_entrypoint()
def grid(name: str, k: int = MODAL_DEFAULT_K):
    """Roda uma grade (ou "paper", todas as do artigo em sequência) com k execuções por GPU."""
    from fedcxr.grids import grids
    for g, _ in grids(name):
        secs = run_grid.remote(g, k)
        print(f"{g}: {secs / 3600:.2f} h")


if __name__ == "__main__":
    # python modal_run.py <grade|paper> [k]: dispara as grades no app já implantado (modal deploy)
    import sys

    from fedcxr.grids import grids

    name, k = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else MODAL_DEFAULT_K
    fn = modal.Function.from_name("fedcxr", "run_grid")
    for g, _ in grids(name):
        print(g, fn.spawn(g, k).object_id)
