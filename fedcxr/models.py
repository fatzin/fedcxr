"""ViT do timm, com ajuste completo ou adaptadores LoRA."""
import math

import timm
import torch
import torch.nn as nn

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


class LoRALinear(nn.Module):
    def __init__(self, base: nn.Linear, r: int, alpha: float):
        super().__init__()
        self.base = base
        for p in self.base.parameters():
            p.requires_grad_(False)
        self.lora_A = nn.Parameter(torch.empty(r, base.in_features))
        self.lora_B = nn.Parameter(torch.zeros(base.out_features, r))
        nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))
        self.scale = alpha / r

    def forward(self, x):
        return self.base(x) + (x @ self.lora_A.t() @ self.lora_B.t()) * self.scale


def apply_lora(model, r, alpha, targets):
    for p in model.parameters():
        p.requires_grad_(False)
    for name, module in list(model.named_modules()):
        for child_name, child in list(module.named_children()):
            full = f"{name}.{child_name}" if name else child_name
            if isinstance(child, nn.Linear) and any(full.endswith(t) for t in targets):
                setattr(module, child_name, LoRALinear(child, r, alpha))
    for p in model.get_classifier().parameters():
        p.requires_grad_(True)
    return model


def build_model(cfg, num_classes, img_size):
    m = cfg["model"]
    model = timm.create_model(m["name"], pretrained=m["pretrained"], num_classes=num_classes,
                              img_size=img_size)
    if m["peft"] == "lora":
        apply_lora(model, m["lora_r"], m["lora_alpha"], m["lora_targets"])
    elif m["peft"] != "full":
        raise ValueError(m["peft"])
    return model


def count_params(model):
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    return {"total": total, "trainable": trainable}


def to_input(x_uint8, device):
    """uint8 [n, H, W] -> float normalizado [n, 3, H, W]."""
    x = x_uint8.to(device, non_blocking=True).float().div_(255.0).unsqueeze(1).expand(-1, 3, -1, -1)
    mean = torch.tensor(IMAGENET_MEAN, device=device).view(1, 3, 1, 1)
    std = torch.tensor(IMAGENET_STD, device=device).view(1, 3, 1, 1)
    return (x - mean) / std
