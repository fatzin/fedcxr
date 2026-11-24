"""Heterogeneidade de aquisição simulada (feature skew) e harmonização local por histograma.

Cada cliente recebe um "perfil de aparelho": resolução efetiva, borramento, curva gama,
contraste e brilho, CLAHE e ruído. O parâmetro `severity` em [0, 1] controla o quanto os
perfis se afastam da imagem original; severity = 0 é a identidade.

A harmonização mapeia o histograma de cada imagem para um CDF de referência com 256 valores,
calculado uma vez a partir de imagens públicas e enviado aos clientes (1 KB, contado no custo).
"""
import math

import numpy as np
import torch
import torch.nn.functional as F
from torchvision.transforms.functional import gaussian_blur


def sample_profiles(num_clients, severity, seed):
    rng = np.random.default_rng(seed + 7919)
    s = float(severity)
    profiles = []
    for _ in range(num_clients):
        profiles.append({
            "downsample": 1.0 + rng.uniform(0, 2.0) * s,
            "blur_sigma": rng.uniform(0, 1.5) * s,
            "gamma": math.exp(rng.uniform(-1, 1) * s * math.log(2.0)),
            "contrast": 1.0 + rng.uniform(-0.4, 0.4) * s,
            "brightness": rng.uniform(-0.1, 0.1) * s,
            "clahe": bool(rng.random() < 0.5 * s),
            "noise_std": rng.uniform(0, 0.04) * s,
        })
    return profiles


def _clahe(x):
    from skimage import exposure
    out = np.stack([exposure.equalize_adapthist(img, clip_limit=0.01) for img in x.numpy()])
    return torch.from_numpy(out).float()


def apply_profile(images, profile, seed):
    """images: uint8 [n, H, W] (CPU). Devolve uint8 com o perfil aplicado."""
    if len(images) == 0:
        return images
    x = images.float().div(255.0).unsqueeze(1)
    h, w = x.shape[-2:]
    f = profile["downsample"]
    if f > 1.01:
        small = (max(8, round(h / f)), max(8, round(w / f)))
        x = F.interpolate(x, size=small, mode="bilinear", antialias=True, align_corners=False)
        x = F.interpolate(x, size=(h, w), mode="bilinear", align_corners=False)
    if profile["blur_sigma"] > 0.05:
        k = 2 * math.ceil(3 * profile["blur_sigma"]) + 1
        x = gaussian_blur(x, [k, k], [profile["blur_sigma"]] * 2)
    x = x.clamp(0, 1).pow(profile["gamma"])
    x = (x - 0.5) * profile["contrast"] + 0.5 + profile["brightness"]
    x = x.clamp(0, 1).squeeze(1)
    if profile["clahe"]:
        x = _clahe(x)
    if profile["noise_std"] > 0:
        g = torch.Generator().manual_seed(seed)
        x = x + torch.randn(x.shape, generator=g) * profile["noise_std"]
    return (x.clamp(0, 1) * 255).round().to(torch.uint8)


def reference_cdf(images):
    hist = torch.bincount(images.flatten().long(), minlength=256).double()
    cdf = torch.cumsum(hist, 0) / hist.sum()
    return cdf.float()


def harmonize(images, ref_cdf):
    """Histogram matching de cada imagem para o CDF de referência."""
    ref = ref_cdf.numpy()
    levels = np.arange(256)
    out = np.empty_like(images.numpy())
    for i, img in enumerate(images.numpy()):
        hist = np.bincount(img.ravel(), minlength=256)
        cdf = np.cumsum(hist) / hist.sum()
        mapping = np.interp(cdf, ref, levels)
        out[i] = np.clip(np.round(mapping[img]), 0, 255)
    return torch.from_numpy(out)
