"""Configuração: leitura do YAML, overrides da linha de comando e os rótulos que descrevem uma execução."""
import copy
from pathlib import Path

import yaml

BASE_CONFIG = Path(__file__).resolve().parents[1] / "configs" / "base.yaml"


def apply_overrides(cfg, overrides):
    """Aplica overrides no formato 'a.b.c=valor' sobre um dicionário aninhado."""
    cfg = copy.deepcopy(cfg)
    for item in overrides or []:
        key, sep, value = item.partition("=")
        if not sep:
            raise ValueError(f"override sem '=': {item}")
        node = cfg
        parts = key.split(".")
        for p in parts[:-1]:
            if not isinstance(node.get(p), dict):
                raise KeyError(f"seção desconhecida no config: {key}")
            node = node[p]
        if parts[-1] not in node:
            raise KeyError(f"chave desconhecida no config: {key}")
        node[parts[-1]] = yaml.safe_load(value)
    return cfg


def load_config(path=BASE_CONFIG, overrides=None):
    with open(path) as f:
        cfg = yaml.safe_load(f)
    return apply_overrides(cfg, overrides)


# campos criados depois das primeiras execuções do artigo, com o comportamento que essas execuções tiveram
_FIELDS_ADDED_LATER = {("fl", "scaffold_variant"): "orig", ("acquisition", "eval_profiles"): True}


def with_defaults(cfg):
    """Completa um config gravado antes de existirem os campos de _FIELDS_ADDED_LATER."""
    cfg = copy.deepcopy(cfg)
    for (section, field), value in _FIELDS_ADDED_LATER.items():
        cfg[section].setdefault(field, value)
    return cfg


def partition_tag(scheme, alpha):
    return "iid" if scheme == "iid" else f"dir{alpha}"


def run_name(cfg):
    if cfg["train"]["run_name"]:
        return cfg["train"]["run_name"]
    p, a, m, f = cfg["partition"], cfg["acquisition"], cfg["model"], cfg["fl"]
    name = f"{f['method']}-{m['peft']}_{partition_tag(p['scheme'], p['alpha'])}_sev{a['severity']}"
    if a["harmonize"]:
        name += "_harm"
    if not a["eval_profiles"]:
        name += "_cleaneval"
    return f"{name}_s{cfg['seed']}"


def acquisition_active(cfg):
    """Há perfis de aquisição simulados ou harmonização nesta execução."""
    a = cfg["acquisition"]
    return a["severity"] > 0 or a["harmonize"]


def het_label(cfg):
    """Rótulo legível da heterogeneidade: partição e, se houver, aquisição simulada."""
    p, a = cfg["partition"], cfg["acquisition"]
    het = "IID" if p["scheme"] == "iid" else f"α={p['alpha']}"
    if acquisition_active(cfg):
        het += f" sev={a['severity']}" + (" +harm" if a["harmonize"] else "")
    return het


# campos que só valem para um método ou modo, o valor da configuração principal do artigo e como aparecem
# na chave quando fogem dele (fixos aqui, e não lidos do base.yaml, para os rótulos das execuções já feitas
# não mudarem se um padrão do YAML mudar)
_VARIANT_FIELDS = [("scaffold", ("fl", "scaffold_variant"), "orig", "-{}"), ("fedprox", ("fl", "mu"), 0.01, "-mu{}"),
                   ("lora", ("model", "lora_r"), 8, "-r{}")]


def method_key(cfg):
    """Método e modo de ajuste (ex.: fedavg-full), mais a variante quando ela foge da configuração principal."""
    cfg = with_defaults(cfg)
    key = f"{cfg['fl']['method']}-{cfg['model']['peft']}"
    for owner, (section, field), principal, fmt in _VARIANT_FIELDS:
        value = cfg[section][field]
        if owner in (cfg["fl"]["method"], cfg["model"]["peft"]) and value != principal:
            key += fmt.format(value)
    return key
