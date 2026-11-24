"""Executa uma simulação federada e grava o log por rodada e o resumo final.

    python -m fedcxr.train --config configs/base.yaml --set fl.method=scaffold fl.lr=0.003 partition.alpha=0.1

As grades do artigo (fedcxr/grids.py) fixam fl.lr por modo de ajuste; o 0,01 do base.yaml é o do LoRA.
"""
import argparse
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

from . import acquisition, comm, fl, partition, runlog
from .config import BASE_CONFIG, acquisition_active, load_config, run_name
from .data import SPLITS, load_dataset, summarize
from .metrics import classification_metrics
from .models import build_model, count_params


def set_seed(seed):
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def gpu_info(device):
    """Nome e endereço PCI da GPU (o dashboard usa o endereço para ligar a execução ao nvidia-smi)."""
    if device.type != "cuda":
        return {}
    props = torch.cuda.get_device_properties(0)
    domain, bus, dev = (getattr(props, k, 0) for k in ("pci_domain_id", "pci_bus_id", "pci_device_id"))
    return {"name": props.name, "pci_bus_id": f"{domain:08X}:{bus:02X}:{dev:02X}.0"}


@dataclass
class ClientData:
    images: torch.Tensor          # todas as imagens, já com perfil de aquisição e harmonização (se pedidos)
    parts: list                   # índices de treino de cada cliente
    val_idx: np.ndarray
    test_idx: np.ndarray
    label_stats: dict
    profiles: list | None
    extra_down: int               # bytes enviados uma única vez antes do treino (CDF de referência)


def build_client_data(cfg, data, rng):
    """Particiona o treino e aplica (se pedido) a aquisição simulada e a harmonização."""
    labels_np = data["labels"].numpy()
    split = data["split"].numpy()
    train_idx = np.where(split == SPLITS["train"])[0]
    val_idx = np.where(split == SPLITS["val"])[0]
    test_idx = np.where(split == SPLITS["test"])[0]
    parts = partition.make_partition(cfg, train_idx, labels_np, rng)
    stats = partition.label_stats(parts, labels_np, len(data["classes"]))

    images = data["images"].clone()
    a = cfg["acquisition"]
    extra_down = 0
    profiles = None
    if acquisition_active(cfg):
        k = cfg["partition"]["num_clients"]
        profiles = acquisition.sample_profiles(k, a["severity"], cfg["seed"])
        ref = None
        if a["harmonize"]:
            # CDF de referência: imagens originais do treino, sem perfil (papel de modelo público)
            ref_idx = rng.choice(train_idx, size=min(a["ref_images"], len(train_idx)), replace=False)
            ref = acquisition.reference_cdf(data["images"][ref_idx])
            extra_down = comm.serialized_nbytes({"ref_cdf": ref}) * k
        # validação e teste viram uma mistura dos aparelhos: cada fatia recebe o perfil de um cliente
        val_shares = np.array_split(rng.permutation(val_idx), k)
        test_shares = np.array_split(rng.permutation(test_idx), k)
        for c in range(k):
            for j, idx in enumerate((parts[c], val_shares[c], test_shares[c])):
                idx_t = torch.as_tensor(idx, dtype=torch.long)
                if j == 0 or a["eval_profiles"]:
                    out = acquisition.apply_profile(data["images"][idx_t], profiles[c],
                                                    seed=cfg["seed"] * 1000 + c * 10 + j)
                else:  # avaliação limpa: só a harmonização (parte do pipeline) é aplicada
                    out = data["images"][idx_t]
                if ref is not None:
                    out = acquisition.harmonize(out, ref)
                images[idx_t] = out
    return ClientData(images, parts, val_idx, test_idx, stats, profiles, extra_down)


def run(cfg):
    set_seed(cfg["seed"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    name = run_name(cfg)
    log = runlog.RunWriter(Path(cfg["train"]["out_dir"]) / name)
    log.write(runlog.CONFIG, cfg)

    data = load_dataset(cfg)
    rng = np.random.default_rng(cfg["seed"])
    cd = build_client_data(cfg, data, rng)
    parts, stats = cd.parts, cd.label_stats
    log.write(runlog.PARTITION, {"label_stats": stats, "profiles": cd.profiles, "dataset": summarize(data)})

    # tudo na GPU como uint8: o conjunto inteiro cabe com folga e evita gargalo de CPU
    images = cd.images.to(device)
    labels = data["labels"].to(device)
    client_idx = [torch.as_tensor(p, device=device) for p in parts]
    val_t = torch.as_tensor(cd.val_idx, device=device)
    test_t = torch.as_tensor(cd.test_idx, device=device)

    model = build_model(cfg, num_classes=len(data["classes"]), img_size=images.shape[-1]).to(device)
    server = fl.Server(fl.get_state(model), cfg)
    method = cfg["fl"]["method"]
    sizes = comm.message_sizes(method, server.state)
    k = cfg["partition"]["num_clients"]

    meta = {"run": name, "device": str(device), "params": count_params(model), "message_bytes": sizes,
            "extra_down_bytes": cd.extra_down, "client_sizes": [len(p) for p in parts],
            "kl_mean": stats["kl_mean"], "kl_max": stats["kl_max"]}
    print(json.dumps(meta))
    log.write(runlog.STATUS, {
        "pid": os.getpid(), "gpu": gpu_info(device), "started": time.time(), "rounds": cfg["fl"]["rounds"],
        "n_train": int(sum(len(p) for p in parts)), "lr": cfg["fl"]["lr"], "method": method,
        "peft": cfg["model"]["peft"], "num_clients": k})
    gen = torch.Generator().manual_seed(cfg["seed"])
    cum_bytes = cd.extra_down
    target = cfg["fl"]["early_stop_target"]
    reached = None
    t_start = time.time()

    with log:
        for rnd in range(1, cfg["fl"]["rounds"] + 1):
            t0 = time.time()
            torch.manual_seed(fl.round_seed(cfg["seed"], rnd))
            sel = fl.select_clients(k, cfg["fl"]["participation"], gen)
            n_sel = sum(len(client_idx[c]) for c in sel)
            server.begin_round(len(sel), n_sel)
            client_rows, deltas = [], []
            for c in sel:
                idx = client_idx[c]
                tc = time.time()
                new_state, delta_c, cstats = server.local_train(model, c, images[idx], labels[idx], cfg, device)
                d = fl.flat_delta(new_state, server.state)
                deltas.append(d)
                client_rows.append({"id": c, "n": len(idx), "loss": round(cstats["train_loss"], 4),
                                    "acc": round(cstats["train_acc"], 4), "steps": cstats["steps"],
                                    "sec": round(time.time() - tc, 2), "upd_norm": round(d.norm().item(), 4)})
                server.add(len(idx), new_state, delta_c)
            global_state = server.end_round()
            # alinhamento de cada atualização local com a atualização média (cosseno): mede o client drift
            mean_delta = sum(d * (r["n"] / n_sel) for d, r in zip(deltas, client_rows))
            mnorm = mean_delta.norm().clamp_min(1e-12)
            for d, r in zip(deltas, client_rows):
                r["cos"] = round((d @ mean_delta / (d.norm().clamp_min(1e-12) * mnorm)).item(), 4)
            del deltas, mean_delta
            round_bytes = len(sel) * (sizes["down"] + sizes["up"])
            cum_bytes += round_bytes

            fl.set_state(model, global_state)
            probs, y, val_loss = fl.evaluate(model, images[val_t], labels[val_t], device, cfg)
            val = classification_metrics(probs, y)
            row = {"round": rnd, "val_bacc": val["bacc"], "val_acc": val["acc"], "val_f1": val["f1_macro"],
                   "val_auc": val["auc_macro"], "val_loss": val_loss, "round_bytes": round_bytes,
                   "cum_bytes": cum_bytes, "clients": len(sel), "sec": round(time.time() - t0, 2),
                   "train_loss": sum(r["loss"] * r["n"] for r in client_rows) / n_sel,
                   "train_acc": sum(r["acc"] * r["n"] for r in client_rows) / n_sel,
                   "cos_mean": sum(r["cos"] * r["n"] for r in client_rows) / n_sel,
                   "imgs_per_sec": round(n_sel * cfg["fl"]["local_epochs"] / max(time.time() - t0, 1e-6), 1),
                   "client_stats": client_rows}
            if rnd % cfg["eval"]["test_every"] == 0 or rnd == cfg["fl"]["rounds"]:
                probs, y, _ = fl.evaluate(model, images[test_t], labels[test_t], device, cfg)
                row["test_bacc"] = classification_metrics(probs, y)["bacc"]
            log.append_round(row)
            print(f"[{name}] r{rnd:03d} val_bacc={val['bacc']:.4f} loss={val_loss:.4f} "
                  f"MB={cum_bytes / 1e6:.1f} {row['sec']}s", flush=True)
            if target is not None and val["bacc"] >= target:
                reached = rnd
                break

    probs, y, test_loss = fl.evaluate(model, images[test_t], labels[test_t], device, cfg)
    summary = {**meta, "rounds_run": rnd, "target": target, "rounds_to_target": reached,
               "total_bytes": cum_bytes, "test": classification_metrics(probs, y), "test_loss": test_loss,
               "wall_sec": round(time.time() - t_start, 1)}
    if cfg["train"]["save_model"]:
        # só os parâmetros treináveis (no LoRA, adaptadores + cabeça); a base vem do timm
        torch.save({k: v.detach().cpu() for k, v in global_state.items()}, log.dir / runlog.FINAL_STATE)
    log.write(runlog.SUMMARY, summary)
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(BASE_CONFIG))
    ap.add_argument("--set", nargs="*", default=[], help="overrides a.b=valor")
    args = ap.parse_args()
    run(load_config(args.config, args.set))


if __name__ == "__main__":
    main()
