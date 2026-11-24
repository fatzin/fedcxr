"""Métricas de classificação (acurácia balanceada, F1 e AUC macro) e critérios de chegada ao alvo."""
import numpy as np
from sklearn.metrics import balanced_accuracy_score, f1_score, roc_auc_score


def classification_metrics(probs, y):
    probs, y = np.asarray(probs), np.asarray(y)
    pred = probs.argmax(1)
    out = {
        "bacc": float(balanced_accuracy_score(y, pred)),
        "acc": float((pred == y).mean()),
        "f1_macro": float(f1_score(y, pred, average="macro")),
        "f1_per_class": f1_score(y, pred, average=None, labels=list(range(probs.shape[1]))).tolist(),
    }
    try:
        out["auc_macro"] = float(roc_auc_score(y, probs, multi_class="ovr", average="macro"))
    except ValueError:
        out["auc_macro"] = None
    return out


def first_cross(rows, t):
    """(rodada, bytes acumulados) da primeira rodada com BACC de validação >= t; (None, None) se nunca."""
    for r in rows:
        if r["val_bacc"] >= t:
            return r["round"], r["cum_bytes"]
    return None, None


def sustained_cross(rows, t, k=3):
    """Primeira rodada que inicia k rodadas seguidas com BACC de validação >= t (critério sustentado)."""
    v = [r["val_bacc"] >= t for r in rows]
    for i in range(len(v) - k + 1):
        if all(v[i:i + k]):
            return rows[i]["round"], rows[i]["cum_bytes"]
    return None, None
