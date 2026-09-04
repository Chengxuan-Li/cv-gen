import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

import build
from cvgen.schema import load
from cvgen.select import select

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


@pytest.mark.parametrize("length", ["long", "short"])
def test_each_document_contains_exactly_its_declared_sections(built, length):
    """Derived from variants.yaml rather than hardcoded.

    An earlier version listed section titles literally, so simply dropping a
    section from variants.yaml failed a test that had nothing to say about the
    change. What is worth pinning is the mechanism: a document renders the
    sections it declares, in order, and nothing else.
    """
    config = load(ROOT)
    doc = select(config, length, "general")
    qmd = (ROOT / ".build" / f"cv-{length}-general.qmd").read_text(encoding="utf-8")

    rendered = [line[3:] for line in qmd.splitlines() if line.startswith("## ")]
    assert rendered == [s.title for s in doc.sections]

    undeclared = set(config.sections) - {s.name for s in doc.sections}
    for name in undeclared:
        assert f"## {config.sections[name].title}" not in qmd


def test_markdown_survives_into_the_document(built):
    qmd = (ROOT / ".build" / "cv-long-general.qmd").read_text(encoding="utf-8")
    assert "**CBRE GWS**" in qmd
    assert "[DOI: 10.1080/19401493.2025.2536261]" in qmd


def test_every_link_carries_a_visible_mark(built):
    """Underlining alone reads as emphasis on paper, so links get a trailing mark.

    Asserted against the generated .typ rather than templates/cv.typ, so this
    fails if the rule stops reaching the pipeline as well as if it is deleted.
    """
    typ = (ROOT / ".build" / "cv-long-general.typ").read_text(encoding="utf-8")
    assert "#let link-mark" in typ
    # The mark trails the link text; pinned so the order is not flipped silently.
    assert "#show link: it => [#underline[#it]#h(0.08em)#link-mark]" in typ
    # The rule is worthless if the document has no links to apply it to.
    assert typ.count("#link(") > 5


def test_the_link_icon_is_staged_beside_the_generated_typst(built):
    """cv.typ references it with a bare path, which only resolves inside .build/."""
    icon = ROOT / ".build" / "link-icon.svg"
    assert icon.exists(), "link-icon.svg was not staged; Typst cannot resolve it"
    assert icon.read_bytes() == (ROOT / "templates" / "link-icon.svg").read_bytes()
    typ = (ROOT / ".build" / "cv-long-general.typ").read_text(encoding="utf-8")
    assert 'image("link-icon.svg"' in typ
