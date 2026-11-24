"""LoRA e medida do tamanho das mensagens."""
import torch
import torch.nn as nn

from fedcxr import comm
from fedcxr.models import LoRALinear, apply_lora


def test_message_size_matches_raw_payload():
    state = {"w": torch.randn(1000, 100), "b": torch.randn(100)}
    s = comm.message_sizes("fedavg", state)
    assert s["raw_up"] == 100100 * 4
    assert s["raw_up"] <= s["up"] < s["raw_up"] * 1.05  # o cabeçalho do torch.save é pequeno


def test_scaffold_message_is_twice_as_large():
    state = {"w": torch.randn(1000, 100), "b": torch.randn(100)}
    fedavg, scaffold = comm.message_sizes("fedavg", state), comm.message_sizes("scaffold", state)
    assert abs(scaffold["up"] - 2 * fedavg["up"]) / fedavg["up"] < 0.05


def test_lora_starts_equal_to_base_layer():
    base = nn.Linear(16, 8)
    x = torch.randn(4, 16)
    assert torch.allclose(LoRALinear(base, r=2, alpha=4)(x), base(x))


def test_lora_trains_only_adapters_and_head():
    model = nn.Sequential(nn.Linear(16, 8), nn.ReLU(), nn.Linear(8, 3))
    model.get_classifier = lambda: model[2]
    apply_lora(model, 2, 4, targets=["0"])
    trainable = {n for n, p in model.named_parameters() if p.requires_grad}
    assert trainable == {"0.lora_A", "0.lora_B", "2.weight", "2.bias"}
