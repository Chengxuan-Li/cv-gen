"""Lint rules for content that is structurally valid but semantically wrong.

Neither rule can be caught by a schema, and both fail silently - the build
succeeds and produces a document that is quietly incorrect. That is exactly why
they are worth a separate pass.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from .diagnostics import Problem, format_path, line_index
from .schema import LOCAL_SUFFIX, local_profile_path

# '+Design' is not a marker - the grammar needs a space - so it renders a literal
# '+' and the item stays in the short CV. Restricted to a following letter so
# that '-5% peak load reduction' and '+1 (555) 000-0000' are not flagged.
NEAR_MISS = re.compile(r"^[+-][A-Za-z]")

# Only email addresses and phone numbers are sensitive. A public URL - a personal
# site, an ORCID, a GitHub profile - belongs in the tracked file, so the rule
# looks for the two things that actually matter rather than flagging every line
# that fails to look like a placeholder.
EMAIL = re.compile(r"[\w.+-]+@([\w-]+\.[\w.]+)")
PHONE = re.compile(r"\+?\d[\d\s()\-]{6,}\d")
PLACEHOLDER_DOMAINS = ("example.com", "example.org", "example.net")
PLACEHOLDER_PHONE = "555"


def _sensitive(entry: str) -> str:
    """Name what looks real in a contact line, or '' if nothing does."""
    for domain in EMAIL.findall(entry):
        if domain.lower() not in PLACEHOLDER_DOMAINS:
            return f"an email address at {domain}"
    for number in PHONE.findall(entry):
        if PLACEHOLDER_PHONE not in number:
            return "a phone number"
    return ""


def _scalars(text: str) -> list[tuple[tuple, str, int]]:
    """Every string scalar in a YAML document, as (path, value, line)."""
    try:
        root = yaml.compose(text)
    except yaml.YAMLError:
        return []
    if root is None:
        return []

    found: list[tuple[tuple, str, int]] = []

    def walk(node: yaml.Node, path: tuple) -> None:
        if isinstance(node, yaml.MappingNode):
            for key, value in node.value:
                walk(value, path + (key.value,))
        elif isinstance(node, yaml.SequenceNode):
            for index, value in enumerate(node.value):
                walk(value, path + (index,))
        elif isinstance(node, yaml.ScalarNode) and node.tag.endswith(":str"):
            found.append((path, node.value, node.start_mark.line + 1))

    walk(root, ())
    return found


def _linted_files(root: Path) -> list[Path]:
    files = [
        p
        for p in sorted((root / "content").glob("*.yaml"))
        if not p.name.endswith(LOCAL_SUFFIX)
    ]
    variants = root / "variants.yaml"
    if variants.exists():
        files.append(variants)
    return files


def _near_miss_markers(path: Path) -> list[Problem]:
    findings = []
    for node_path, value, line in _scalars(path.read_text(encoding="utf-8")):
        if not NEAR_MISS.match(value):
            continue
        where = format_path(node_path)
        findings.append(
            Problem(
                file=path.name,
                code="near_miss_marker",
                message=(
                    f"{path.name}: {where}: starts with {value[0]!r} but no space follows, "
                    f"so it is literal text rather than a marker"
                ),
                line=line,
                path=where,
                hint=(
                    f"write '{value[0]} ...' or '{value[0]}[variant] ...' for a marker, "
                    f"or '\\{value[0]}' to keep a literal {value[0]!r}"
                ),
            )
        )
    return findings


def _real_contact(profile: Path) -> list[Problem]:
    data = yaml.safe_load(profile.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return []
    lines = line_index(profile.read_text(encoding="utf-8"))
    local = local_profile_path(profile).name
    findings = []
    for index, entry in enumerate(data.get("contact") or []):
        what = _sensitive(str(entry))
        if not what:
            continue
        findings.append(
            Problem(
                file=profile.name,
                code="real_contact_in_tracked_profile",
                message=(
                    f"{profile.name}: contact[{index}] looks like {what}; "
                    f"real details belong in {local}"
                ),
                line=lines.get(("contact", index)),
                path=f"contact[{index}]",
                hint=(
                    "this file is tracked - a committed phone number cannot be removed "
                    "without rewriting history"
                ),
            )
        )
    return findings


def lint(root: Path) -> list[Problem]:
    """Every lint finding. An empty list means clean."""
    findings: list[Problem] = []
    for path in _linted_files(root):
        findings += _near_miss_markers(path)

    profile = root / "content" / "profile.yaml"
    if profile.exists():
        findings += _real_contact(profile)
    return findings
