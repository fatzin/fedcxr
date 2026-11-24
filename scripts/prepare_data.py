"""Baixa (opcional) e converte o ChestXRay2017 em um único tensor uint8 224x224.

    python scripts/prepare_data.py --download                          # baixa do Mendeley, confere o SHA-256 e prepara
    python scripts/prepare_data.py --raw data/raw --out data/prepared/kermany.pt   # se já tiver descompactado
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fedcxr.data import download_kermany, prepare_kermany, summarize  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--out", default="data/prepared/kermany.pt")
    ap.add_argument("--val-frac", type=float, default=0.1)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--download", action="store_true", help="baixa o ZIP do Mendeley para --raw antes de preparar")
    args = ap.parse_args()
    if args.download:
        download_kermany(args.raw)

    data = prepare_kermany(args.raw, args.out, val_frac=args.val_frac, workers=args.workers)
    print(json.dumps(summarize(data), indent=2))
    print(f"{len(data['labels'])} imagens salvas em {args.out}")


if __name__ == "__main__":
    main()
