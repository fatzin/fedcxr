"""Roda as grades do artigo (definidas em fedcxr/grids.py) numa máquina com GPU própria (self-hosted).

    python scripts/run_grid.py --list                       # grades disponíveis e número de execuções
    python scripts/run_grid.py --grid h2 --gpus 0,1         # um job por GPU
    python scripts/run_grid.py --grid h2 --gpus 0 --per-gpu 4   # quatro jobs simultâneos na mesma GPU
    python scripts/run_grid.py --grid paper --gpus 0,1      # todas as grades do artigo
    python scripts/run_grid.py --grid paper --dry-run     # só lista o que falta rodar

Jobs com summary.json já gravado são pulados, então dá para interromper e retomar.
O executor run_jobs também é usado por modal_run.py.
"""
import argparse
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fedcxr import runlog  # noqa: E402
from fedcxr.config import BASE_CONFIG, load_config, run_name  # noqa: E402
from fedcxr.grids import GRIDS, PAPER_GRIDS, grid, grids  # noqa: E402


def pending(jobs, out_dir, config, extra=()):
    """(out_dir, nome, overrides) dos jobs que ainda não têm summary.json em out_dir."""
    todo = []
    for ov in jobs:
        ov = [*ov, *extra, f"train.out_dir={out_dir}"]
        name = run_name(load_config(config, ov))
        if not runlog.is_done(Path(out_dir) / name):
            todo.append((out_dir, name, ov))
    return todo


def run_jobs(todo, config, slots, after_each=None):
    """Roda os jobs, um subprocess `fedcxr.train` por vez em cada slot, com uma nova tentativa se falhar.

    slots: lista de (rótulo, variáveis de ambiente extras), uma thread por slot.
    after_each: chamado depois de cada job, nunca em paralelo. Devolve o tempo total em segundos.
    """
    todo = list(todo)
    lock, done_lock = threading.Lock(), threading.Lock()

    def worker(label, env):
        while True:
            with lock:
                if not todo:
                    return
                out_dir, name, ov = todo.pop(0)
            t = time.time()
            Path(out_dir, "_logs").mkdir(parents=True, exist_ok=True)
            cmd = [sys.executable, "-m", "fedcxr.train", "--config", str(config), "--set", *ov]
            with open(Path(out_dir, "_logs", f"{name}.log"), "w") as log:
                for _ in range(2):  # falhas passageiras (rede, E/S do Volume); o log guarda as duas tentativas
                    rc = subprocess.call(cmd, env={**os.environ, **env}, stdout=log, stderr=subprocess.STDOUT)
                    if rc == 0:
                        break
            print(f"[{label}] {'ok ' if rc == 0 else 'ERRO'} {name} ({(time.time() - t) / 60:.1f} min)", flush=True)
            if after_each:
                with done_lock:
                    after_each()

    t0 = time.time()
    threads = [threading.Thread(target=worker, args=slot) for slot in slots]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", help="nome da grade ou 'paper' (todas as do artigo)")
    ap.add_argument("--list", action="store_true", help="lista as grades e o número de execuções")
    ap.add_argument("--config", default=str(BASE_CONFIG))
    ap.add_argument("--runs", default="runs", help="pasta de saída (runs/<grade>/<execução>/)")
    ap.add_argument("--gpus", default="0", help="índices das GPUs, separados por vírgula")
    ap.add_argument("--per-gpu", type=int, default=1, help="execuções simultâneas por GPU (o ViT-S cabe várias)")
    ap.add_argument("--extra", nargs="*", default=[], help="overrides aplicados a todos os jobs")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.list or not args.grid:
        for n in GRIDS:
            print(f"{n:14s} {len(grid(n)):4d} execuções")
        print(f"{'paper':14s} {sum(len(grid(n)) for n in PAPER_GRIDS):4d} execuções (todas as do artigo)")
        return

    todo = [item for gname, jobs in grids(args.grid)
            for item in pending(jobs, f"{args.runs}/{gname}", args.config, args.extra)]
    print(f"{len(todo)} jobs pendentes")
    if args.dry_run:
        for out_dir, name, _ in todo:
            print(" ", out_dir, name)
        return
    # PCI_BUS_ID faz o índice bater com o nvidia-smi (o padrão do CUDA põe a GPU mais rápida primeiro)
    slots = [(f"gpu {g}", {"CUDA_DEVICE_ORDER": "PCI_BUS_ID", "CUDA_VISIBLE_DEVICES": g})
             for g in args.gpus.split(",") for _ in range(args.per_gpu)]
    run_jobs(todo, args.config, slots)


if __name__ == "__main__":
    main()
