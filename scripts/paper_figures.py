"""Gera as tabelas (.tex) e figuras (.pdf) do artigo a partir dos logs das execuções.

    python scripts/paper_figures.py --runs runs_final --out ../artigo-experimental

Nenhum número do artigo é digitado à mão: tudo sai daqui. Lê as grades do artigo (fedcxr.grids.PAPER_GRIDS)
em --runs; as ausentes são puladas. As execuções são escolhidas pelo nome (congelado em runs_final/).
"""
import argparse
import math
import statistics as st
import sys
from pathlib import Path

import matplotlib
import numpy as np
from scipy import stats

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fedcxr.grids import PAPER_GRIDS  # noqa: E402
from fedcxr.metrics import first_cross, sustained_cross  # noqa: E402
from fedcxr.runlog import load_grid  # noqa: E402

TARGET = 0.75
TARGETS = [0.70, 0.72, 0.75, 0.78]
METHODS = [("fedavg-full", "FedAvg"), ("fedprox-full", "FedProx"), ("scaffold-full", "SCAFFOLD"),
           ("fedavg-lora", "FedAvg + LoRA")]
PARTS = [("iid", "IID"), ("dir1.0", r"$\alpha=1{,}0$"), ("dir0.5", r"$\alpha=0{,}5$"),
         ("dir0.3", r"$\alpha=0{,}3$"), ("dir0.2", r"$\alpha=0{,}2$"), ("dir0.15", r"$\alpha=0{,}15$"),
         ("dir0.1", r"$\alpha=0{,}1$")]


# ---------------------------------------------------------------- seleção e critérios
def by_seed(runs, prefix):
    """Execuções cujo nome é <prefix>_s<seed>, ordenadas pela seed."""
    sel = {}
    for name, r in runs.items():
        base, _, seed = name.rpartition("_s")
        if base == prefix and seed.isdigit():
            sel[int(seed)] = r
    return [sel[s] for s in sorted(sel)]


def rounds_to(rs, t=TARGET):
    """R (primeira travessia) de cada execução; None nas que não atingem o alvo."""
    return [first_cross(r["rows"], t)[0] for r in rs]


def mean_hits(values):
    """Média dos valores que não são None (execuções que atingem o alvo); None se nenhuma atinge."""
    ok = [x for x in values if x is not None]
    return st.mean(ok) if ok else None


def n_hits(rs, t=TARGET):
    return sum(x is not None for x in rounds_to(rs, t))


def n_sustained(rs, t=TARGET):
    return sum(sustained_cross(r["rows"], t)[0] is not None for r in rs)


def size_cv(r):
    """Coeficiente de variação dos tamanhos dos clientes."""
    n = r["summary"]["client_sizes"]
    return st.pstdev(n) / st.mean(n)


def test_last(r):
    return r["summary"]["test"]["bacc"]


def test_tail(r):
    """Média da BACC de teste nas rodadas 80, 90 e 100 (menos sensível à oscilação final)."""
    v = [row["test_bacc"] for row in r["rows"] if "test_bacc" in row and row["round"] >= 80]
    return sum(v) / len(v) if v else None


# ---------------------------------------------------------------- formatação
def num(x, nd=1):
    return f"{x:.{nd}f}".replace(".", "{,}")


def msd(v, nd=1, scale=1.0):
    """média ± dp amostral; marca censuras (execuções que não atingem o alvo)."""
    ok = [x / scale for x in v if x is not None]
    cens = len(v) - len(ok)
    if not ok:
        return "n.a."
    s = num(st.mean(ok), nd)
    if len(ok) > 1:
        s += r"\,$\pm$\," + num(st.stdev(ok), nd)
    if cens:
        s += rf"$^{{\dagger{cens}}}$"
    return s


def ci_paired(d):
    n = len(d)
    m = st.mean(d)
    h = stats.t.ppf(0.975, n - 1) * st.stdev(d) / math.sqrt(n) if n > 1 else float("nan")
    return m, m - h, m + h


def write(out, name, lines):
    path = Path(out, "tabelas", name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    print("escrito", path)


def write_macros(out, name, macros):
    """Macros LaTeX (\\newcommand) com os números citados no texto."""
    write(out, name, ["% gerado por scripts/paper_figures.py; não editar à mão"] +
          [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in sorted(macros.items())])


def save_fig(fig, out, name):
    path = Path(out, "figuras", name)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    print("escrito", path)


# ---------------------------------------------------------------- tabelas
def table_h12(h2, out):
    lines = [r"\begin{table*}[t]", r"\centering",
             r"\caption{Heterogeneidade de rótulos (H1) e estratégias de mitigação (H2). $R$: rodadas até "
             r"BACC de validação $\ge 0{,}75$; $C_{total}$: bytes até $R$. "
             r"$\mathrm{CV}_N$: coeficiente de variação dos tamanhos dos clientes. BACC de teste: modelo da "
             r"rodada 100 e média das rodadas 80, 90 e 100. Média\,$\pm$\,desvio padrão entre \textit{seeds}; "
             r"$^{\dagger k}$: $k$ execuções não atingiram o alvo em 100 rodadas e ficam fora da média. "
             r"$\alpha=0{,}2$ e $0{,}15$: só FedAvg, grade complementar. n.a.: nenhuma execução atingiu o alvo.}",
             r"\label{tab:h12}", r"\small",
             r"\resizebox{\textwidth}{!}{%", r"\begin{tabular}{llcccrrcc}", r"\toprule",
             r"Método & Partição & \textit{Seeds} & $\overline{\text{KL}}$ & $\mathrm{CV}_N$ & $R$ & "
             r"$C_{total}$ (GB) & "
             r"BACC teste (r100) & BACC teste (r80, 90, 100) \\", r"\midrule"]
    for mi, (m, mlabel) in enumerate(METHODS):
        for pi, (p, plabel) in enumerate(PARTS):
            rs = by_seed(h2, f"{m}_{p}_sev0.0")
            if not rs:
                continue
            fc = [first_cross(r["rows"], TARGET) for r in rs]
            kl = [r["summary"]["kl_mean"] for r in rs]
            lines.append(
                f"{mlabel if pi == 0 else ''} & {plabel} & {len(rs)} & {num(st.mean(kl), 2)} & "
                f"{num(st.mean(size_cv(r) for r in rs), 2)} & "
                f"{msd([x[0] for x in fc])} & {msd([x[1] for x in fc], 2 if 'lora' in m else 1, 1e9)} & "
                f"{msd([test_last(r) for r in rs], 3)} & {msd([test_tail(r) for r in rs], 3)} \\\\")
        if mi < len(METHODS) - 1:
            lines.append(r"\midrule")
    lines += [r"\bottomrule", r"\end{tabular}}", r"\end{table*}"]
    write(out, "h12.tex", lines)


def table_targets(h2, out):
    lines = [r"\begin{table}[t]", r"\centering",
             r"\caption{Robustez à escolha do alvo e do critério, com $\alpha=0{,}1$. "
             r"Primeira travessia: razão entre o "
             r"$R$ médio com $\alpha=0{,}1$ e com IID. Sustentado: $R$ médio quando se exige que a BACC de validação "
             r"fique $\ge\tau$ por três rodadas seguidas. Entre parênteses, quantas \textit{seeds} atingem o alvo; "
             r"as que não atingem ficam fora da média. n.a.: nenhuma execução atingiu o alvo.}",
             r"\label{tab:alvos}", r"\small", r"\setlength{\tabcolsep}{3pt}",
             r"\resizebox{\columnwidth}{!}{%", r"\begin{tabular}{lcccc}", r"\toprule",
             "Método & " + " & ".join(f"$\\tau={num(t, 2)}$" for t in TARGETS) + r" \\", r"\midrule"]

    for m, mlabel in METHODS:
        iid, a01 = by_seed(h2, f"{m}_iid_sev0.0"), by_seed(h2, f"{m}_dir0.1_sev0.0")
        if not iid or not a01:
            continue
        cells = []
        for t in TARGETS:
            ri, ra = mean_hits(rounds_to(iid, t)), mean_hits(rounds_to(a01, t))
            hits = f"({n_hits(a01, t)}/{len(a01)})"
            cells.append(f"n.a. {hits}" if ri is None or ra is None else f"{num(ra / ri)}$\\times$ {hits}")
        lines.append(f"{mlabel} & " + " & ".join(cells) + r" \\")
    lines += [r"\midrule", r"\multicolumn{5}{l}{\textit{Sustentado: $R$ com $\alpha=0{,}1$ (3 rodadas seguidas)}} \\"]
    for m, mlabel in METHODS:
        a01 = by_seed(h2, f"{m}_dir0.1_sev0.0")
        if not a01:
            continue
        cells = []
        for t in TARGETS:
            v = [sustained_cross(r["rows"], t)[0] for r in a01]
            ok = [x for x in v if x is not None]
            cells.append(f"{num(st.mean(ok)) if ok else 'n.a.'} ({len(ok)}/{len(v)})")
        lines.append(f"{mlabel} & " + " & ".join(cells) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}}", r"\end{table}"]
    write(out, "alvos.tex", lines)


def table_h3(h3, h3c, out):
    lines = [r"\begin{table*}[t]", r"\centering",
             r"\caption{Heterogeneidade de aquisição (H3), partição IID. Avaliação deformada: validação e teste "
             r"recebem os perfis dos clientes. Avaliação limpa: só o treino é deformado. "
             r"$\Delta R_{harm}$: diferença pareada (com harmonização menos sem) e IC95\%. n.a.: sem valor.}",
             r"\label{tab:h3}", r"\small",
             r"\begin{tabular}{llccccccc}", r"\toprule",
             r"& & \multicolumn{3}{c}{Avaliação deformada} & & \multicolumn{3}{c}{Avaliação limpa} \\",
             r"\cmidrule{3-5}\cmidrule{7-9}",
             r"Ajuste & $s$ & $R$ sem harm. & $R$ com harm. & $\Delta R_{harm}$ & & $R$ sem harm. & "
             r"$R$ com harm. & $\Delta R_{harm}$ \\", r"\midrule"]

    def block(runs, peft, sev, suffix):
        a = by_seed(runs, f"fedavg-{peft}_iid_sev{sev}{suffix}")
        b = by_seed(runs, f"fedavg-{peft}_iid_sev{sev}_harm{suffix}")
        if not a or not b:
            return ["n.a."] * 3
        ra, rb = rounds_to(a), rounds_to(b)
        d = [y - x for x, y in zip(ra, rb) if x is not None and y is not None]
        dcell = "n.a."
        if len(d) > 1:
            m, lo, hi = ci_paired(d)
            dcell = f"{num(m)} [{num(lo)}; {num(hi)}]"
        return [msd(ra), msd(rb), dcell]

    for pi, (peft, plabel) in enumerate((("full", "Completo"), ("lora", "LoRA"))):
        for si, sev in enumerate(("0.0", "0.5", "1.0")):
            dist = block(h3, peft, sev, "")
            same = ["\\multicolumn{3}{c}{= avaliação deformada}"]
            clean = block(h3c, peft, sev, "_cleaneval") if sev != "0.0" else same
            row = f"{plabel if si == 0 else ''} & {num(float(sev))} & " + " & ".join(dist) + " & & " + " & ".join(clean)
            lines.append(row + r" \\")
        if pi == 0:
            lines.append(r"\midrule")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table*}"]
    write(out, "h3.tex", lines)


def table_ablation(h2, sens, mu, lora, out):
    lines = [r"\begin{table}[t]", r"\centering",
             r"\caption{Análises adicionais com $\alpha=0{,}1$ (e IID para o posto do LoRA). Mesmas \textit{seeds} "
             r"e partições da grade principal. n.a.: nenhuma execução atingiu o alvo.}",
             r"\label{tab:ablacao}", r"\setlength{\tabcolsep}{3pt}",
             r"\resizebox{\columnwidth}{!}{%", r"\begin{tabular}{llcrrc}", r"\toprule",
             r"Variante & Partição & \textit{Seeds} & $R$ & $C_{total}$ (GB) & BACC teste \\", r"\midrule"]

    def row(label, part, rs, nd=1):
        if not rs:
            return
        fc = [first_cross(r["rows"], TARGET) for r in rs]
        lines.append(f"{label} & {part} & {len(rs)} & {msd([x[0] for x in fc])} & "
                     f"{msd([x[1] for x in fc], nd, 1e9)} & {msd([test_last(r) for r in rs], 3)} \\\\")

    row(r"FedProx $\mu=0{,}001$", r"$\alpha=0{,}1$", by_seed(mu, "fedprox-full_dir0.1_mu0.001"))
    row(r"FedProx $\mu=0{,}01$ (princ.)", r"$\alpha=0{,}1$", by_seed(h2, "fedprox-full_dir0.1_sev0.0"))
    row(r"FedProx $\mu=0{,}1$", r"$\alpha=0{,}1$", by_seed(mu, "fedprox-full_dir0.1_mu0.1"))
    lines.append(r"\midrule")
    row(r"SCAFFOLD $\eta=0{,}003$ (princ.)", r"$\alpha=0{,}1$", by_seed(h2, "scaffold-full_dir0.1_sev0.0"))
    row(r"SCAFFOLD $\eta=0{,}001$", r"$\alpha=0{,}1$", by_seed(sens, "scaffold-full_dir0.1_sev0.0_lr0.001"))
    lines.append(r"\midrule")
    for part, plabel, base in (("iid", "IID", "iid"), ("dir0.1", r"$\alpha=0{,}1$", "dir0.1")):
        for r in (4, 8, 16):
            rs = (by_seed(h2, f"fedavg-lora_{base}_sev0.0") if r == 8
                  else by_seed(lora, f"fedavg-lora-r{r}_{part}"))
            row(f"LoRA $r={r}$" + (" (princ.)" if r == 8 else ""), plabel, rs, 2)
    lines += [r"\bottomrule", r"\end{tabular}}", r"\end{table}"]
    write(out, "ablacao.tex", lines)


def table_scaffold(h2, sv, out, sn):
    """Variantes de agregação do SCAFFOLD (diagnóstico do colapso com alpha = 0,1)."""
    lines = [r"\begin{table}[t]", r"\centering",
             r"\caption{Variantes do SCAFFOLD. Princ.: implementação principal, modelo ponderado por $N_k/N$ e $c$ "
             r"pela média uniforme; unif.: ambos uniformes, como no algoritmo original; pond.: ambos por $N_k/N$; "
             r"recorte: princ. com $\|c-c_k\|\le\|g\|$. Atingem: \textit{seeds} que chegam a 0,75 (primeira "
             r"travessia); sust.: idem, por três rodadas seguidas. $R$ e $C_{total}$ só são mostrados quando ao "
             r"menos metade das \textit{seeds} atinge o alvo (n.a.).}",
             r"\label{tab:scaffold}", r"\setlength{\tabcolsep}{3pt}",
             r"\resizebox{\columnwidth}{!}{%", r"\begin{tabular}{llccrrc}", r"\toprule",
             r"Variante & Partição & Atingem & Sust. & $R$ & $C_{total}$ (GB) & BACC teste \\", r"\midrule"]

    def row(label, part, rs):
        if not rs:
            return
        fc = [first_cross(r["rows"], TARGET) for r in rs]
        ok, sus = n_hits(rs), n_sustained(rs)
        show = 2 * ok >= len(rs)
        rcell = msd([x[0] for x in fc]) if show else "n.a."
        ccell = msd([x[1] for x in fc], 1, 1e9) if show else "n.a."
        lines.append(f"{label} & {part} & {ok}/{len(rs)} & {sus}/{len(rs)} & {rcell} & {ccell} & "
                     f"{msd([test_last(r) for r in rs], 3)} \\\\")

    a01, a03 = r"$\alpha=0{,}1$", r"$\alpha=0{,}3$"
    row("FedAvg (ref.)", a01, by_seed(h2, "fedavg-full_dir0.1_sev0.0"))
    lines.append(r"\midrule")
    row("SCAFFOLD princ.", a01, by_seed(h2, "scaffold-full_dir0.1_sev0.0"))
    row("SCAFFOLD unif.", a01, by_seed(sv, "scaffold-uniform_dir0.1"))
    row("SCAFFOLD recorte", a01, by_seed(sv, "scaffold-clip_dir0.1"))
    row("SCAFFOLD pond.", a01, by_seed(sv, "scaffold-cweighted_dir0.1"))
    lines.append(r"\midrule")
    row("SCAFFOLD princ.", a03, by_seed(h2, "scaffold-full_dir0.3_sev0.0"))
    row("SCAFFOLD pond.", a03, by_seed(sv, "scaffold-cweighted_dir0.3"))
    row("SCAFFOLD princ.", "IID", by_seed(h2, "scaffold-full_iid_sev0.0"))
    row("SCAFFOLD pond.", "IID", by_seed(sv, "scaffold-cweighted_iid"))
    if sn:
        lines += [r"\midrule",
                  r"\multicolumn{7}{l}{\textit{Replicação com \textit{seeds} novas (5 a 9), $\alpha=0{,}1$}} \\"]
        row("FedAvg (ref.)", a01, by_seed(sn, "fedavg-full_dir0.1_sev0.0"))
        row("SCAFFOLD princ.", a01, by_seed(sn, "scaffold-full_dir0.1_sev0.0"))
        row("SCAFFOLD pond.", a01, by_seed(sn, "scaffold-cweighted_dir0.1"))
    lines += [r"\bottomrule", r"\end{tabular}}", r"\end{table}"]
    write(out, "scaffold.tex", lines)


def numbers_scaffold(h2, sv, sn, out):
    """Macros do diagnóstico do SCAFFOLD citadas no texto."""
    fa = by_seed(h2, "fedavg-full_dir0.1_sev0.0")
    cw = by_seed(sv, "scaffold-cweighted_dir0.1")
    m = {}
    if fa and cw and len(fa) == len(cw):
        rf, rc = rounds_to(fa), rounds_to(cw)
        if None not in rf + rc:
            d, lo, hi = ci_paired([a - b for a, b in zip(rf, rc)])
            m.update(RcwAlta=num(st.mean(rc)), DeltaRcw=num(d), DeltaRcwLo=num(lo), DeltaRcwHi=num(hi))
        cc = [first_cross(r["rows"], TARGET)[1] for r in cw]
        if None not in cc:
            m["CcwAlta"] = num(st.mean(cc) / 1e9)
        m["BACCcwAlta"] = num(st.mean(test_last(r) for r in cw), 3)
        m["SustCwAlta"] = str(n_sustained(cw))
    if sn:
        fa2, pr2, cw2 = (by_seed(sn, "fedavg-full_dir0.1_sev0.0"), by_seed(sn, "scaffold-full_dir0.1_sev0.0"),
                         by_seed(sn, "scaffold-cweighted_dir0.1"))
        m.update(NovFa=str(n_hits(fa2)), NovPr=str(n_hits(pr2)), NovCw=str(n_hits(cw2)),
                 NovCwSust=str(n_sustained(cw2)), NovFaSust=str(n_sustained(fa2)), NovPrSust=str(n_sustained(pr2)),
                 NovPrColapso=str(sum(test_last(r) < 0.34 for r in pr2)))
        # dez seeds: pares em que FedAvg e pond. atingem o alvo
        allfa = by_seed(h2, "fedavg-full_dir0.1_sev0.0") + fa2
        allcw = by_seed(sv, "scaffold-cweighted_dir0.1") + cw2
        pairs = list(zip(rounds_to(allfa), rounds_to(allcw)))
        both = [(x, y) for x, y in pairs if x is not None and y is not None]
        d, lo, hi = ci_paired([x - y for x, y in both])
        m.update(DezPares=str(len(both)), DezDelta=num(d), DezLo=num(lo), DezHi=num(hi),
                 DezMenor=str(sum(1 for x, y in pairs if y is not None and (x is None or y < x))),
                 DezRcw=num(st.mean(y for _, y in pairs if y is not None)),
                 DezRfa=num(st.mean(x for x, _ in pairs if x is not None)))
        cfa = [first_cross(r["rows"], TARGET)[1] for r in allfa]
        ccw = [first_cross(r["rows"], TARGET)[1] for r in allcw]
        m.update(DezCfa=num(st.mean(v for v in cfa if v is not None) / 1e9),
                 DezCcw=num(st.mean(v for v in ccw if v is not None) / 1e9),
                 DezFaHit=str(sum(v is not None for v in cfa)))
    write_macros(out, "numeros_scaffold.tex", m)


# ---------------------------------------------------------------- figuras
plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8,
                     "legend.fontsize": 7, "xtick.labelsize": 7, "ytick.labelsize": 7,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.formatter.use_locale": False})


PART_COLORS = {"iid": "#1f4e79", "dir1.0": "#3c7fb1", "dir0.5": "#7fa7c9", "dir0.3": "#d18a3a",
               "dir0.2": "#c97a35", "dir0.15": "#be6230", "dir0.1": "#b4432a"}


def fig_curves(h2, out):
    fig, axes = plt.subplots(1, 4, figsize=(7.16, 1.9), sharey=True)
    for ax, (m, mlabel) in zip(axes, METHODS):
        for p, plabel in PARTS:
            rs = by_seed(h2, f"{m}_{p}_sev0.0")
            if not rs:
                continue
            y = np.array([[row["val_bacc"] for row in r["rows"]] for r in rs])
            x = np.arange(1, y.shape[1] + 1)
            ax.plot(x, y.mean(0), color=PART_COLORS[p], lw=1, label=plabel)
            ax.fill_between(x, y.min(0), y.max(0), color=PART_COLORS[p], alpha=0.12, lw=0)
        ax.axhline(TARGET, color="0.4", lw=0.6, ls="--")
        ax.set_title(mlabel)
        ax.set_xlabel("Rodada")
        ax.set_ylim(0.3, 0.85)
    axes[0].set_ylabel("BACC validação")
    axes[-1].legend(loc="lower right", frameon=False)
    fig.tight_layout(pad=0.3)
    save_fig(fig, out, "curvas.pdf")


def fig_scaffold(h2, sv, out):
    series = [("FedAvg", by_seed(h2, "fedavg-full_dir0.1_sev0.0"), "#1f4e79", "-"),
              ("SCAF. princ.", by_seed(h2, "scaffold-full_dir0.1_sev0.0"), "#b4432a", "-"),
              ("SCAF. unif.", by_seed(sv, "scaffold-uniform_dir0.1"), "#b7943a", "--"),
              ("SCAF. recorte", by_seed(sv, "scaffold-clip_dir0.1"), "0.5", ":"),
              ("SCAF. pond.", by_seed(sv, "scaffold-cweighted_dir0.1"), "#4a7c6f", "-")]
    fig, ax = plt.subplots(figsize=(3.45, 2.2))
    for label, rs, c, ls in series:
        if not rs:
            continue
        y = np.array([[row["val_bacc"] for row in r["rows"]] for r in rs])
        x = np.arange(1, y.shape[1] + 1)
        ax.plot(x, y.mean(0), color=c, lw=1, ls=ls, label=label)
        if label in ("FedAvg", "SCAF. princ.", "SCAF. pond."):
            ax.fill_between(x, y.min(0), y.max(0), color=c, alpha=0.10, lw=0)
    ax.axhline(TARGET, color="0.4", lw=0.6, ls="--")
    ax.set_xlabel("Rodada")
    ax.set_ylabel("BACC validação")
    ax.set_ylim(0.3, 0.85)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), frameon=False, ncol=3, columnspacing=0.8,
              handlelength=1.5, fontsize=6)
    fig.tight_layout(pad=0.3)
    save_fig(fig, out, "scaffold.pdf")


def fig_partition(h2, out, seed=0):
    """Composição de classes por cliente (seed 0) para alpha = 0,3 e 0,1."""
    cls = [("Normal", "#7fa7c9"), ("Bacteriana", "#b4432a"), ("Viral", "#b7943a")]
    fig, axes = plt.subplots(1, 2, figsize=(3.45, 2.1), sharey=True)
    for ax, (tag, title) in zip(axes, (("dir0.3", r"$\alpha=0{,}3$"), ("dir0.1", r"$\alpha=0{,}1$"))):
        run = h2.get(f"fedavg-full_{tag}_sev0.0_s{seed}")
        if run is None:
            continue
        cl = run["partition"]["label_stats"]["clients"]
        cl = sorted(cl, key=lambda c: -c["n"])
        counts = np.array([c["counts"] for c in cl], dtype=float)
        n = counts.sum(1)
        frac = counts / n[:, None]
        x = np.arange(len(cl))
        bottom = np.zeros(len(cl))
        for j, (name, col) in enumerate(cls):
            ax.bar(x, frac[:, j], bottom=bottom, color=col, width=0.8, label=name)
            bottom += frac[:, j]
        for xi, ni in zip(x, n):
            ax.text(xi, 1.02, str(int(ni)), ha="center", va="bottom", fontsize=5, rotation=90)
        ax.set_ylim(0, 1.32)
        ax.set_yticks([0, 0.5, 1])
        ax.set_title(title, pad=2)
        ax.set_xticks(x)
        ax.set_xticklabels([str(i + 1) for i in x])
        ax.set_xlabel("Cliente (por tamanho)")
    axes[0].set_ylabel("Fração por classe")
    fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=3, frameon=False,
               bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(pad=0.3, rect=(0, 0.07, 1, 1))
    save_fig(fig, out, "particao.pdf")


def fig_cost(h2, out):
    markers = {"fedavg-full": "o", "fedprox-full": "s", "scaffold-full": "^", "fedavg-lora": "D"}
    colors = {"fedavg-full": "#1f4e79", "fedprox-full": "#4a7c6f", "scaffold-full": "#b7943a", "fedavg-lora": "#b4432a"}
    fig, ax = plt.subplots(figsize=(3.45, 2.3))
    for m, mlabel in METHODS:
        xs, ys, es = [], [], []
        for p, _ in PARTS:
            rs = by_seed(h2, f"{m}_{p}_sev0.0")
            c = [first_cross(r["rows"], TARGET)[1] for r in rs]
            ok = [v / 1e9 for v in c if v is not None]
            if not ok:
                continue
            xs.append(st.mean(r["summary"]["kl_mean"] for r in rs))
            ys.append(st.mean(ok))
            es.append(st.stdev(ok) if len(ok) > 1 else 0)
        ax.errorbar(xs, ys, yerr=es, marker=markers[m], ms=3.5, lw=0.9, capsize=2, color=colors[m], label=mlabel)
    ax.set_yscale("log")
    ax.set_xlabel(r"KL médio realizado ($\overline{\mathrm{KL}}$)")
    ax.set_ylabel(r"$C_{total}$ até BACC 0,75 (GB)")
    ax.legend(frameon=False, ncol=2, loc="upper left")
    fig.tight_layout(pad=0.3)
    save_fig(fig, out, "custo_kl.pdf")


def fig_h3(h3, h3c, out):
    fig, axes = plt.subplots(1, 2, figsize=(3.45, 1.9), sharey=False)
    for ax, (peft, plabel) in zip(axes, (("full", "Ajuste completo"), ("lora", "LoRA"))):
        for harm, suffix_runs, ls, lab, col in (
                ("", (h3, ""), "-", "deformada, sem harm.", "#1f4e79"),
                ("_harm", (h3, ""), "--", "deformada, com harm.", "#1f4e79"),
                ("", (h3c, "_cleaneval"), "-", "limpa, sem harm.", "#b4432a"),
                ("_harm", (h3c, "_cleaneval"), "--", "limpa, com harm.", "#b4432a")):
            runs, suffix = suffix_runs
            xs, ys = [], []
            for sev in ("0.0", "0.5", "1.0"):
                src, suf = (h3, "") if sev == "0.0" else (runs, suffix)
                rs = by_seed(src, f"fedavg-{peft}_iid_sev{sev}{harm}{suf}")
                r = mean_hits(rounds_to(rs))
                if r is not None:
                    xs.append(float(sev))
                    ys.append(r)
            if len(xs) > 1:
                ax.plot(xs, ys, ls=ls, marker="o", ms=3, lw=0.9, color=col, label=lab)
        ax.set_title(plabel)
        ax.set_xlabel("Severidade $s$")
        ax.set_xticks([0, 0.5, 1.0])
    axes[0].set_ylabel(r"$R$ até BACC 0,75")
    axes[1].legend(frameon=False, fontsize=6, loc="upper left")
    fig.tight_layout(pad=0.3)
    save_fig(fig, out, "h3.pdf")


# ---------------------------------------------------------------- números para o texto
def numbers(h2, h3, h3c, out):
    """Macros LaTeX com os números citados no texto (\\newcommand), para nada ser digitado à mão."""
    macros = {}

    fa_iid, fa_01 = by_seed(h2, "fedavg-full_iid_sev0.0"), by_seed(h2, "fedavg-full_dir0.1_sev0.0")
    if fa_iid and fa_01:
        macros["RiidFedAvg"] = num(mean_hits(rounds_to(fa_iid)))
        macros["RaltaFedAvg"] = num(mean_hits(rounds_to(fa_01)))
        macros["RazaoAltaFedAvg"] = num(mean_hits(rounds_to(fa_01)) / mean_hits(rounds_to(fa_iid)))
        c_iid = st.mean(first_cross(r["rows"], TARGET)[1] for r in fa_iid) / 1e9
        c_01 = [first_cross(r["rows"], TARGET)[1] for r in fa_01]
        c_01 = st.mean(x for x in c_01 if x is not None) / 1e9
        macros["CiidFedAvg"] = num(c_iid)
        macros["CaltaFedAvg"] = num(c_01)
        macros["KLalta"] = num(st.mean(r["summary"]["kl_mean"] for r in fa_01), 2)
        macros["NseedsAlta"] = str(len(fa_01))
    lo_01 = by_seed(h2, "fedavg-lora_dir0.1_sev0.0")
    if lo_01:
        c = [first_cross(r["rows"], TARGET)[1] for r in lo_01]
        macros["CaltaLoRA"] = num(st.mean(x for x in c if x is not None) / 1e9, 2)
        macros["CensLoRAalta"] = str(sum(1 for x in c if x is None))
    lo_iid = by_seed(h2, "fedavg-lora_iid_sev0.0")
    if fa_iid and lo_iid:
        full_b = fa_iid[0]["rows"][0]["round_bytes"]
        lora_b = lo_iid[0]["rows"][0]["round_bytes"]
        macros["MBrodadaFull"] = num(full_b / 1e6, 0)
        macros["MBrodadaLoRA"] = num(lora_b / 1e6, 1)
        macros["RazaoBytesLoRA"] = num(full_b / lora_b, 0)
    # LoRA com alpha = 0,1: execuções censuradas contadas como 100 rodadas (limite inferior do custo)
    if lo_01:
        per = lo_01[0]["rows"][0]["round_bytes"]
        c = [first_cross(r["rows"], TARGET)[1] or 100 * per for r in lo_01]
        macros["CaltaLoRAcens"] = num(st.mean(c) / 1e9, 2)
    # critério sustentado com tau = 0,72 (LoRA e FedAvg, alpha = 0,1)
    for key, rs in (("FedAvg", fa_01), ("LoRA", lo_01)):
        if rs:
            v = [sustained_cross(r["rows"], 0.72) for r in rs]
            ok = [x for x in v if x[0] is not None]
            macros[f"SustRk{key}"] = num(st.mean(x[0] for x in ok))
            macros[f"SustCk{key}"] = num(st.mean(x[1] for x in ok) / 1e9, 2 if key == "LoRA" else 1)
            macros[f"SustN{key}"] = str(len(ok))
    if fa_01 and lo_01:
        cf = st.mean(x[1] for x in (sustained_cross(r["rows"], 0.72) for r in fa_01) if x[0] is not None)
        cl = st.mean(x[1] for x in (sustained_cross(r["rows"], 0.72) for r in lo_01) if x[0] is not None)
        macros["SustRazao"] = num(cf / cl, 0)
        maxv = [max(row["val_bacc"] for row in r["rows"]) for r in lo_01]
        macros["MaxValLoRAmin"], macros["MaxValLoRAmax"] = num(min(maxv), 3), num(max(maxv), 3)
        macros["SustLoRAalta"] = str(n_sustained(lo_01))
    for p, key in (("dir0.2", "Dois"), ("dir0.15", "Quinze")):
        rs = by_seed(h2, f"fedavg-full_{p}_sev0.0")
        if rs:
            macros[f"R{key}FedAvg"] = num(mean_hits(rounds_to(rs)))
            macros[f"KL{key}"] = num(st.mean(r["summary"]["kl_mean"] for r in rs), 2)
    # dispersão dos tamanhos dos clientes por partição
    for p, key in (("dir0.3", "Tres"), ("dir0.2", "Dois"), ("dir0.15", "Quinze"), ("dir0.1", "Um")):
        rs = by_seed(h2, f"fedavg-full_{p}_sev0.0")
        if rs:
            cv = [size_cv(r) for r in rs]
            macros[f"CVmin{key}"], macros[f"CVmax{key}"] = num(min(cv), 2), num(max(cv), 2)
    # efeito da severidade (s = 1 contra s = 0, sem harmonização, avaliação deformada), pareado
    for peft, key in (("full", "Full"), ("lora", "LoRA")):
        a = rounds_to(by_seed(h3, f"fedavg-{peft}_iid_sev0.0"))
        b = rounds_to(by_seed(h3, f"fedavg-{peft}_iid_sev1.0"))
        if a and b and None not in a + b:
            d, lo, hi = ci_paired([y - x for x, y in zip(a, b)])
            macros[f"DSev{key}"], macros[f"DSev{key}Lo"], macros[f"DSev{key}Hi"] = num(d), num(lo), num(hi)
    write_macros(out, "numeros.tex", macros)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="runs_final")
    ap.add_argument("--out", default="../artigo-experimental")
    args = ap.parse_args()
    g = {name: load_grid(args.runs, name) for name in PAPER_GRIDS}
    g["h2"].update(g["alpha_extra"])  # FedAvg com alpha = 0,2 e 0,15 (só FedAvg; os outros métodos não rodaram)
    print({k: len(v) for k, v in g.items()})
    table_h12(g["h2"], args.out)
    table_targets(g["h2"], args.out)
    table_h3(g["h3"], g["h3clean"], args.out)
    table_ablation(g["h2"], g["sens"], g["abl_mu"], g["abl_lora"], args.out)
    table_scaffold(g["h2"], g["scaffold_var"], args.out, g["seeds_novas"])
    numbers_scaffold(g["h2"], g["scaffold_var"], g["seeds_novas"], args.out)
    numbers(g["h2"], g["h3"], g["h3clean"], args.out)
    fig_curves(g["h2"], args.out)
    fig_cost(g["h2"], args.out)
    fig_h3(g["h3"], g["h3clean"], args.out)
    fig_scaffold(g["h2"], g["scaffold_var"], args.out)
    fig_partition(g["h2"], args.out)


if __name__ == "__main__":
    main()
