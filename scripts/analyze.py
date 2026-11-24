"""Resume uma grade: rodadas até o alvo (R), custo total até o alvo (C_total) e desempenho no teste.

    python scripts/analyze.py --runs runs_final --grid h2 --targets 0.80 0.85
    python scripts/analyze.py --grid h2 --rel 0.95     # alvo = 95% da melhor BACC de validação do FedAvg IID
    python scripts/analyze.py --grid h2 --targets 0.75 --out analise_h2   # grava tabela, JSON e curvas

Com --rel, a melhor BACC de validação de cada seed do FedAvg IID entra na média entre seeds.
R é calculado depois, a partir do log de todas as rodadas, para qualquer alvo.
Execuções que não atingem o alvo são marcadas como censuradas (R > rodadas executadas).
Os grupos separam método, variante (config.method_key) e heterogeneidade (config.het_label).
"""
import argparse
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fedcxr.config import het_label, method_key  # noqa: E402
from fedcxr.metrics import first_cross  # noqa: E402
from fedcxr.runlog import load_grid  # noqa: E402


def group_key(cfg):
    return method_key(cfg), het_label(cfg)


def fmt(values, scale=1.0, nd=1, censored=False):
    """média ± dp amostral (como no artigo); None = censurada (R, C_total) ou sem valor (ex.: AUC indefinida)."""
    v = [x / scale for x in values if x is not None]
    if not v:
        return "não atinge" if censored else "n.a."
    s = f"{st.mean(v):.{nd}f} ± {(st.stdev(v) if len(v) > 1 else 0.0):.{nd}f}"
    if len(v) < len(values):
        s += f" ({len(values) - len(v)} {'censur.' if censored else 'sem valor'})"
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", required=True)
    ap.add_argument("--targets", nargs="*", type=float, default=[])
    ap.add_argument("--rel", type=float, default=None)
    ap.add_argument("--runs", default="runs", help="pasta com as grades (ex.: runs_final)")
    ap.add_argument("--out", help="pasta onde gravar summary_table.md, summary.json e as curvas (padrão: só imprime)")
    args = ap.parse_args()
    runs = list(load_grid(args.runs, args.grid).values())
    if not runs:
        raise SystemExit(f"nenhuma execução completa em {Path(args.runs) / args.grid}")

    targets = list(args.targets)
    if args.rel is not None:
        ref = [max(r["val_bacc"] for r in run["rows"]) for run in runs
               if group_key(run["cfg"]) == ("fedavg-full", "IID")]
        if ref:
            targets.append(round(args.rel * float(np.mean(ref)), 4))

    groups = defaultdict(list)
    for run in runs:
        groups[group_key(run["cfg"])].append(run)

    lines = ["| Método | Heterogeneidade | KL médio | Bytes/rodada (MB) | " +
             " | ".join(f"R @ {t}" for t in targets) + " | " +
             " | ".join(f"C_total @ {t} (MB)" for t in targets) + " | BACC teste | AUC teste |",
             "|" + "---|" * (6 + 2 * len(targets))]
    records = []
    for (method, het), rs in sorted(groups.items()):
        kl = fmt([r["summary"]["kl_mean"] for r in rs], nd=3)
        per_round = fmt([r["rows"][0]["round_bytes"] for r in rs], scale=1e6)
        rt = {t: [first_cross(r["rows"], t) for r in rs] for t in targets}
        r_cells = [fmt([x[0] for x in rt[t]], nd=1, censored=True) for t in targets]
        c_cells = [fmt([x[1] for x in rt[t]], scale=1e6, censored=True) for t in targets]
        bacc = fmt([r["summary"]["test"]["bacc"] for r in rs], nd=3)
        auc = fmt([r["summary"]["test"]["auc_macro"] for r in rs], nd=3)
        lines.append(f"| {method} | {het} | {kl} | {per_round} | " + " | ".join(r_cells) + " | " +
                     " | ".join(c_cells) + f" | {bacc} | {auc} |")
        records.append({"method": method, "heterogeneity": het, "n_seeds": len(rs),
                        "rounds_to_target": {str(t): [x[0] for x in rt[t]] for t in targets},
                        "bytes_to_target": {str(t): [x[1] for x in rt[t]] for t in targets},
                        "test_bacc": [r["summary"]["test"]["bacc"] for r in rs]})

    table = "\n".join(lines)
    print(table)
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "summary_table.md").write_text(f"Alvos (acurácia balanceada de validação): {targets}\n\n{table}\n")
        (out / "summary.json").write_text(json.dumps(records, indent=2))
        plot(groups, targets, out)


def plot(groups, targets, out):
    by_method = defaultdict(list)
    for (method, het), rs in groups.items():
        by_method[method].append((het, rs))
    for xkey, xlabel, fname in [("round", "Rodada", "curvas_rodada.png"),
                                ("cum_bytes", "Bytes acumulados (GB)", "curvas_bytes.png")]:
        fig, axes = plt.subplots(1, len(by_method), figsize=(4.2 * len(by_method), 3.4), squeeze=False,
                                 sharey=True)
        for ax, (method, items) in zip(axes[0], sorted(by_method.items())):
            for het, rs in sorted(items):
                n = min(len(r["rows"]) for r in rs)
                y = np.mean([[row["val_bacc"] for row in r["rows"][:n]] for r in rs], axis=0)
                x = np.array([row[xkey] for row in rs[0]["rows"][:n]], dtype=float)
                if xkey == "cum_bytes":
                    x /= 1e9
                ax.plot(x, y, label=het)
            for t in targets:
                ax.axhline(t, color="gray", lw=0.6, ls="--")
            ax.set_title(method)
            ax.set_xlabel(xlabel)
        axes[0][0].set_ylabel("BACC validação")
        axes[0][-1].legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(out / fname, dpi=150)
        plt.close(fig)


if __name__ == "__main__":
    main()
