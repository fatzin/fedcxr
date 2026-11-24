"""Partição dos dados de treino entre clientes e medida do grau Non-IID realizado."""
import numpy as np


def iid(indices, num_clients, rng):
    idx = rng.permutation(indices)
    return [np.sort(p) for p in np.array_split(idx, num_clients)]


def dirichlet(indices, labels, num_clients, alpha, rng, min_size=20, max_tries=1000):
    """Para cada classe, divide suas amostras entre os clientes com proporções ~ Dir(alpha).

    Esquema usado pela maioria dos estudos revisados (proporção de cada classe entre clientes).
    Reamostra até todo cliente ter pelo menos `min_size` amostras.
    """
    indices = np.asarray(indices)
    classes = np.unique(labels[indices])
    for _ in range(max_tries):
        parts = [[] for _ in range(num_clients)]
        for c in classes:
            idx_c = rng.permutation(indices[labels[indices] == c])
            props = rng.dirichlet(alpha * np.ones(num_clients))
            cuts = (np.cumsum(props) * len(idx_c)).astype(int)[:-1]
            for k, chunk in enumerate(np.split(idx_c, cuts)):
                parts[k].extend(chunk.tolist())
        if min(len(p) for p in parts) >= min_size:
            return [np.sort(np.array(p, dtype=np.int64)) for p in parts]
    raise RuntimeError(f"não foi possível ter {min_size} amostras por cliente com alpha={alpha}")


def make_partition(cfg, train_idx, labels, rng):
    p = cfg["partition"]
    if p["scheme"] == "iid":
        return iid(train_idx, p["num_clients"], rng)
    if p["scheme"] == "dirichlet":
        return dirichlet(train_idx, labels, p["num_clients"], p["alpha"], rng, p["min_size"])
    raise ValueError(p["scheme"])


def label_stats(parts, labels, num_classes, eps=1e-8):
    """Distribuição de rótulos por cliente e KL(P_k(y) || P(y)) em relação ao total do treino."""
    all_idx = np.concatenate(parts)
    p_global = np.bincount(labels[all_idx], minlength=num_classes) / len(all_idx)
    rows = []
    for k, part in enumerate(parts):
        counts = np.bincount(labels[part], minlength=num_classes)
        p_k = counts / counts.sum()
        kl = float(np.sum(np.where(p_k > 0, p_k * np.log((p_k + eps) / (p_global + eps)), 0.0)))
        rows.append({"client": k, "n": int(counts.sum()), "counts": counts.tolist(), "kl": kl})
    kls = [r["kl"] for r in rows]
    return {"clients": rows, "kl_mean": float(np.mean(kls)), "kl_max": float(np.max(kls)),
            "p_global": p_global.tolist()}
