"""Medida do custo de comunicação.

O tamanho de cada mensagem é medido serializando os tensores que de fato trafegam
(torch.save em memória, float32), e não estimado pelo número de parâmetros.
Também guardamos o payload bruto (numel x 4 bytes) para comparação.
"""
import io

import torch


def serialized_nbytes(tensors: dict) -> int:
    buf = io.BytesIO()
    torch.save({k: v.detach().float().cpu().contiguous() for k, v in tensors.items()}, buf)
    return buf.getbuffer().nbytes


def raw_nbytes(tensors: dict) -> int:
    return sum(v.numel() * 4 for v in tensors.values())


def message_sizes(method, state):
    """Bytes de uma mensagem servidor->cliente (down) e cliente->servidor (up).

    FedAvg e FedProx enviam os parâmetros treináveis nos dois sentidos.
    SCAFFOLD envia também a variável de controle (c para baixo, delta c para cima).
    """
    one = serialized_nbytes(state)
    raw = raw_nbytes(state)
    if method == "scaffold":
        # c tem o mesmo formato de x; clone para o torch.save não deduplicar o armazenamento
        both = {**{f"x.{k}": v for k, v in state.items()}, **{f"c.{k}": v.clone() for k, v in state.items()}}
        two = serialized_nbytes(both)
        return {"down": two, "up": two, "raw_down": 2 * raw, "raw_up": 2 * raw}
    return {"down": one, "up": one, "raw_down": raw, "raw_up": raw}
