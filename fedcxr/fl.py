"""Treino local e agregação no servidor: FedAvg, FedProx e SCAFFOLD (com as variantes de agregação).

Todos os clientes compartilham um único objeto de modelo na GPU: antes de treinar um cliente,
os parâmetros globais são copiados para ele. Só os parâmetros treináveis trafegam
(no LoRA, adaptadores + cabeça; no ajuste completo, a rede inteira).

Variantes do SCAFFOLD (fl.scaffold_variant):
    orig       modelo ponderado por n_k/n e c com peso 1/K (K = total de clientes); "principal" no artigo
    cweighted  modelo e c ponderados por n_k/n
    uniform    modelo pela média simples dos clientes da rodada e c com peso 1/K, como no SCAFFOLD original
    clip       orig, com a correção local limitada à norma do gradiente do lote
"""
import math

import torch
import torch.nn.functional as F

from .models import to_input


def trainable(model):
    return {n: p for n, p in model.named_parameters() if p.requires_grad}


def get_state(model):
    return {n: p.detach().clone() for n, p in trainable(model).items()}


@torch.no_grad()
def set_state(model, state):
    for n, p in trainable(model).items():
        p.copy_(state[n])


def zeros_like_state(state):
    return {k: torch.zeros_like(v) for k, v in state.items()}


def _augment(x):
    """Deslocamento aleatório de até 8 px (mesmo deslocamento para o lote inteiro)."""
    pad = 8
    x = F.pad(x, (pad, pad, pad, pad), mode="reflect")
    i, j = torch.randint(0, 2 * pad + 1, (2,)).tolist()
    return x[..., i:i + x.shape[-2] - 2 * pad, j:j + x.shape[-1] - 2 * pad]


def _autocast(device, amp):
    if device.type != "cuda" or amp == "none":
        return torch.autocast(device_type="cpu", enabled=False)
    dtype = torch.bfloat16 if amp == "bf16" else torch.float16
    return torch.autocast(device_type="cuda", dtype=dtype)


def local_train(model, global_state, images, labels, cfg, device, c_global=None, c_local=None):
    """Treina um cliente a partir do estado global. Devolve (estado novo, delta c, estatísticas locais)."""
    f = cfg["fl"]
    method = f["method"]
    set_state(model, global_state)
    model.train()
    params = trainable(model)
    opt = torch.optim.SGD(params.values(), lr=f["lr"], momentum=f["momentum"],
                          weight_decay=f["weight_decay"])
    scaler = torch.amp.GradScaler("cuda", enabled=(device.type == "cuda" and cfg["train"]["amp"] == "fp16"))
    n = len(labels)
    bs = f["batch_size"]
    steps = 0
    loss_sum = torch.zeros((), device=device)
    correct = torch.zeros((), device=device)
    seen = 0
    for _ in range(f["local_epochs"]):
        perm = torch.randperm(n, device=labels.device)
        for b in range(0, n, bs):
            idx = perm[b:b + bs]
            if len(idx) < 2:
                continue
            x = _augment(to_input(images[idx], device))
            y = labels[idx].to(device)
            with _autocast(device, cfg["train"]["amp"]):
                logits = model(x)
                loss = F.cross_entropy(logits, y)
            loss_sum += loss.detach().float() * len(idx)
            correct += (logits.detach().argmax(1) == y).sum()
            seen += len(idx)
            if method == "fedprox":
                prox = sum(((p - global_state[k]) ** 2).sum() for k, p in params.items())
                loss = loss + 0.5 * f["mu"] * prox
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            if method == "scaffold":
                scaler.unscale_(opt)
                corr = {k: c_global[k] - c_local[k] for k in params}
                if f["scaffold_variant"] == "clip":
                    g_norm = torch.sqrt(sum((p.grad.float() ** 2).sum() for p in params.values() if p.grad is not None))
                    c_norm = torch.sqrt(sum((v.float() ** 2).sum() for v in corr.values()))
                    scale = torch.clamp(g_norm / (c_norm + 1e-12), max=1.0)
                    corr = {k: v * scale for k, v in corr.items()}
                for k, p in params.items():
                    if p.grad is not None:
                        p.grad.add_(corr[k])
            scaler.step(opt)
            scaler.update()
            steps += 1
    new_state = get_state(model)
    delta_c = None
    if method == "scaffold":
        # opção II do SCAFFOLD: c_i+ = c_i - c + (x - y_i) / (K * lr)
        coef = 1.0 / (max(steps, 1) * f["lr"])
        new_c = {k: c_local[k] - c_global[k] + (global_state[k] - new_state[k]) * coef for k in new_state}
        delta_c = {k: new_c[k] - c_local[k] for k in new_state}
        for k in new_state:
            c_local[k].copy_(new_c[k])
    stats = {"steps": steps, "train_loss": (loss_sum / max(seen, 1)).item(),
             "train_acc": (correct / max(seen, 1)).item()}
    return new_state, delta_c, stats


def flat_delta(new_state, old_state):
    return torch.cat([(new_state[k] - old_state[k]).float().flatten() for k in old_state])


@torch.no_grad()
def evaluate(model, images, labels, device, cfg):
    model.eval()
    logits = []
    for b in range(0, len(labels), cfg["eval"]["batch_size"]):
        x = to_input(images[b:b + cfg["eval"]["batch_size"]], device)
        with _autocast(device, cfg["train"]["amp"]):
            logits.append(model(x).float())
    logits = torch.cat(logits)
    y = labels.to(device)
    loss = F.cross_entropy(logits, y).item()
    return logits.softmax(1).cpu(), y.cpu(), loss


class Server:
    """Estado global e agregação. No SCAFFOLD guarda também c e o c_k de cada cliente."""

    def __init__(self, global_state, cfg):
        self.state = global_state
        self.fl = cfg["fl"]
        self.scaffold = self.fl["method"] == "scaffold"
        self.num_clients = cfg["partition"]["num_clients"]
        self.c_global = zeros_like_state(global_state) if self.scaffold else None
        self.c_locals = [zeros_like_state(global_state) for _ in range(self.num_clients)] if self.scaffold else None

    def local_train(self, model, client, images, labels, cfg, device):
        c_local = self.c_locals[client] if self.scaffold else None
        return local_train(model, self.state, images, labels, cfg, device, self.c_global, c_local)

    def begin_round(self, n_selected, n_samples):
        """n_selected clientes nesta rodada, somando n_samples amostras."""
        self._m, self._n = n_selected, n_samples
        self._acc = zeros_like_state(self.state)
        self._acc_c = zeros_like_state(self.state) if self.scaffold else None

    def add(self, n, new_state, delta_c):
        """Acumula a resposta de um cliente com n amostras (em fluxo, sem guardar os estados)."""
        variant = self.fl["scaffold_variant"] if self.scaffold else None
        w = 1.0 / self._m if variant == "uniform" else n / self._n
        for k in self._acc:
            self._acc[k].add_(new_state[k], alpha=w)
        if self.scaffold:
            wc = n / self._n if variant == "cweighted" else 1.0 / self.num_clients
            for k in self._acc_c:
                self._acc_c[k].add_(delta_c[k], alpha=wc)

    def end_round(self):
        if self.scaffold:
            lr_g = self.fl["server_lr"]
            self.state = {k: self.state[k] + lr_g * (self._acc[k] - self.state[k]) for k in self._acc}
            for k in self.c_global:
                self.c_global[k].add_(self._acc_c[k])
        else:
            self.state = self._acc
        return self.state


def round_seed(seed, rnd):
    return int(seed) * 100003 + rnd


def select_clients(num_clients, participation, generator):
    m = max(1, int(math.ceil(participation * num_clients)))
    return sorted(torch.randperm(num_clients, generator=generator)[:m].tolist())
