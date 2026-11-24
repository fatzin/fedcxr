"""Proteção térmica: pausa os treinos de uma GPU quando ela passa de --hot e retoma abaixo de --cool.

    nohup python scripts/thermal_guard.py --hot 88 --cool 75 >> thermal_guard.log 2>&1 &

Só mexe em processos `fedcxr.train` (nunca no desktop ou em outros programas).
Pausa com SIGSTOP e retoma com SIGCONT: o treino continua exatamente de onde parou.

Grava na raiz do repositório, de onde quer que seja chamada, thermal_guard.pid (pid e limites, ao iniciar) e
os eventos em thermal_guard.log. O dashboard lê os dois com read_state(), que fica aqui junto do formato.
A saída padrão só recebe erros fatais do Python (o redirecionamento acima os junta ao mesmo log).
"""
import argparse
import contextlib
import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PID_FILE = ROOT / "thermal_guard.pid"
LOG_FILE = ROOT / "thermal_guard.log"
TIME_FMT = "%Y-%m-%d %H:%M:%S"
LOG_LINE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) (.*)$")
EVENT = re.compile(r"^GPU (\d+) a (\d+) °C: treino \d+ (pausado|retomado)$")


def gpus():
    query = ["nvidia-smi", "--query-gpu=index,pci.bus_id,temperature.gpu", "--format=csv,noheader,nounits"]
    out = subprocess.run(query, capture_output=True, text=True, timeout=10).stdout
    res = []
    for line in out.strip().splitlines():
        i, bus, temp = [x.strip() for x in line.split(",")]
        res.append((int(i), bus.upper()[-12:], float(temp)))
    return res


def train_pids_by_bus():
    out = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,gpu_bus_id", "--format=csv,noheader"],
                         capture_output=True, text=True, timeout=10).stdout
    by_bus = {}
    for line in out.strip().splitlines():
        pid, bus = [x.strip() for x in line.split(",")]
        try:
            cmd = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode()
        except OSError:
            continue
        if "fedcxr.train" in cmd:
            by_bus.setdefault(bus.upper()[-12:], []).append(int(pid))
    return by_bus


def proc_state(pid):
    """Estado do processo no /proc (ex.: 'T' = pausado por SIGSTOP); None se não existe ou fora do Linux."""
    try:
        return Path(f"/proc/{pid}/stat").read_text().split(") ")[1].split()[0]
    except (OSError, IndexError):
        return None


def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(f"{time.strftime(TIME_FMT)} {msg}\n")


def read_state():
    """Processo, limites e eventos recentes, como o dashboard mostra."""
    info = {}
    with contextlib.suppress(OSError, ValueError):
        info = json.loads(PID_FILE.read_text())
    if not isinstance(info, dict):  # pid file antigo, escrito à mão só com o número
        info = {"pid": info}
    defaults = vars(parser().parse_args([]))
    pid = info.get("pid")
    alive = False
    with contextlib.suppress(OSError):
        alive = pid is not None and b"thermal_guard" in Path(f"/proc/{pid}/cmdline").read_bytes()
    events = []
    try:
        lines = LOG_FILE.read_text().splitlines()[-400:]
    except OSError:
        lines = []
    for line in lines:
        m = LOG_LINE.match(line)
        if not m:
            continue
        msg = m.group(2)
        ev = EVENT.match(msg)
        kind = {"pausado": "pause", "retomado": "resume"}[ev.group(3)] if ev else \
            "error" if msg.startswith("erro") else "info"
        events.append({"t": time.mktime(time.strptime(m.group(1), TIME_FMT)), "kind": kind, "msg": msg,
                       "gpu": int(ev.group(1)) if ev else None, "temp": float(ev.group(2)) if ev else None})
    return {"pid": pid, "alive": alive, "hot": info.get("hot", defaults["hot"]),
            "cool": info.get("cool", defaults["cool"]), "events": events}


def parser():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hot", type=float, default=88)
    ap.add_argument("--cool", type=float, default=75)
    ap.add_argument("--every", type=float, default=5)
    return ap


def main():
    args = parser().parse_args()
    PID_FILE.write_text(json.dumps({"pid": os.getpid(), "hot": args.hot, "cool": args.cool}))
    log(f"proteção ativa: pausa em {args.hot} °C, retoma em {args.cool} °C")
    while True:
        try:
            pids = train_pids_by_bus()
            for idx, bus, temp in gpus():
                for pid in pids.get(bus, []):
                    stopped = proc_state(pid) == "T"
                    if temp >= args.hot and not stopped:
                        os.kill(pid, signal.SIGSTOP)
                        log(f"GPU {idx} a {temp:.0f} °C: treino {pid} pausado")
                    elif temp <= args.cool and stopped:
                        os.kill(pid, signal.SIGCONT)
                        log(f"GPU {idx} a {temp:.0f} °C: treino {pid} retomado")
        except Exception as e:  # a proteção não pode morrer por um erro pontual
            log(f"erro: {e}")
        time.sleep(args.every)


if __name__ == "__main__":
    main()
