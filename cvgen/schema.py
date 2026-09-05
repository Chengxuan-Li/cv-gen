"""Load and validate the content files.

This module owns every load-time diagnostic. Validation runs to completion and
collects all problems so one run surfaces every issue; each carries the file, a
source line, a path into the document, and a stable `code` (see
`diagnostics.CODES`) alongside its prose message.

What may appear in a content file is declared in `spec.py`, not encoded in the
branches here. To add a field or a block type, edit that table.

Every translatable value is loaded as an `LStr` (see `localize.py`): a plain
string is the English source serving every language, and a language-keyed map
supplies translations. Consumers see the English text through the ordinary str
interface; only the emitter asks an LStr for another language.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .diagnostics import Problem, Source, line_index
from .localize import (
    SOURCE_LANG,
    LanguageSpec,
    LStr,
    default_languages,
    is_lang_map,
    language_spec,
)
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
# content/profile.local.yaml never becomes a section named "profile.local".
LOCAL_SUFFIX = ".local.yaml"

MARKER_HINT = (
    "a marker is '+' or '-' followed by a space, optionally with [variants]; "
    "'+text' with no space is literal text, not a marker"
)


def local_profile_path(profile_path: Path) -> Path:
    """content/profile.yaml -> content/profile.local.yaml"""
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
    anticipated_graduation: str = ""


@dataclass(frozen=True)
class Config:
    profile: Profile
    sections: dict[str, Section]
    documents: dict[str, dict[str, tuple[str, ...]]]
    languages: dict[str, LanguageSpec] = field(default_factory=default_languages)

    def all_documents(self) -> list[tuple[str, str]]:
        return [(length, v) for length, variants in self.documents.items() for v in variants]

    def all_renders(self) -> list[tuple[str, str, str]]:
        """Every (length, variant, lang) that builds to a PDF."""
        return [(l, v, lang) for l, v in self.all_documents() for lang in self.languages]

    def declared_variants(self) -> set[str]:
        return {v for variants in self.documents.values() for v in variants}


@dataclass(frozen=True)
class MarkerSite:
    """Where a marker was written, so a bad variant name can be pointed at."""

    marker: Marker
    source: Source
    path: tuple
    where: str


@dataclass(frozen=True)
class TextSite:
    """Where a translatable string was written, so lint can report on it."""

    text: LStr
    source: Source
    path: tuple
    where: str


@dataclass
class _Ctx:
    """Everything the loader accumulates while walking the files."""

    languages: dict[str, LanguageSpec]
    problems: list[Problem] = field(default_factory=list)
    sites: list[MarkerSite] = field(default_factory=list)
    texts: list[TextSite] = field(default_factory=list)


@dataclass(frozen=True)
class Loaded:
    config: Config
    texts: tuple[TextSite, ...]


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


def _text(raw: object, source: Source, path: tuple, where: str, ctx: _Ctx) -> LStr:
    """Load one translatable value: a plain string or a language-keyed map."""
    if not is_lang_map(raw):
        result = LStr("" if raw is None else str(raw))
        ctx.texts.append(TextSite(result, source, path, where))
        return result

    assert isinstance(raw, dict)
    for lang in raw:
        if lang not in ctx.languages:
            ctx.problems.append(
                source.problem(
                    "undeclared_language",
                    f"{where}: language {lang!r} is not declared in variants.yaml "
                    f"(declared: {', '.join(sorted(ctx.languages))})",
                    path + (lang,),
                    field=lang,
                    hint="add it under `languages:` in variants.yaml, or fix the spelling",
                )
            )
    if SOURCE_LANG not in raw:
        ctx.problems.append(
            source.problem(
                "missing_source_language",
                f"{where}: a translated value needs an {SOURCE_LANG!r} entry - "
                f"it is the source every other language falls back to",
                path,
                field=SOURCE_LANG,
            )
        )
    src = str(raw.get(SOURCE_LANG, next(iter(raw.values()))))
    translations = {
        lang: str(value)
        for lang, value in raw.items()
        if lang != SOURCE_LANG and lang in ctx.languages
    }
    result = LStr(src, translations)
    ctx.texts.append(TextSite(result, source, path, where))
    return result


def _marked(raw: object, source: Source, path: tuple, where: str, ctx: _Ctx) -> Marked:
    """Parse one marked string, recording its marker site.

    The marker is parsed from the source language only. Translations decide how
    an item reads, never whether it is included, so they carry no marker; lint
    reports one that does.
    """
    text = _text(raw, source, path, where, ctx)
    try:
        marked = parse_item(str(text))
    except MarkerError as exc:
        ctx.problems.append(
            source.problem("malformed_marker", f"{where}: {exc}", path, hint=MARKER_HINT)
        )
        marked = Marked(Marker(), str(text))
    ctx.sites.append(MarkerSite(marked.marker, source, path, where))
    return Marked(marked.marker, LStr(marked.text, text.translations))


def _item_noun(block: BlockSpec) -> str:
    return "entry" if block.items_key == "entries" else "item"


def _load_section(path: Path, ctx: _Ctx) -> Section | None:
    source = _read(path, ctx.problems)
    if not source.data:
        return None

    name = path.stem
    title = _text(source.data.get("title", name.title()), source, ("title",), "title", ctx)
    kind = source.data.get("type")
    block = BLOCKS.get(kind) if isinstance(kind, str) else None
    if block is None:
        ctx.problems.append(
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

        # A bare string, or a language map standing in for one, is shorthand for
        # the item's text field. A mapping with any non-language key is the item.
        if block.item_form == FLAT and (isinstance(raw, str) or is_lang_map(raw)):
            raw = {block.text_field: raw}
        if not isinstance(raw, dict):
            ctx.problems.append(
                source.problem("item_not_a_mapping", f"{where}: expected a mapping", path_at)
            )
            continue

        missing = [f for f in block.required_fields if not raw.get(f)]
        if missing:
            for missing_field in missing:
                ctx.problems.append(
                    source.problem(
                        "missing_required_field",
                        f"{where}: missing required field {missing_field!r}",
                        path_at,
                        field=missing_field,
                        hint=f"{block.type} requires: {', '.join(block.required_fields)}",
                    )
                )
            continue

        values: dict[str, object] = {}
        for spec in block.fields:
            raw_value = raw.get(spec.name)
            field_path = path_at + (spec.name,)
            if spec.kind == MARKED:
                marked = _marked(raw_value, source, field_path, where, ctx)
                values[spec.name] = marked.text
                values["__marker__"] = marked.marker
            elif spec.kind == MARK:
                try:
                    marker = parse_mark(raw_value)
                except MarkerError as exc:
                    ctx.problems.append(
                        source.problem(
                            "malformed_marker",
                            f"{where}: {exc}",
                            field_path,
                            field=spec.name,
                            hint=MARKER_HINT,
                        )
                    )
                    marker = Marker()
                ctx.sites.append(MarkerSite(marker, source, path_at, where))
                values["__marker__"] = marker
            elif spec.kind == MARKED_LIST:
                bullets = []
                for i, bullet in enumerate(raw_value or []):
                    marked = _marked(
                        bullet, source, field_path + (i,), f"{where}, bullet {i}", ctx
                    )
                    bullets.append(Item(marked.marker, marked.text))
                values[spec.name] = tuple(bullets)
            elif spec.translatable:
                values[spec.name] = _text(raw_value, source, field_path, where, ctx)
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


def _load_profile(path: Path, ctx: _Ctx) -> Profile:
    """Load profile.yaml, letting an untracked profile.local.yaml override it.

    The tracked file carries deliberately fake contact details; real ones live in
    the sibling `.local` file, which is gitignored. The merge is a shallow
    top-level key replacement - a `contact:` in the override swaps the whole
    list, since element-wise merging of a list has no unambiguous meaning.
    """
    source = _read(path, ctx.problems)
    data = dict(source.data)
    origin = {key: source for key in data}

    local_path = local_profile_path(path)
    has_local_override = local_path.exists()
    if has_local_override:
        local = _read(local_path, ctx.problems)
        data.update(local.data)
        origin.update({key: local for key in local.data})

    def where(key: str) -> Source:
        """The file a key actually came from, so errors point at the right one."""
        return origin.get(key, source)

    name = _text(data.get("name", ""), where("name"), ("name",), "name", ctx)
    if not name:
        ctx.problems.append(
            where("name").problem(
                "missing_required_field", "missing required field 'name'", ("name",), field="name"
            )
        )

    raw_tagline = data.get("tagline", "")
    raw_taglines = raw_tagline if isinstance(raw_tagline, list) else [raw_tagline]
    tagline_source = where("tagline")
    taglines = []
    for i, t in enumerate(raw_taglines):
        path = ("tagline", i) if isinstance(raw_tagline, list) else ("tagline",)
        m = _marked(t, tagline_source, path, f"tagline {i}", ctx)
        taglines.append(Item(m.marker, m.text))

    raw_contact = data.get("contact") or []
    if not isinstance(raw_contact, list):
        ctx.problems.append(
            where("contact").problem(
                "invalid_field_type",
                f"'contact' must be a list of lines, got {type(raw_contact).__name__}",
                ("contact",),
                field="contact",
                hint="one string per line, e.g. - \"Email: [a@b.c](mailto:a@b.c)\"",
            )
        )
        raw_contact = []
    contact = tuple(
        _text(c, where("contact"), ("contact", i), f"contact {i}", ctx)
        for i, c in enumerate(raw_contact)
    )
    graduation = _text(
        data.get("anticipated_graduation", ""),
        where("anticipated_graduation"),
        ("anticipated_graduation",),
        "anticipated_graduation",
        ctx,
    )
    return Profile(name, contact, tuple(taglines), has_local_override, graduation)


def _load_documents(source: Source, problems: list[Problem]) -> dict[str, dict[str, tuple[str, ...]]]:
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


def _load_languages(source: Source, problems: list[Problem]) -> dict[str, LanguageSpec]:
    """Read `languages:` from variants.yaml; English alone when absent."""
    raw = source.data.get("languages")
    if raw is None:
        return default_languages()
    if not isinstance(raw, dict) or not raw:
        problems.append(
            source.problem(
                "invalid_field_type",
                "languages must be a mapping of code to {typst, font}",
                ("languages",),
                field="languages",
                hint="e.g. languages: {en: {typst: en, font: Garamond}}",
            )
        )
        return default_languages()

    languages: dict[str, LanguageSpec] = {}
    for code, spec in raw.items():
        code = str(code)
        if spec is not None and not isinstance(spec, dict):
            problems.append(
                source.problem(
                    "invalid_field_type",
                    f"languages.{code} must be a mapping, got {type(spec).__name__}",
                    ("languages", code),
                    field=code,
                )
            )
            spec = None
        languages[code] = language_spec(code, spec)

    if SOURCE_LANG not in languages:
        problems.append(
            source.problem(
                "missing_source_language",
                f"languages must include {SOURCE_LANG!r}, the source every "
                f"translation falls back to",
                ("languages",),
                field=SOURCE_LANG,
            )
        )
        languages = {**default_languages(), **languages}
    return languages


def _legacy_extensions(root: Path) -> list[Problem]:
    """Report `.yml` files that the loader will not see.

    This project standardises on `.yaml`, which the YAML spec recommends. Since
    discovery globs `*.yaml` only, a stray `.yml` would otherwise be ignored in
    silence - the section would simply vanish from the CV, surfacing later as a
    confusing 'no content file' error against variants.yaml. Naming it here turns
    that into an obvious one-line fix.
    """
    stray = sorted((root / "content").glob("*.yml")) + sorted(root.glob("variants.yml"))
    return [
        Problem(
            file=path.name,
            code="legacy_yml_extension",
            message=(
                f"{path.name}: this project uses '.yaml', so this file is ignored "
                f"by the loader"
            ),
            path=str(path.relative_to(root).as_posix()),
            hint=f"rename it to {path.with_suffix('.yaml').name}",
        )
        for path in stray
    ]


def load_all(root: Path) -> Loaded:
    """Load every content file, or raise ValidationError listing all problems.

    Returns the Config together with every translatable string's location, which
    lint uses to report translation coverage without re-deriving the loader's
    rules.
    """
    problems: list[Problem] = []
    variants_source = _read(root / "variants.yaml", problems)
    documents = _load_documents(variants_source, problems)
    ctx = _Ctx(languages=_load_languages(variants_source, problems), problems=problems)

    profile = _load_profile(root / "content" / "profile.yaml", ctx)

    sections: dict[str, Section] = {}
    for path in sorted((root / "content").glob("*.yaml")):
        if path.stem == "profile" or path.name.endswith(LOCAL_SUFFIX):
            continue
        section = _load_section(path, ctx)
        if section is not None:
            sections[section.name] = section

    problems += _legacy_extensions(root)

    available = ", ".join(sorted(sections)) or "none"
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
                            hint=f"create content/{name}.yaml, or remove it from variants.yaml",
                        )
                    )

    config = Config(profile, sections, documents, ctx.languages)
    declared = config.declared_variants() | {GENERAL}
    for site in ctx.sites:
        for target in site.marker.only:
            if target not in declared:
                problems.append(
                    site.source.problem(
                        "undeclared_variant",
                        f"{site.where}: targets undeclared variant {target!r} "
                        f"(declared: {', '.join(sorted(declared))})",
                        site.path,
                        field=target,
                        hint="declare it under a length in variants.yaml, or fix the spelling",
                    )
                )

    if problems:
        raise ValidationError(problems)
    return Loaded(config, tuple(ctx.texts))


def load(root: Path) -> Config:
    """Load every content file, or raise ValidationError listing all problems."""
    return load_all(root).config
