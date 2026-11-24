"""Grades de experimentos do artigo: cada job é uma lista de overrides sobre o base.yaml.

Usadas por scripts/run_grid.py (máquina própria), modal_run.py, pelo notebook do Colab, pelo dashboard
(execuções esperadas por grade) e por scripts/paper_figures.py (quais grades ler).

Os nomes das execuções do artigo estão congelados em runs_final/; as variantes que o nome automático
(config.run_name) não distingue recebem um nome explícito.
"""
import itertools

from .config import partition_tag

SEEDS = [0, 1, 2]
SEEDS_ALTA = [0, 1, 2, 3, 4]
# lr por modo, escolhida num piloto (100 rodadas, α = 0,1): o ajuste completo diverge com 0,01 no não-IID
# e o LoRA precisa de um passo maior
LR = {"full": 0.003, "lora": 0.01}
ALPHAS_H2 = [None, 1.0, 0.5, 0.3, 0.1]  # None = IID
METHODS_H2 = [("fedavg", "full"), ("fedprox", "full"), ("scaffold", "full"), ("fedavg", "lora")]


def seeds_for(alpha):
    """Cinco seeds em α = 0,1, onde a variância entre seeds é maior; três nos demais."""
    return SEEDS_ALTA if alpha == 0.1 else SEEDS


def job(method, peft, alpha, seed, *extra, lr=None, label=None, suffix=""):
    """Overrides de uma execução. alpha=None é a partição IID.

    label (e suffix) dão o nome explícito <label>_<partição><suffix>_s<seed>.
    """
    scheme = "iid" if alpha is None else "dirichlet"
    ov = [f"partition.scheme={scheme}"] + ([] if alpha is None else [f"partition.alpha={alpha}"])
    ov += [f"fl.method={method}", f"model.peft={peft}", f"fl.lr={LR[peft] if lr is None else lr}", *extra,
           f"seed={seed}"]
    if label:
        ov.append(f"train.run_name={label}_{partition_tag(scheme, alpha)}{suffix}_s{seed}")
    return ov


def smoke():  # 3 rodadas, para conferir a instalação
    return [job(m, peft, a, 0, "fl.rounds=3") for (m, peft), a in itertools.product(METHODS_H2, [None, 0.1])]


def h2():  # rótulos x métodos
    return [job(m, peft, a, s) for (m, peft), a in itertools.product(METHODS_H2, ALPHAS_H2) for s in seeds_for(a)]


def _h3(sevs, *extra):
    return [job("fedavg", peft, None, s, f"acquisition.severity={sev}", f"acquisition.harmonize={str(harm).lower()}",
                *extra)
            for peft, sev, harm, s in itertools.product(["full", "lora"], sevs, [False, True], SEEDS)]


def h3():  # aquisição simulada
    return _h3([0.0, 0.5, 1.0])


def h3clean():  # idem, com validação e teste sem deformação
    return _h3([0.5, 1.0], "acquisition.eval_profiles=false")


def sens():  # SCAFFOLD com taxa menor (só três seeds)
    return [job("scaffold", "full", 0.1, s, lr=0.001, label="scaffold-full", suffix="_sev0.0_lr0.001") for s in SEEDS]


def abl_mu():  # FedProx com outros mu
    return [job("fedprox", "full", 0.1, s, f"fl.mu={mu}", label="fedprox-full", suffix=f"_mu{mu}")
            for mu in [0.001, 0.1] for s in seeds_for(0.1)]


def abl_lora():  # posto do LoRA (alpha_LoRA = 2r, como no principal)
    return [job("fedavg", "lora", a, s, f"model.lora_r={r}", f"model.lora_alpha={2 * r}", label=f"fedavg-lora-r{r}")
            for r, a in itertools.product([4, 16], [None, 0.1]) for s in seeds_for(a)]


def scaffold_var():  # variantes de agregação do SCAFFOLD (Seção V-D)
    cases = [("cweighted", 0.1), ("cweighted", None), ("cweighted", 0.3), ("uniform", 0.1), ("clip", 0.1)]
    return [job("scaffold", "full", a, s, f"fl.scaffold_variant={v}", label=f"scaffold-{v}")
            for v, a in cases for s in seeds_for(a)]


def seeds_novas():  # replicação do diagnóstico do SCAFFOLD em seeds que não o geraram
    return [j for s in range(5, 10) for j in (
        job("fedavg", "full", 0.1, s), job("scaffold", "full", 0.1, s),
        job("scaffold", "full", 0.1, s, "fl.scaffold_variant=cweighted", label="scaffold-cweighted"))]


def alpha_extra():  # localiza o salto de custo entre alpha = 0,3 e 0,1
    return [job("fedavg", "full", a, s) for a, s in itertools.product([0.2, 0.15], SEEDS)]


GRIDS = {f.__name__: f for f in (smoke, h2, h3, h3clean, sens, abl_mu, abl_lora, scaffold_var, seeds_novas,
                                 alpha_extra)}
# grades do artigo, na ordem da Seção IV (as complementares rodaram depois da primeira análise)
PAPER_GRIDS = ["h2", "h3", "h3clean", "sens", "abl_mu", "abl_lora", "scaffold_var", "seeds_novas", "alpha_extra"]


def grid(name):
    if name not in GRIDS:
        raise ValueError(f"grade desconhecida: {name}")
    return GRIDS[name]()


def grids(name):
    """Lista de (grade, jobs); 'paper' expande para todas as grades do artigo."""
    names = PAPER_GRIDS if name == "paper" else [name]
    return [(n, grid(n)) for n in names]
