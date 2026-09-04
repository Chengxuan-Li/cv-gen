"""Load and validate the content files.

This module owns every load-time diagnostic. Validation runs to completion and
collects all problems so one run surfaces every issue; each carries the file, a
source line, a path into the document, and a stable `code` (see
`diagnostics.CODES`) alongside its prose message.

What may appear in a content file is declared in `spec.py`, not encoded in the
branches here. To add a field or a block type, edit that table.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .diagnostics import Problem, Source, line_index
from .marker import Marked, Marker, MarkerError, parse_item, parse_mark
from .spec import (
    BLOCK_TYPES,
    BLOCKS,
    FLAT,
    GENERAL,
    LENGTHS,
    MARK,
    MARKED,
    MARKED_LIST,
    BlockSpec,
)

ENTRY_FIELDS = BLOCKS["entries"].required_fields

# Untracked per-machine overrides. Excluded from section discovery so that
# content/profile.local.yml never becomes a section named "profile.local".
LOCAL_SUFFIX = ".local.yml"

MARKER_HINT = (
    "a marker is '+' or '-' followed by a space, optionally with [variants]; "
    "'+text' with no space is literal text, not a marker"
)


def local_profile_path(profile_path: Path) -> Path:
    """content/profile.yml -> content/profile.local.yml"""
    return profile_path.with_name(profile_path.stem + LOCAL_SUFFIX)


class ValidationError(Exception):
    """One or more content files are invalid."""

    def __init__(self, problems: list[Problem]) -> None:
        self.problems = list(problems)
        super().__init__("\n".join(f"  - {p}" for p in self.problems))

    def as_dict(self) -> dict:
        return {"ok": False, "problems": [p.as_dict() for p in self.problems]}


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
    has_local_override: bool = False


@dataclass(frozen=True)
class Config:
    profile: Profile
    sections: dict[str, Section]
    documents: dict[str, dict[str, tuple[str, ...]]]

    def all_documents(self) -> list[tuple[str, str]]:
        return [(length, v) for length, variants in self.documents.items() for v in variants]

    def declared_variants(self) -> set[str]:
        return {v for variants in self.documents.values() for v in variants}


@dataclass(frozen=True)
class MarkerSite:
    """Where a marker was written, so a bad variant name can be pointed at."""

    marker: Marker
    source: Source
    path: tuple
    where: str


def _read(path: Path, problems: list[Problem]) -> Source:
    """Read one YAML file into a Source, reporting anything that stops it."""
    blank = Source(path, {}, {})
    if not path.exists():
        problems.append(blank.problem("file_not_found", f"file not found at {path}"))
        return blank

    text = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        problems.append(blank.problem("invalid_yaml", f"invalid YAML - {exc}"))
        return blank

    if data is None:
        problems.append(blank.problem("empty_file", "empty file"))
        return blank
    if not isinstance(data, dict):
        problems.append(
            blank.problem("not_a_mapping", f"expected a mapping, got {type(data).__name__}")
        )
        return blank
    return Source(path, data, line_index(text))


def _marked(
    raw: object,
    source: Source,
    path: tuple,
    where: str,
    problems: list[Problem],
    sites: list[MarkerSite],
) -> Marked:
    """Parse one marked string, recording its marker site."""
    try:
        marked = parse_item(str(raw))
    except MarkerError as exc:
        problems.append(
            source.problem("malformed_marker", f"{where}: {exc}", path, hint=MARKER_HINT)
        )
        marked = Marked(Marker(), str(raw))
    sites.append(MarkerSite(marked.marker, source, path, where))
    return marked


def _item_noun(block: BlockSpec) -> str:
    return "entry" if block.items_key == "entries" else "item"


def _load_section(
    path: Path, problems: list[Problem], sites: list[MarkerSite]
) -> Section | None:
    source = _read(path, problems)
    if not source.data:
        return None

    name = path.stem
    title = str(source.data.get("title", name.title()))
    kind = source.data.get("type")
    block = BLOCKS.get(kind) if isinstance(kind, str) else None
    if block is None:
        problems.append(
            source.problem(
                "unknown_block_type",
                f"unknown type {kind!r} (valid: {', '.join(BLOCK_TYPES)})",
                ("type",),
                field="type",
                hint=f"one of: {', '.join(BLOCK_TYPES)}",
            )
        )
        return None

    noun = _item_noun(block)
    items: list[object] = []

    for index, raw in enumerate(source.data.get(block.items_key) or []):
        path_at = (block.items_key, index)
        where = f"{noun} {index}"

        if isinstance(raw, str) and block.item_form == FLAT:
            raw = {block.text_field: raw}
        if not isinstance(raw, dict):
            problems.append(
                source.problem("item_not_a_mapping", f"{where}: expected a mapping", path_at)
            )
            continue

        missing = [f for f in block.required_fields if not raw.get(f)]
        if missing:
            for field in missing:
                problems.append(
                    source.problem(
                        "missing_required_field",
                        f"{where}: missing required field {field!r}",
                        path_at,
                        field=field,
                        hint=f"{block.type} requires: {', '.join(block.required_fields)}",
                    )
                )
            continue

        values: dict[str, object] = {}
        for spec in block.fields:
            raw_value = raw.get(spec.name)
            if spec.kind == MARKED:
                marked = _marked(
                    raw_value, source, path_at + (spec.name,), where, problems, sites
                )
                values[spec.name] = marked.text
                values["__marker__"] = marked.marker
            elif spec.kind == MARK:
                try:
                    marker = parse_mark(raw_value)
                except MarkerError as exc:
                    problems.append(
                        source.problem(
                            "malformed_marker",
                            f"{where}: {exc}",
                            path_at + (spec.name,),
                            field=spec.name,
                            hint=MARKER_HINT,
                        )
                    )
                    marker = Marker()
                sites.append(MarkerSite(marker, source, path_at, where))
                values["__marker__"] = marker
            elif spec.kind == MARKED_LIST:
                bullets = []
                for i, bullet in enumerate(raw_value or []):
                    marked = _marked(
                        bullet,
                        source,
                        path_at + (spec.name, i),
                        f"{where}, bullet {i}",
                        problems,
                        sites,
                    )
                    bullets.append(Item(marked.marker, marked.text))
                values[spec.name] = tuple(bullets)
            else:
                values[spec.name] = str(raw_value) if raw_value is not None else ""

        items.append(_build_item(block, values))

    return Section(name, title, block.type, tuple(items))


def _build_item(block: BlockSpec, values: dict) -> object:
    """Turn validated field values into the block's content object."""
    marker = values.get("__marker__", Marker())
    if block.type == "labels":
        return Label(marker, values["label"], values["text"])
    if block.type == "entries":
        return Entry(
            marker,
            values["org"],
            values["location"],
            values["dates"],
            values["role"],
            values.get("bullets", ()),
        )
    return Item(marker, values["text"], values.get("date", ""))


def _load_profile(
    path: Path, problems: list[Problem], sites: list[MarkerSite]
) -> Profile:
    """Load profile.yml, letting an untracked profile.local.yml override it.

    The tracked file carries deliberately fake contact details; real ones live in
    the sibling `.local` file, which is gitignored. The merge is a shallow
    top-level key replacement - a `contact:` in the override swaps the whole
    list, since element-wise merging of a list has no unambiguous meaning.
    """
    source = _read(path, problems)
    data = dict(source.data)
    origin = {key: source for key in data}

    local_path = local_profile_path(path)
    has_local_override = local_path.exists()
    if has_local_override:
        local = _read(local_path, problems)
        data.update(local.data)
        origin.update({key: local for key in local.data})

    def where(key: str) -> Source:
        """The file a key actually came from, so errors point at the right one."""
        return origin.get(key, source)

    name = str(data.get("name", ""))
    if not name:
        problems.append(
            where("name").problem(
                "missing_required_field", "missing required field 'name'", ("name",), field="name"
            )
        )

    raw_tagline = data.get("tagline", "")
    raw_taglines = raw_tagline if isinstance(raw_tagline, list) else [raw_tagline]
    tagline_source = where("tagline")
    taglines = tuple(
        Item(
            m.marker,
            m.text,
        )
        for m in (
            _marked(
                t,
                tagline_source,
                ("tagline", i) if isinstance(raw_tagline, list) else ("tagline",),
                f"tagline {i}",
                problems,
                sites,
            )
            for i, t in enumerate(raw_taglines)
        )
    )

    raw_contact = data.get("contact") or []
    if not isinstance(raw_contact, list):
        problems.append(
            where("contact").problem(
                "invalid_field_type",
                f"'contact' must be a list of lines, got {type(raw_contact).__name__}",
                ("contact",),
                field="contact",
                hint="one string per line, e.g. - \"Email: [a@b.c](mailto:a@b.c)\"",
            )
        )
        raw_contact = []
    contact = tuple(str(c) for c in raw_contact)
    return Profile(name, contact, taglines, has_local_override)


def _load_documents(
    path: Path, problems: list[Problem]
) -> dict[str, dict[str, tuple[str, ...]]]:
    source = _read(path, problems)
    documents: dict[str, dict[str, tuple[str, ...]]] = {}

    for length in LENGTHS:
        spec = source.data.get(length)
        if not spec:
            continue
        if not isinstance(spec, dict):
            problems.append(
                source.problem(
                    "invalid_field_type",
                    f"{length} must be a mapping with a 'sections' list, "
                    f"got {type(spec).__name__}",
                    (length,),
                    field=length,
                )
            )
            continue
        default = tuple(str(s) for s in (spec.get("sections") or []))
        if not default:
            problems.append(
                source.problem(
                    "no_sections_listed",
                    f"{length} has no 'sections' list",
                    (length,),
                    field="sections",
                )
            )
        variants = spec.get("variants") or {}
        resolved: dict[str, tuple[str, ...]] = {}
        for variant, override in variants.items():
            override = override or {}
            sections = override.get("sections")
            resolved[str(variant)] = tuple(str(s) for s in sections) if sections else default
        if resolved:
            documents[length] = resolved

    if not documents:
        problems.append(
            source.problem(
                "no_documents_declared",
                "declares no documents (expected 'long' and/or 'short')",
            )
        )
    return documents


def load(root: Path) -> Config:
    """Load every content file, or raise ValidationError listing all problems."""
    problems: list[Problem] = []
    sites: list[MarkerSite] = []

    variants_path = root / "variants.yml"
    documents = _load_documents(variants_path, problems)
    profile = _load_profile(root / "content" / "profile.yml", problems, sites)

    sections: dict[str, Section] = {}
    for path in sorted((root / "content").glob("*.yml")):
        if path.stem == "profile" or path.name.endswith(LOCAL_SUFFIX):
            continue
        section = _load_section(path, problems, sites)
        if section is not None:
            sections[section.name] = section

    available = ", ".join(sorted(sections)) or "none"
    variants_source = Source(variants_path, {}, {})
    for length, variants in documents.items():
        for variant, order in variants.items():
            for name in order:
                if name not in sections:
                    problems.append(
                        variants_source.problem(
                            "missing_section_file",
                            f"{length}/{variant} lists section {name!r}, "
                            f"which has no content file (available: {available})",
                            (length, "sections"),
                            field=name,
                            hint=f"create content/{name}.yml, or remove it from variants.yml",
                        )
                    )

    config = Config(profile, sections, documents)
    declared = config.declared_variants() | {GENERAL}
    for site in sites:
        for target in site.marker.only:
            if target not in declared:
                problems.append(
                    site.source.problem(
                        "undeclared_variant",
                        f"{site.where}: targets undeclared variant {target!r} "
                        f"(declared: {', '.join(sorted(declared))})",
                        site.path,
                        field=target,
                        hint="declare it under a length in variants.yml, or fix the spelling",
                    )
                )

    if problems:
        raise ValidationError(problems)
    return config
