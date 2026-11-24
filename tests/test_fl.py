"""Agregação no servidor."""
import torch

from fedcxr import fl
from fedcxr.config import BASE_CONFIG, load_config


def _aggregate(method, variant, clients):
    cfg = load_config(BASE_CONFIG, [f"fl.method={method}", f"fl.scaffold_variant={variant}",
                                            "partition.num_clients=4"])
    server = fl.Server({"w": torch.zeros(1)}, cfg)
    server.begin_round(len(clients), sum(n for n, _ in clients))
    for n, w in clients:
        server.add(n, {"w": torch.tensor([w])}, {"w": torch.tensor([w])})
    return server.end_round()["w"].item(), (server.c_global["w"].item() if server.c_global else None)


def test_model_is_weighted_by_client_size():
    assert _aggregate("fedavg", "orig", [(1, 1.0), (3, 5.0)])[0] == 4.0


def test_scaffold_variants_weight_model_and_control_variates():
    clients = [(1, 1.0), (3, 5.0)]
    assert _aggregate("scaffold", "orig", clients) == (4.0, 1.5)       # c: soma / K, com K = 4 clientes
    assert _aggregate("scaffold", "uniform", clients) == (3.0, 1.5)    # modelo: média simples da rodada
    assert _aggregate("scaffold", "cweighted", clients) == (4.0, 4.0)  # c: mesmo peso n_k/n do modelo

