#!/usr/bin/env python
"""Build PDF CVs from content/*.yml.

    python build.py --all
    python build.py --long
    python build.py --long --variant general
    python build.py --check
    python build.py --check --json
    python build.py --lint
    python build.py --explain long/general
    python build.py --schema

Exit codes are part of the contract: 0 success, 1 content or build failure,
2 usage error (argparse's own).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from cvgen.diagnostics import Problem
from cvgen.emit import render
from cvgen.explain import explain
from cvgen.explain import render as render_explanation
from cvgen.jsonschema import write as write_schemas
from cvgen.lint import lint
from cvgen.schema import Config, ValidationError, load
from cvgen.select import SelectionError, select

BUILD_DIR = Path(".build")
OUT_DIR = Path("out")
FALLBACK_QUARTO = Path(r"C:\Program Files\Quarto\bin\quarto.exe")
LOCAL_PROFILE = "content/profile.local.yml"


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
    # Quarto resolves a bare --output filename relative to its own process
    # cwd, not relative to the input file. Run it with cwd=BUILD_DIR (and
    # pass bare filenames) so the intermediate .typ and the rendered PDF both
    # land next to the .qmd, in .build/, where we then move the PDF from.
    subprocess.run(
        [
            quarto, "render", qmd.name,
            "--to", "typst",
            "--output", pdf.name,
            "-M", "keep-typ:true",  # keep the intermediate .typ in .build/
        ],
        cwd=BUILD_DIR,
        check=True,
    )
    produced = qmd.with_suffix(".pdf")
    if produced.exists():
        produced.replace(pdf)
    if not pdf.exists():
        raise BuildError(
            f"{length}/{variant}: quarto exited successfully but no PDF was found at {pdf}"
        )
    return pdf


def report_contact_source(config: Config, as_json: bool = False) -> None:
    """Say which file supplied the contact details, every run.

    The dangerous outcome here is sending someone a CV carrying the placeholder
    phone number, so a missing override is announced loudly rather than assumed.

    Under --json, stdout is reserved for the JSON document - anything else there
    makes the output unparseable - so the confirmation is suppressed and the
    caller reads `contact_source` from the payload instead. The warning still
    goes to stderr, which never pollutes stdout.
    """
    if config.profile.has_local_override:
        if not as_json:
            print(f"contact: {LOCAL_PROFILE}")
    else:
        print(
            f"WARNING: {LOCAL_PROFILE} not found - using PLACEHOLDER contact details",
            file=sys.stderr,
        )


def parse_document(spec: str) -> tuple[str, str]:
    """'long/general' -> ('long', 'general')"""
    length, _, variant = spec.partition("/")
    if not variant:
        raise SystemExit(f"--explain takes LENGTH/VARIANT, e.g. long/general (got {spec!r})")
    return length, variant


def run_lint(root: Path, as_json: bool) -> int:
    findings = lint(root)
    if as_json:
        print(json.dumps({"ok": not findings, "findings": [f.as_dict() for f in findings]}, indent=2))
    elif findings:
        joined = "\n".join(f"  - {f}\n    hint: {f.hint}" for f in findings)
        print(f"lint found {len(findings)} problem(s):\n{joined}", file=sys.stderr)
    else:
        print("lint clean")
    return 1 if findings else 0


def run_explain(config: Config, spec: str, as_json: bool) -> int:
    length, variant = parse_document(spec)
    try:
        decisions = explain(config, length, variant)
    except SelectionError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if as_json:
        print(
            json.dumps(
                {
                    "document": f"{length}/{variant}",
                    "items": [d.as_dict() for d in decisions],
                },
                indent=2,
            )
        )
    else:
        included = sum(1 for d in decisions if d.included)
        print(f"{length}/{variant}: {included} of {len(decisions)} items included")
        print(render_explanation(decisions))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="build every declared document")
    length_group = parser.add_mutually_exclusive_group()
    length_group.add_argument("--long", dest="length", action="store_const", const="long")
    length_group.add_argument("--short", dest="length", action="store_const", const="short")
    parser.add_argument("--variant", help="build only this variant")
    parser.add_argument("--check", action="store_true", help="validate content, render nothing")
    parser.add_argument("--lint", action="store_true", help="check for silent semantic mistakes")
    parser.add_argument("--explain", metavar="LENGTH/VARIANT", help="why each item is in or out")
    parser.add_argument("--schema", action="store_true", help="regenerate schema/*.json")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    root = Path.cwd()

    if args.schema:
        written = write_schemas(root)
        if args.json:
            print(json.dumps({"ok": True, "written": [str(p) for p in written]}, indent=2))
        else:
            for path in written:
                print(f"wrote {path}")
        return 0

    if args.lint:
        return run_lint(root, args.json)

    try:
        config = load(root)
    except ValidationError as exc:
        if args.json:
            print(json.dumps(exc.as_dict(), indent=2))
        else:
            print(f"content is invalid:\n{exc}", file=sys.stderr)
        return 1

    if args.explain:
        return run_explain(config, args.explain, args.json)

    report_contact_source(config, args.json)

    if args.check:
        problems = []
        for length, variant in config.all_documents():
            try:
                select(config, length, variant)
            except SelectionError as exc:
                problems.append(
                    Problem(
                        file="variants.yml",
                        code="no_surviving_tagline",
                        message=f"{length}/{variant}: {exc}",
                        path=f"{length}/{variant}",
                    )
                )
        if problems:
            if args.json:
                print(json.dumps({"ok": False, "problems": [p.as_dict() for p in problems]}, indent=2))
            else:
                joined = "\n".join(f"  - {p}" for p in problems)
                print(f"content is invalid:\n{joined}", file=sys.stderr)
            return 1
        documents = config.all_documents()
        if args.json:
            print(
                json.dumps(
                    {
                        "ok": True,
                        "documents": [f"{a}/{b}" for a, b in documents],
                        "contact_source": (
                            LOCAL_PROFILE if config.profile.has_local_override else "placeholder"
                        ),
                    },
                    indent=2,
                )
            )
        else:
            print(f"content is valid: {len(documents)} documents declared")
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
