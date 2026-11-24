"""Os números do artigo: as tabelas geradas a partir de runs_final/ não podem mudar."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = Path(__file__).parent / "golden" / "tabelas"


def test_paper_tables_are_unchanged(tmp_path):
    subprocess.run([sys.executable, str(ROOT / "scripts" / "paper_figures.py"), "--runs", str(ROOT / "runs_final"),
                    "--out", str(tmp_path)], check=True, capture_output=True)
    made = sorted(p.name for p in (tmp_path / "tabelas").iterdir())
    assert made == sorted(p.name for p in GOLDEN.iterdir())
    for name in made:
        assert (tmp_path / "tabelas" / name).read_text() == (GOLDEN / name).read_text(), name
    assert len(list((tmp_path / "figuras").glob("*.pdf"))) == 5
