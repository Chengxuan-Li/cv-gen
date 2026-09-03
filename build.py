#!/usr/bin/env python
"""Build PDF CVs from content/*.yml.

    python build.py --all
    python build.py --long
    python build.py --long --variant gev-pos-1
    python build.py --check
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from cvgen.emit import render
from cvgen.schema import Config, ValidationError, load
from cvgen.select import SelectionError, select

BUILD_DIR = Path(".build")
OUT_DIR = Path("out")
FALLBACK_QUARTO = Path(r"C:\Program Files\Quarto\bin\quarto.exe")


class BuildError(Exception):
    """A document's PDF did not end up where it was expected."""


def find_quarto() -> str:
    """Locate the Quarto executable, which is not always on PATH on Windows."""
    found = shutil.which("quarto")
    if found:
        return found
    if FALLBACK_QUARTO.exists():
        return str(FALLBACK_QUARTO)
    raise SystemExit(
        "quarto not found on PATH.\n"
        "  Install it with:  winget install Posit.Quarto"
    )


def documents_for(config: Config, length: str | None, variant: str | None) -> list[tuple[str, str]]:
    """Resolve CLI selectors to the list of documents to build."""
    documents = config.all_documents()
    if length:
        documents = [d for d in documents if d[0] == length]
    if variant:
        documents = [d for d in documents if d[1] == variant]
    if not documents:
        available = ", ".join(f"{a}/{b}" for a, b in sorted(config.all_documents()))
        raise SystemExit(
            f"no document matches length={length!r} variant={variant!r}\n"
            f"  declared: {available}"
        )
    return documents


def build_one(config: Config, quarto: str, length: str, variant: str) -> Path:
    doc = select(config, length, variant)
    BUILD_DIR.mkdir(exist_ok=True)
    OUT_DIR.mkdir(exist_ok=True)
    qmd = BUILD_DIR / f"{doc.name}.qmd"
    qmd.write_text(render(doc), encoding="utf-8")

    pdf = OUT_DIR / f"{doc.name}.pdf"
    subprocess.run(
        [quarto, "render", str(qmd), "--to", "typst", "--output", pdf.name],
        check=True,
    )
    # Quarto writes the output next to the input; move it into out/.
    produced = qmd.with_suffix(".pdf")
    if produced.exists():
        produced.replace(pdf)
    if not pdf.exists():
        raise BuildError(
            f"{length}/{variant}: quarto exited successfully but no PDF was found at {pdf}"
        )
    return pdf


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="build every declared document")
    length_group = parser.add_mutually_exclusive_group()
    length_group.add_argument("--long", dest="length", action="store_const", const="long")
    length_group.add_argument("--short", dest="length", action="store_const", const="short")
    parser.add_argument("--variant", help="build only this variant")
    parser.add_argument("--check", action="store_true", help="validate content, render nothing")
    args = parser.parse_args(argv)

    try:
        config = load(Path.cwd())
    except ValidationError as exc:
        print(f"content is invalid:\n{exc}", file=sys.stderr)
        return 1

    if args.check:
        problems: list[str] = []
        for length, variant in config.all_documents():
            try:
                select(config, length, variant)
            except SelectionError as exc:
                problems.append(f"{length}/{variant}: {exc}")
        if problems:
            joined = "\n".join(f"  - {p}" for p in problems)
            print(f"content is invalid:\n{joined}", file=sys.stderr)
            return 1
        print(f"content is valid: {len(config.all_documents())} documents declared")
        return 0

    if not (args.all or args.length or args.variant):
        parser.error("choose --all, --long, --short, --variant or --check")

    try:
        documents = documents_for(config, args.length, args.variant)
        quarto = find_quarto()
        for length, variant in documents:
            print(f"building {length}/{variant}")
            try:
                print(f"  wrote {build_one(config, quarto, length, variant)}")
            except subprocess.CalledProcessError as exc:
                print(
                    f"quarto failed on {length}/{variant} with exit code {exc.returncode}",
                    file=sys.stderr,
                )
                return 1
    except SelectionError as exc:
        print(f"cannot build: {exc}", file=sys.stderr)
        return 1
    except BuildError as exc:
        print(f"cannot build: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
