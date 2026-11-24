"""Download, preparação e carga do conjunto de pneumonia pediátrica (Kermany et al., 2018).

Dados: Kermany, Zhang e Goldbaum (2018), Mendeley Data, doi:10.17632/rscbjbr9sj.2, licença CC BY 4.0.
Estrutura esperada após descompactar ChestXRay2017.zip:
    <raiz>/chest_xray/{train,test}/{NORMAL,PNEUMONIA}/*.jpeg
As pneumonias são separadas em bacteriana e viral pelo nome do arquivo.
O conjunto de teste oficial é mantido; a validação sai do treino, separada por paciente.
"""
import hashlib
import re
import urllib.request
import zipfile
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import torch
from PIL import Image

ZIP_URL = ("https://data.mendeley.com/public-files/datasets/rscbjbr9sj/files/"
           "f12eaf6d-6023-432f-acc9-80c9d7393433/file_downloaded")
ZIP_SHA256 = "13efc055629733dbab07877f8b3c9f81097840dbcdaa326a8542322c2281ce36"
CLASSES = ["normal", "bacteria", "virus"]
SPLITS = {"train": 0, "val": 1, "test": 2}
IMG_SIZE = 224


def download_kermany(raw):
    """Baixa o ZIP (1,2 GB) para raw/, confere o SHA-256 e descompacta em raw/."""
    raw = Path(raw)
    raw.mkdir(parents=True, exist_ok=True)
    zpath = raw / "ChestXRay2017.zip"
    if not zpath.exists():
        print("baixando do Mendeley (1,2 GB)...", flush=True)
        # o Mendeley devolve 403 para o User-Agent padrão do urllib
        req = urllib.request.Request(ZIP_URL, headers={"User-Agent": "curl/8.7.1"})
        tmp = zpath.with_suffix(".part")
        with urllib.request.urlopen(req) as r, open(tmp, "wb") as f:
            for chunk in iter(lambda: r.read(1 << 20), b""):
                f.write(chunk)
        tmp.rename(zpath)
    h = hashlib.sha256()
    with open(zpath, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    if h.hexdigest() != ZIP_SHA256:
        raise SystemExit(f"SHA-256 não confere para {zpath}; apague o arquivo e baixe de novo")
    zipfile.ZipFile(zpath).extractall(raw)


def _label_and_patient(path: Path):
    name = path.name.lower()
    if path.parent.name.upper() == "NORMAL":
        # ex.: IM-0115-0001.jpeg, NORMAL2-IM-1427-0001.jpeg
        return 0, "n:" + re.sub(r"-\d+\.jpe?g$", "", name)
    if "bacteria" in name:
        label = 1
    elif "virus" in name:
        label = 2
    else:
        return None, None
    m = re.match(r"(person\d+)", name)
    return label, "p:" + (m.group(1) if m else name)


def _official_split(path: Path):
    for part in reversed(path.parts):
        if part.lower() in ("train", "val", "test"):
            return part.lower()
    return None


def _load_image(path):
    img = Image.open(path).convert("L").resize((IMG_SIZE, IMG_SIZE), Image.BILINEAR)
    return np.asarray(img, dtype=np.uint8)


def prepare_kermany(raw_root, out_path, val_frac=0.1, seed=0, workers=8):
    raw_root = Path(raw_root)
    seen, records = set(), []
    for p in sorted(raw_root.rglob("*.jp*g")):
        if "__MACOSX" in p.parts or p.name.startswith("."):
            continue
        split = _official_split(p)
        label, patient = _label_and_patient(p)
        key = (split, p.parent.name.upper(), p.name)
        if split is None or label is None or key in seen:
            continue
        seen.add(key)
        records.append((p, split, label, patient))
    if not records:
        raise FileNotFoundError(f"nenhuma imagem encontrada em {raw_root}")

    with Pool(workers) as pool:
        images = pool.map(_load_image, [r[0] for r in records], chunksize=64)

    labels = np.array([r[2] for r in records], dtype=np.int64)
    patients = [r[3] for r in records]
    # treino + val oficiais (o val oficial tem 16 imagens) viram o pool de treino
    split = np.array([SPLITS["test"] if r[1] == "test" else SPLITS["train"] for r in records])

    # validação separada por paciente, para não vazar imagens do mesmo paciente
    rng = np.random.default_rng(seed)
    pool_pat = sorted({patients[i] for i in np.where(split == SPLITS["train"])[0]})
    rng.shuffle(pool_pat)
    n_val = int(round(val_frac * len(pool_pat)))
    val_pat = set(pool_pat[:n_val])
    for i in np.where(split == SPLITS["train"])[0]:
        if patients[i] in val_pat:
            split[i] = SPLITS["val"]

    data = {
        "images": torch.from_numpy(np.stack(images)),
        "labels": torch.from_numpy(labels),
        "split": torch.from_numpy(split),
        "patients": patients,
        "classes": CLASSES,
    }
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    torch.save(data, out_path)
    return data


def synthetic_dataset(n=900, size=64, seed=0):
    """Conjunto aleatório e aprendível, só para testar o código sem dados reais."""
    g = torch.Generator().manual_seed(seed)
    labels = torch.randint(0, 3, (n,), generator=g)
    base = torch.rand(n, size, size, generator=g) * 120
    base += labels.view(-1, 1, 1).float() * 50
    split = torch.zeros(n, dtype=torch.long)
    split[int(0.7 * n):int(0.8 * n)] = SPLITS["val"]
    split[int(0.8 * n):] = SPLITS["test"]
    return {"images": base.clamp(0, 255).to(torch.uint8), "labels": labels, "split": split,
            "patients": [f"s{i}" for i in range(n)], "classes": CLASSES}


def load_dataset(cfg):
    if cfg["data"]["synthetic"]:
        return synthetic_dataset(seed=cfg["seed"])
    return torch.load(cfg["data"]["path"], weights_only=False)


def summarize(data):
    out = {}
    for name, code in SPLITS.items():
        mask = data["split"] == code
        counts = torch.bincount(data["labels"][mask], minlength=len(CLASSES)).tolist()
        out[name] = dict(zip(CLASSES, counts))
    return out
