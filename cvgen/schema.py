"""Load and validate the content files.

This module owns every load-time error message. Validation runs to completion
and collects all problems so one run surfaces every issue; each message names
the file and the item index, because a user editing YAML needs to know *where*.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .marker import GENERAL, Marked, Marker, MarkerError, parse_item, parse_mark

BLOCK_TYPES = ("labels", "entries", "rows", "prose")
LENGTHS = ("long", "short")
ENTRY_FIELDS = ("org", "location", "dates", "role")


class ValidationError(Exception):
    """One or more content files are invalid."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = list(problems)
        super().__init__("\n".join(f"  - {p}" for p in self.problems))


@dataclass(frozen=True)
class Item:
    marker: Marker
    text: str
    date: str = ""


@dataclass(frozen=True)
class Label:
    marker: Marker
    label: str
    text: str


@dataclass(frozen=True)
class Entry:
    marker: Marker
    org: str
    location: str
    dates: str
    role: str
    bullets: tuple[Item, ...]


@dataclass(frozen=True)
class Section:
    name: str
    title: str
    type: str
    items: tuple[object, ...]


@dataclass(frozen=True)
class Profile:
    name: str
    contact: tuple[str, ...]
    taglines: tuple[Item, ...]


@dataclass(frozen=True)
class Config:
    profile: Profile
    sections: dict[str, Section]
    documents: dict[str, dict[str, tuple[str, ...]]]

    def all_documents(self) -> list[tuple[str, str]]:
        return [(length, v) for length, variants in self.documents.items() for v in variants]

    def declared_variants(self) -> set[str]:
        return {v for variants in self.documents.values() for v in variants}


def _read_yaml(path: Path, problems: list[str]) -> dict:
    if not path.exists():
        problems.append(f"{path.name}: file not found at {path}")
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        problems.append(f"{path.name}: invalid YAML - {exc}")
        return {}

    if data is None:
        problems.append(f"{path.name}: empty file")
        return {}
    if not isinstance(data, dict):
        problems.append(f"{path.name}: expected a mapping, got {type(data).__name__}")
        return {}
    return data


def _item(raw: object, where: str, problems: list[str]) -> Item:
    """Parse a flat item, which is a string or a {text, date} mapping."""
    date = ""
    if isinstance(raw, dict):
        date = str(raw.get("date", ""))
        raw = raw.get("text", "")
    try:
        marked: Marked = parse_item(str(raw))
    except MarkerError as exc:
        problems.append(f"{where}: {exc}")
        return Item(Marker(), str(raw), date)
    return Item(marked.marker, marked.text, date)


def _load_section(path: Path, problems: list[str]) -> Section | None:
    data = _read_yaml(path, problems)
    if not data:
        return None

    name = path.stem
    title = str(data.get("title", name.title()))
    kind = data.get("type")
    if kind not in BLOCK_TYPES:
        problems.append(
            f"{path.name}: unknown type {kind!r} (valid: {', '.join(BLOCK_TYPES)})"
        )
        return None

    items: list[object] = []

    if kind == "labels":
        for index, raw in enumerate(data.get("items") or []):
            if not isinstance(raw, dict) or "label" not in raw or "text" not in raw:
                problems.append(f"{path.name}: item {index} needs both 'label' and 'text'")
                continue
            marked = _item(raw["text"], f"{path.name}: item {index}", problems)
            items.append(Label(marked.marker, str(raw["label"]), marked.text))

    elif kind == "entries":
        for index, raw in enumerate(data.get("entries") or []):
            where = f"{path.name}: entry {index}"
            if not isinstance(raw, dict):
                problems.append(f"{where}: expected a mapping")
                continue
            missing = [f for f in ENTRY_FIELDS if not raw.get(f)]
            if missing:
                for field in missing:
                    problems.append(f"{where}: missing required field {field!r}")
                continue
            try:
                marker = parse_mark(raw.get("mark"))
            except MarkerError as exc:
                problems.append(f"{where}: {exc}")
                marker = Marker()
            bullets = tuple(
                _item(b, f"{where}, bullet {i}", problems)
                for i, b in enumerate(raw.get("bullets") or [])
            )
            items.append(
                Entry(
                    marker,
                    str(raw["org"]),
                    str(raw["location"]),
                    str(raw["dates"]),
                    str(raw["role"]),
                    bullets,
                )
            )

    else:  # "rows" and "prose" are both lists of flat items.
        for index, raw in enumerate(data.get("items") or []):
            items.append(_item(raw, f"{path.name}: item {index}", problems))

    return Section(name, title, kind, tuple(items))


def _load_profile(path: Path, problems: list[str]) -> Profile:
    data = _read_yaml(path, problems)
    name = str(data.get("name", ""))
    if not name:
        problems.append(f"{path.name}: missing required field 'name'")

    raw_tagline = data.get("tagline", "")
    raw_taglines = raw_tagline if isinstance(raw_tagline, list) else [raw_tagline]
    taglines = tuple(
        _item(t, f"{path.name}: tagline {i}", problems) for i, t in enumerate(raw_taglines)
    )
    contact = tuple(str(c) for c in (data.get("contact") or []))
    return Profile(name, contact, taglines)


def _load_documents(path: Path, problems: list[str]) -> dict[str, dict[str, tuple[str, ...]]]:
    data = _read_yaml(path, problems)
    documents: dict[str, dict[str, tuple[str, ...]]] = {}

    for length in LENGTHS:
        spec = data.get(length)
        if not spec:
            continue
        default = tuple(str(s) for s in (spec.get("sections") or []))
        if not default:
            problems.append(f"{path.name}: {length} has no 'sections' list")
        variants = spec.get("variants") or {}
        resolved: dict[str, tuple[str, ...]] = {}
        for variant, override in variants.items():
            override = override or {}
            sections = override.get("sections")
            resolved[str(variant)] = tuple(str(s) for s in sections) if sections else default
        if resolved:
            documents[length] = resolved

    if not documents:
        problems.append(f"{path.name}: declares no documents (expected 'long' and/or 'short')")
    return documents


def _markers(config_sections: dict[str, Section], profile: Profile):
    """Yield (marker, where) for every marker in the content."""
    for item in profile.taglines:
        yield item.marker, "profile.yml"
    for section in config_sections.values():
        where = f"{section.name}.yml"
        for index, item in enumerate(section.items):
            yield item.marker, f"{where}: item {index}"
            for bullet_index, bullet in enumerate(getattr(item, "bullets", ())):
                yield bullet.marker, f"{where}: item {index}, bullet {bullet_index}"


def load(root: Path) -> Config:
    """Load every content file, or raise ValidationError listing all problems."""
    problems: list[str] = []

    documents = _load_documents(root / "variants.yml", problems)
    profile = _load_profile(root / "content" / "profile.yml", problems)

    sections: dict[str, Section] = {}
    for path in sorted((root / "content").glob("*.yml")):
        if path.stem == "profile":
            continue
        section = _load_section(path, problems)
        if section is not None:
            sections[section.name] = section

    available = ", ".join(sorted(sections)) or "none"
    for length, variants in documents.items():
        for variant, order in variants.items():
            for name in order:
                if name not in sections:
                    problems.append(
                        f"variants.yml: {length}/{variant} lists section {name!r}, "
                        f"which has no content file (available: {available})"
                    )

    declared = {v for variants in documents.values() for v in variants} | {GENERAL}
    for marker, where in _markers(sections, profile):
        for target in marker.only:
            if target not in declared:
                problems.append(
                    f"{where}: targets undeclared variant {target!r} "
                    f"(declared: {', '.join(sorted(declared))})"
                )

    if problems:
        raise ValidationError(problems)
    return Config(profile, sections, documents)
