"""Arquivos que uma execução grava em <out_dir>/<nome>/ e a leitura deles.

    config.json     config completo usado
    status.json     pid, GPU e início (o dashboard usa para acompanhar a execução ao vivo)
    partition.json  estatísticas da partição, perfis de aquisição e tamanho do conjunto
    rounds.jsonl    uma linha por rodada
    summary.json    resumo final; só existe quando a execução terminou

A leitura tolera arquivos ausentes ou a meio, porque o dashboard lê execuções em andamento.
"""
import contextlib
import json
import os
from pathlib import Path

from .config import with_defaults

CONFIG, STATUS, PARTITION, ROUNDS, SUMMARY = "config.json", "status.json", "partition.json", "rounds.jsonl", \
    "summary.json"
FINAL_STATE = "final_state.pt"


class RunWriter:
    def __init__(self, run_dir):
        self.dir = Path(run_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._rounds = None

    def write(self, filename, obj):
        """Grava por inteiro ou não grava: quem lê nunca vê um JSON pela metade (nem um summary.json truncado)."""
        tmp = self.dir / f"{filename}.tmp"
        tmp.write_text(json.dumps(obj, indent=2))
        os.replace(tmp, self.dir / filename)

    def __enter__(self):
        self._rounds = open(self.dir / ROUNDS, "w")
        return self

    def __exit__(self, *exc):
        self._rounds.close()

    def append_round(self, row):
        self._rounds.write(json.dumps(row) + "\n")
        self._rounds.flush()


def is_done(run_dir):
    return (Path(run_dir) / SUMMARY).exists()


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def read_rounds(run_dir):
    rows = []
    with contextlib.suppress(OSError):
        for line in (Path(run_dir) / ROUNDS).read_text().splitlines():
            if line.strip():
                with contextlib.suppress(ValueError):  # a última linha pode estar sendo escrita agora
                    rows.append(json.loads(line))
    return rows


def load_run(run_dir):
    """Tudo o que a execução gravou até agora; cfg vem completo com os campos novos (ver config.with_defaults)."""
    d = Path(run_dir)
    cfg = read_json(d / CONFIG)
    return {"name": d.name, "cfg": with_defaults(cfg) if cfg else None, "status": read_json(d / STATUS) or {},
            "partition": read_json(d / PARTITION) or {}, "rows": read_rounds(d), "summary": read_json(d / SUMMARY)}


def run_dirs(grid_dir):
    """Pastas de execução de uma grade (as que já gravaram config.json), em ordem de nome."""
    d = Path(grid_dir)
    return [r for r in sorted(d.iterdir()) if (r / CONFIG).exists()] if d.is_dir() else []


def load_grid(root, grid):
    """Execuções terminadas de <root>/<grid>, por nome; grade ausente devolve {}."""
    return {r.name: load_run(r) for r in run_dirs(Path(root, grid)) if is_done(r)}
