"""Dashboard de acompanhamento dos experimentos (servidor HTTP da biblioteca padrão).

    python dashboard/server.py                                   # IP do Tailscale, porta 8050, lê runs/
    python dashboard/server.py --host 127.0.0.1 --runs runs_final

API (somente leitura):
    GET /api/state                          estado de todas as grades, GPUs e proteção térmica
    GET /api/run?grid=<grade>&run=<nome>    todas as linhas do rounds.jsonl da execução (com client_stats)
    GET /api/launch-info                    grades com número de execuções, padrões da proteção térmica e de cada
                                            ambiente (local, Colab, Modal)

Interface: / (index.html), /style.css, /app/... (componentes Preact) e /vendor/... (bibliotecas, sem CDN).

Lê os logs das execuções em <runs>/<grade>/<execução>/ (formato em fedcxr/runlog.py), o estado da proteção
térmica (scripts/thermal_guard.py) e amostra o nvidia-smi a cada 2 s (histórico de 15 min em memória).
Somente leitura: não dispara nem interrompe experimentos.
"""
import argparse
import json
import re
import socket
import subprocess
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fedcxr import runlog  # noqa: E402
from fedcxr.config import het_label, method_key  # noqa: E402
from fedcxr.grids import GRIDS, PAPER_GRIDS  # noqa: E402
from scripts import launch, thermal_guard  # noqa: E402

HTML_PATH = Path(__file__).parent / "index.html"
STATIC_DIR = Path(__file__).parent
STATIC_DIRS = ("app", "vendor")  # além de /style.css, só arquivos dentro destas pastas são servidos
STATIC_TYPES = {".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8"}
RUNNING_WINDOW = 180  # segundos sem atualização até considerar a execução parada
ROW_KEYS = ("round", "val_bacc", "val_loss", "val_f1", "val_auc", "train_loss", "train_acc", "cos_mean",
            "cum_bytes", "round_bytes", "sec", "imgs_per_sec", "test_bacc")

GPU_FIELDS = ["index", "name", "pci.bus_id", "utilization.gpu", "memory.used", "memory.total", "temperature.gpu",
              "power.draw", "power.limit", "clocks.sm", "clocks.max.sm", "fan.speed",
              "clocks_event_reasons.sw_thermal_slowdown", "clocks_event_reasons.hw_thermal_slowdown",
              "clocks_event_reasons.sw_power_cap", "clocks_event_reasons.hw_slowdown",
              "clocks_event_reasons.gpu_idle"]
GPU_NOW = {"gpus": [], "procs": []}
GPU_HIST = deque(maxlen=450)
LOCK = threading.Lock()


def _num(x):
    try:
        return float(x)
    except ValueError:
        return None


def sample_gpus():
    try:
        out = subprocess.run(["nvidia-smi", f"--query-gpu={','.join(GPU_FIELDS)}", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5).stdout
        apps = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,gpu_bus_id,used_memory",
                               "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return
    gpus = []
    for line in out.strip().splitlines():
        v = [x.strip() for x in line.split(",")]
        if len(v) != len(GPU_FIELDS):
            continue
        thermal = v[12] == "Active" or v[13] == "Active"
        gpus.append({
            "index": int(v[0]), "name": v[1], "bus": v[2].upper(), "util": _num(v[3]), "mem_used": _num(v[4]),
            "mem_total": _num(v[5]), "temp": _num(v[6]), "power": _num(v[7]), "power_limit": _num(v[8]),
            "clock": _num(v[9]), "clock_max": _num(v[10]), "fan": _num(v[11]),
            "limit": "hw_thermal" if v[13] == "Active" else "thermal" if thermal else
                     "power" if v[14] == "Active" else "hw" if v[15] == "Active" else
                     "idle" if v[16] == "Active" else "none"})
    procs = []
    for line in apps.strip().splitlines():
        v = [x.strip() for x in line.split(",")]
        if len(v) == 3 and v[0].isdigit():
            procs.append({"pid": int(v[0]), "bus": v[1].upper(), "mem": _num(v[2])})
    with LOCK:
        GPU_NOW["gpus"], GPU_NOW["procs"] = gpus, procs
        GPU_HIST.append({"t": time.time(), "g": [[g["temp"], g["util"], g["power"], g["clock"]] for g in gpus]})


def sampler():
    while True:
        sample_gpus()
        time.sleep(2)


def read_run(d):
    run = runlog.load_run(d)
    cfg, rows, summary, part, status = run["cfg"], run["rows"], run["summary"], run["partition"], run["status"]
    mtime = max(p.stat().st_mtime for p in d.iterdir())
    paused = not summary and thermal_guard.proc_state(status.get("pid")) == "T"
    state = "done" if summary else "paused" if paused else \
        "running" if time.time() - mtime < RUNNING_WINDOW else "stalled"
    clients = [{"id": c["client"], "n": c["n"], "counts": c["counts"], "kl": c["kl"]}
               for c in part.get("label_stats", {}).get("clients", [])]
    return {
        "name": d.name, "group": re.sub(r"_s\d+$", "", d.name), "status": state,
        "method": method_key(cfg), "het": het_label(cfg), "seed": cfg["seed"],
        "lr": cfg["fl"]["lr"], "max_rounds": cfg["fl"]["rounds"], "pid": status.get("pid"),
        "gpu_bus": (status.get("gpu") or {}).get("pci_bus_id"), "gpu_name": (status.get("gpu") or {}).get("name"),
        "started": status.get("started"), "n_train": status.get("n_train"),
        "kl_mean": part.get("label_stats", {}).get("kl_mean"), "clients": clients,
        "dataset": part.get("dataset") or {},
        "rows": [{k: r.get(k) for k in ROW_KEYS} for r in rows],
        "client_stats": rows[-1].get("client_stats") if rows else None,
        "summary": None if not summary else {
            "test_bacc": summary["test"]["bacc"], "test_auc": summary["test"]["auc_macro"],
            "test_f1": summary["test"]["f1_macro"], "f1_per_class": summary["test"].get("f1_per_class"),
            "total_bytes": summary["total_bytes"], "wall_sec": summary["wall_sec"],
            "trainable": summary["params"]["trainable"], "total_params": summary["params"]["total"]},
        "updated": mtime,
    }


def state(runs_dir):
    grids = []
    for g in sorted(runs_dir.iterdir()) if runs_dir.exists() else []:
        if not g.is_dir():
            continue
        runs = []
        for d in runlog.run_dirs(g):
            try:
                runs.append(read_run(d))
            except Exception as e:  # uma execução corrompida não derruba o painel
                runs.append({"name": d.name, "status": "error", "error": str(e), "rows": []})
        expected = len(GRIDS[g.name]()) if g.name in GRIDS else None
        grids.append({"grid": g.name, "expected": expected, "runs": runs})
    with LOCK:
        gpus = json.loads(json.dumps(GPU_NOW))
        hist = list(GPU_HIST)
    return {"time": time.time(), "gpus": gpus["gpus"], "procs": gpus["procs"], "gpu_hist": hist, "grids": grids,
            "guard": thermal_guard.read_state(), "host": socket.gethostname(), "stalled_after": RUNNING_WINDOW}


def run_rows(runs_dir, grid, run):
    """Todas as linhas do rounds.jsonl de uma execução (modo replay); None se a grade ou a execução não existe.

    Só aceita nomes simples de diretórios que já existem em runs_dir, sem caminhos.
    """
    if not all(name and "/" not in name and "\\" not in name and ".." not in name for name in (grid, run)):
        return None
    d = Path(runs_dir) / grid / run
    if d not in runlog.run_dirs(Path(runs_dir) / grid):
        return None
    return {"grid": grid, "name": run, "rows": runlog.read_rounds(d)}


def static_file(path):
    """Arquivo da interface (/style.css, /app/..., /vendor/...) e seu Content-Type; None se não for um deles.

    Recusa ".." e qualquer caminho que, resolvido, saia de dashboard/app ou dashboard/vendor.
    """
    parts = unquote(path).lstrip("/").split("/")
    if any(p in ("", ".", "..") or "\\" in p for p in parts):
        return None
    if parts != ["style.css"] and (len(parts) < 2 or parts[0] not in STATIC_DIRS):
        return None
    f = STATIC_DIR.joinpath(*parts).resolve()
    roots = [STATIC_DIR.resolve() / d for d in STATIC_DIRS]
    inside = f == (STATIC_DIR / "style.css").resolve() or any(f.is_relative_to(r) for r in roots)
    ctype = STATIC_TYPES.get(f.suffix)
    return (f, ctype) if inside and ctype and f.is_file() else None


def launch_info():
    """O que o painel precisa para montar comandos de execução (não executa nada)."""
    guard = vars(thermal_guard.parser().parse_args([]))
    return {"grids": [{"name": n, "runs": len(f())} for n, f in GRIDS.items()],
            "paper": {"grids": PAPER_GRIDS, "runs": sum(len(GRIDS[n]()) for n in PAPER_GRIDS)},
            "guard_defaults": {"hot": guard["hot"], "cool": guard["cool"]},
            "modal": {"volume": launch.MODAL_VOLUME, "default_k": launch.MODAL_DEFAULT_K},
            "local": {"default_k": launch.LOCAL_DEFAULT_K},
            "colab": {"url": launch.COLAB_NOTEBOOK_URL, "default_k": launch.COLAB_DEFAULT_K,
                      "max_runs": launch.COLAB_MAX_RUNS}}


class Handler(BaseHTTPRequestHandler):
    runs_dir = ROOT / "runs"

    def _send(self, body, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == "/api/state":
            self._send(json.dumps(state(self.runs_dir)).encode(), "application/json")
        elif url.path == "/api/launch-info":
            self._send(json.dumps(launch_info()).encode(), "application/json")
        elif url.path == "/api/run":
            q = parse_qs(url.query)
            body = run_rows(self.runs_dir, q.get("grid", [""])[0], q.get("run", [""])[0])
            if body is None:
                self.send_error(404)
            else:
                self._send(json.dumps(body).encode(), "application/json")
        elif url.path in ("/", "/index.html"):
            self._send(HTML_PATH.read_bytes(), "text/html; charset=utf-8")
        elif found := static_file(url.path):
            self._send(found[0].read_bytes(), found[1])
        else:
            self.send_error(404)

    def log_message(self, *args):
        pass


def tailscale_ip():
    try:
        out = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=5).stdout
        return out.split()[0]
    except (OSError, IndexError, subprocess.TimeoutExpired):
        return "127.0.0.1"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=None, help="padrão: IP do Tailscale (não expõe na rede local)")
    ap.add_argument("--port", type=int, default=8050)
    ap.add_argument("--runs", default="runs", help="pasta com as grades (ex.: runs_final)")
    args = ap.parse_args()
    Handler.runs_dir = ROOT / args.runs  # relativo à raiz do repositório; um caminho absoluto fica como está
    threading.Thread(target=sampler, daemon=True).start()
    host = args.host or tailscale_ip()
    print(f"dashboard em http://{host}:{args.port}", flush=True)
    ThreadingHTTPServer((host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
