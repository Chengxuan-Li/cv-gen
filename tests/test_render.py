import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

import build

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def built() -> list[Path]:
    result = subprocess.run(
        [sys.executable, "build.py", "--all"], cwd=ROOT, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    return sorted((ROOT / "out").glob("*.pdf"))


def test_every_declared_document_builds(built):
    names = {p.name for p in built}
    assert names == {"cv-long-general.pdf", "cv-short-general.pdf"}


def test_pdfs_are_not_trivial(built):
    for pdf in built:
        assert pdf.stat().st_size > 5000, f"{pdf.name} is suspiciously small"


def page_count(pdf: Path) -> int:
    """Count pages by rasterising with Typst rather than regexing the PDF bytes.

    Typst's PDF object streams are compressed, so a `/Type /Page` byte-regex
    over the raw PDF finds zero (or a wrong count) -- verified against the
    real output of this build. `quarto typst compile` against the
    intermediate .typ file emits one PNG per page, so the number of PNGs it
    writes is a reliable page count.
    """
    quarto = build.find_quarto()
    typ = ROOT / ".build" / f"{pdf.stem}.typ"
    assert typ.exists(), f"expected intermediate {typ} to exist"
    with tempfile.TemporaryDirectory() as tmp:
        # {p} is a page-number template; typst refuses a bare filename for a
        # multi-page export, so this must always be used, not just when we
        # expect more than one page.
        out_pattern = Path(tmp) / "page{p}.png"
        subprocess.run(
            [quarto, "typst", "compile", str(typ), str(out_pattern), "--format", "png"],
            check=True,
            capture_output=True,
        )
        return len(list(Path(tmp).glob("page*.png")))


def test_short_variant_is_one_page(built):
    short = next(p for p in built if p.name == "cv-short-general.pdf")
    assert page_count(short) == 1


def test_long_contains_sections_short_omits(built):
    qmd_long = (ROOT / ".build" / "cv-long-general.qmd").read_text(encoding="utf-8")
    qmd_short = (ROOT / ".build" / "cv-short-general.qmd").read_text(encoding="utf-8")
    assert "## Selected Publications" in qmd_long
    assert "## Selected Publications" not in qmd_short
    assert "## Experience" in qmd_short


def test_markdown_survives_into_the_document(built):
    qmd = (ROOT / ".build" / "cv-long-general.qmd").read_text(encoding="utf-8")
    assert "**CBRE GWS**" in qmd
    assert "[DOI: 10.1080/19401493.2025.2536261]" in qmd
