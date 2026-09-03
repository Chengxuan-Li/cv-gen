# cv-gen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a generator that turns `content/*.yml` into PDF CVs, one per declared (length, variant) document, rendered through Quarto's Typst engine.

**Architecture:** A pure-Python pipeline — `marker` parses the tier/variant token, `schema` loads and validates YAML, `select` applies two inclusion gates and orders sections, `emit` writes a `.qmd` of markdown and fenced divs. A Lua filter converts those divs into Typst function calls so markdown survives Pandoc; all styling lives in one `.typ` file. `build.py` wires it together and shells out to Quarto.

**Tech Stack:** Python 3.13.9 (verified), `pyyaml` 6.0.3, `pytest`, Quarto 1.10.18 bundling Typst 0.15.1 and Pandoc.

**Spec:** [docs/superpowers/specs/2026-09-03-cv-gen-design.md](../specs/2026-09-03-cv-gen-design.md)

## Global Constraints

Every task's requirements implicitly include these.

- **No Claude attribution in commits.** No `Co-Authored-By: Claude` trailer, no "Generated with Claude Code" footer, no model name anywhere in a commit message. See [AGENTS.md](../../../AGENTS.md).
- **`resources/` is never tracked and never read by the build.** It is private reference material for humans.
- **No LaTeX.** Render target is `format: typst` only. Never add `format: pdf`.
- **The marker's trailing-whitespace rule is load-bearing** and must not be relaxed. It is the sole reason the grammar does not collide with `[text](url)`.
- **`general` is an inherited base pool, not a sibling variant.** Inclusion is `general in only or variant in only`.
- **Validation reports all problems in one pass**, then exits non-zero having written no PDF. Never fail on the first error.
- **Every error message names the file and the item index.**
- All modules start with `from __future__ import annotations`.
- Quarto is at `C:\Program Files\Quarto\bin\quarto.exe` and may not be on `PATH` in every shell.

## File Structure

| File | Responsibility |
|---|---|
| `cvgen/__init__.py` | Package marker; exports nothing. |
| `cvgen/marker.py` | Marker token → `(tier, only, text)`. Pure; no I/O, no YAML. |
| `cvgen/schema.py` | Load and validate `variants.yml`, `profile.yml`, `content/*.yml`. Owns every load-time error message. |
| `cvgen/select.py` | The two inclusion gates; section ordering; empty-section dropping. Never formats. |
| `cvgen/emit.py` | `Document` → `.qmd` text. Never filters. |
| `build.py` | CLI, Quarto discovery and invocation. |
| `templates/cv.typ` | All styling. Injected via `include-in-header`. |
| `templates/cv.lua` | Fenced div → Typst call. The only bridge between content and style. |
| `variants.yml` | Which documents exist and their section order. |
| `content/*.yml` | Profile and one file per section. |
| `tests/test_*.py` | One test module per `cvgen` module, plus an end-to-end render test. |

---

### Task 1: Marker grammar

**Files:**
- Create: `cvgen/__init__.py`, `cvgen/marker.py`
- Test: `tests/test_marker.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - Constants `GENERAL = "general"`, `LONG = "long"`, `BOTH = "both"`
  - `class MarkerError(ValueError)`
  - `@dataclass(frozen=True) Marker(tier: str = BOTH, only: tuple[str, ...] = (GENERAL,))`
  - `@dataclass(frozen=True) Marked(marker: Marker, text: str)`
  - `DEFAULT: Marker`
  - `parse_item(raw: str) -> Marked`
  - `parse_mark(raw: str | None) -> Marker`

- [ ] **Step 1: Write the failing test**

Create `tests/test_marker.py`:

```python
import pytest

from cvgen.marker import BOTH, GENERAL, LONG, Marker, MarkerError, parse_item, parse_mark


@pytest.mark.parametrize(
    "raw, tier, only, text",
    [
        # Markers, in every shape.
        ("+[gev-pos-1] Research inverse modeling", LONG, ("gev-pos-1",), "Research inverse modeling"),
        ("+[a,b] Text", LONG, ("a", "b"), "Text"),
        ("+[ a , b ] Spaces in the list", LONG, ("a", "b"), "Spaces in the list"),
        ("+ Research inverse modeling", LONG, (GENERAL,), "Research inverse modeling"),
        ("- Shared bullet", BOTH, (GENERAL,), "Shared bullet"),
        ("-[a] Shared but targeted", BOTH, ("a",), "Shared but targeted"),
        # An empty list reaches nothing, per spec.
        ("+[] Reaches nothing", LONG, (), "Reaches nothing"),
        # No marker.
        ("Develop load profile inference methods.", BOTH, (GENERAL,), "Develop load profile inference methods."),
        # Markdown collisions. Each of these is a real construct that must survive.
        ("-[ShadingZip](https://x) is a tool", BOTH, (GENERAL,), "-[ShadingZip](https://x) is a tool"),
        ("[ShadingZip](https://x) is a tool", BOTH, (GENERAL,), "[ShadingZip](https://x) is a tool"),
        ("**Nemetschek Award** *Second place*", BOTH, (GENERAL,), "**Nemetschek Award** *Second place*"),
        ("-5% peak load reduction", BOTH, (GENERAL,), "-5% peak load reduction"),
        # Escapes for a literal leading '+ ' or '- '.
        ("\\+ Literal plus", BOTH, (GENERAL,), "+ Literal plus"),
        ("\\- Literal minus", BOTH, (GENERAL,), "- Literal minus"),
    ],
)
def test_parse_item(raw, tier, only, text):
    marked = parse_item(raw)
    assert marked.marker.tier == tier
    assert marked.marker.only == only
    assert marked.text == text


def test_parse_item_unclosed_bracket_raises():
    with pytest.raises(MarkerError) as excinfo:
        parse_item("+[gev-pos-1 Research inverse modeling")
    assert "unclosed" in str(excinfo.value).lower()


@pytest.mark.parametrize(
    "raw, tier, only",
    [
        (None, BOTH, (GENERAL,)),
        ("+", LONG, (GENERAL,)),
        ("-", BOTH, (GENERAL,)),
        ("+[gev-pos-1]", LONG, ("gev-pos-1",)),
        ("-[a,b]", BOTH, ("a", "b")),
    ],
)
def test_parse_mark(raw, tier, only):
    marker = parse_mark(raw)
    assert marker.tier == tier
    assert marker.only == only


@pytest.mark.parametrize("raw", ["+[a] extra text", "gev-pos-1", "+[a", ""])
def test_parse_mark_rejects_malformed(raw):
    with pytest.raises(MarkerError):
        parse_mark(raw)


def test_marker_is_hashable():
    assert Marker() == Marker()
    assert len({Marker(), Marker()}) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_marker.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'cvgen'`

- [ ] **Step 3: Write the implementation**

Create `cvgen/__init__.py` as an empty file.

Create `cvgen/marker.py`:

```python
"""Parse the marker token that prefixes a content item.

    marker := ('+' | '-') ( '[' names ']' )?     must be followed by whitespace

The trailing-whitespace requirement is what keeps this grammar from colliding
with markdown. A markdown link's ']' is always followed by '(', never a space,
so '-[ShadingZip](url) is a tool' is plain text and needs no escaping.

Do not relax that rule. Doing so silently corrupts any item beginning with a
link.
"""

from __future__ import annotations

from dataclasses import dataclass

GENERAL = "general"
LONG = "long"
BOTH = "both"

_TIERS = {"+": LONG, "-": BOTH}


class MarkerError(ValueError):
    """A marker token is malformed."""


@dataclass(frozen=True)
class Marker:
    tier: str = BOTH
    only: tuple[str, ...] = (GENERAL,)


@dataclass(frozen=True)
class Marked:
    marker: Marker
    text: str


DEFAULT = Marker()


def _names(raw: str) -> tuple[str, ...]:
    return tuple(name.strip() for name in raw.split(",") if name.strip())


def parse_item(raw: str) -> Marked:
    """Split a content string into its marker and its text."""
    if raw[:2] in ("\\+", "\\-"):
        return Marked(DEFAULT, raw[1:])

    tier = _TIERS.get(raw[:1])
    if tier is None:
        return Marked(DEFAULT, raw)

    rest = raw[1:]

    if rest.startswith("["):
        close = rest.find("]")
        if close == -1:
            raise MarkerError(f"unclosed '[' in marker: {raw!r}")
        after = rest[close + 1 :]
        if not after[:1].isspace():
            # ']' is followed by '(' or similar: a markdown link, not a marker.
            return Marked(DEFAULT, raw)
        return Marked(Marker(tier, _names(rest[1:close])), after.strip())

    if rest[:1].isspace():
        return Marked(Marker(tier, (GENERAL,)), rest.strip())

    # '-5%' and friends: a sign, not a marker.
    return Marked(DEFAULT, raw)


def parse_mark(raw: str | None) -> Marker:
    """Parse a bare `mark:` field, which carries a marker and no text."""
    if raw is None:
        return DEFAULT

    text = raw.strip()
    tier = _TIERS.get(text[:1])
    if tier is None:
        raise MarkerError(f"mark must start with '+' or '-': {raw!r}")

    rest = text[1:]
    if not rest:
        return Marker(tier, (GENERAL,))
    if not (rest.startswith("[") and rest.endswith("]")):
        raise MarkerError(f"mark must be '+', '-' or '+[names]': {raw!r}")
    return Marker(tier, _names(rest[1:-1]))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_marker.py -q`
Expected: PASS — 24 passed

- [ ] **Step 5: Commit**

```bash
git add cvgen/__init__.py cvgen/marker.py tests/test_marker.py
git commit -m "Add marker grammar parser

The trailing-whitespace rule is what keeps the grammar from colliding with
markdown links, so every collision case in the spec is a test case."
```

---

### Task 2: Schema loading and validation

**Files:**
- Create: `cvgen/schema.py`
- Test: `tests/test_schema.py`

**Interfaces:**
- Consumes: `cvgen.marker` — `GENERAL`, `Marker`, `MarkerError`, `parse_item`, `parse_mark`.
- Produces:
  - `BLOCK_TYPES = ("labels", "entries", "rows", "prose")`, `LENGTHS = ("long", "short")`
  - `class ValidationError(Exception)` with a `.problems: list[str]` attribute
  - Frozen dataclasses `Item(marker, text, date="")`, `Label(marker, label, text)`, `Entry(marker, org, location, dates, role, bullets: tuple[Item, ...])`, `Section(name, title, type, items: tuple[object, ...])`, `Profile(name, contact: tuple[str, ...], taglines: tuple[Item, ...])`
  - `@dataclass(frozen=True) Config(profile: Profile, sections: dict[str, Section], documents: dict[str, dict[str, tuple[str, ...]]])` where `documents[length][variant]` is the **resolved** section order
  - `Config.all_documents() -> list[tuple[str, str]]` returning `(length, variant)` pairs
  - `Config.declared_variants() -> set[str]`
  - `load(root: Path) -> Config`

- [ ] **Step 1: Write the failing test**

Create `tests/test_schema.py`:

```python
from pathlib import Path

import pytest

from cvgen.schema import ValidationError, load

VARIANTS = """
long:
  sections: [skills, experience]
  variants:
    general: {}
    gev-pos-1: {sections: [experience, skills]}
short:
  sections: [experience]
  variants:
    general: {}
    google-pos-1: {}
"""

PROFILE = """
name: Chengxuan Li
contact:
  - "Email: [x@y.edu](mailto:x@y.edu)"
tagline:
  - -[gev-pos-1] Targeted headline
  - Default headline
"""

SKILLS = """
title: Technical Skills
type: labels
items:
  - label: Programming
    text: Python, C#
"""

EXPERIENCE = """
title: Experience
type: entries
entries:
  - org: EnergyAtlas.io
    location: Ithaca NY
    dates: Jan 2025 - Current
    role: Lead Developer
    mark: "-[gev-pos-1]"
    bullets:
      - Lead development of a digital twin.
      - +[gev-pos-1] Build scalable pipelines.
"""


def write_repo(root: Path, **overrides: str) -> Path:
    files = {
        "variants.yml": VARIANTS,
        "content/profile.yml": PROFILE,
        "content/skills.yml": SKILLS,
        "content/experience.yml": EXPERIENCE,
    }
    files.update(overrides)
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def test_load_resolves_documents(tmp_path):
    config = load(write_repo(tmp_path))
    assert sorted(config.all_documents()) == [
        ("long", "gev-pos-1"),
        ("long", "general"),
        ("short", "general"),
        ("short", "google-pos-1"),
    ]


def test_variant_override_replaces_section_order(tmp_path):
    config = load(write_repo(tmp_path))
    assert config.documents["long"]["general"] == ("skills", "experience")
    assert config.documents["long"]["gev-pos-1"] == ("experience", "skills")


def test_declared_variants(tmp_path):
    config = load(write_repo(tmp_path))
    assert config.declared_variants() == {"general", "gev-pos-1", "google-pos-1"}


def test_entry_and_bullet_markers_are_parsed(tmp_path):
    config = load(write_repo(tmp_path))
    entry = config.sections["experience"].items[0]
    assert entry.marker.only == ("gev-pos-1",)
    assert entry.marker.tier == "both"
    assert entry.bullets[1].marker.tier == "long"
    assert entry.bullets[1].text == "Build scalable pipelines."


def test_taglines_keep_order(tmp_path):
    config = load(write_repo(tmp_path))
    assert [t.text for t in config.profile.taglines] == ["Targeted headline", "Default headline"]


def test_undeclared_variant_is_an_error(tmp_path):
    bad = EXPERIENCE.replace("+[gev-pos-1]", "+[gev-pos-9]")
    with pytest.raises(ValidationError) as excinfo:
        load(write_repo(tmp_path, **{"content/experience.yml": bad}))
    message = str(excinfo.value)
    assert "gev-pos-9" in message
    assert "experience.yml" in message
    assert "gev-pos-1" in message  # lists what IS declared


def test_variant_declared_under_other_length_is_not_an_error(tmp_path):
    # google-pos-1 exists only under `short`; targeting it from a `+` item is a
    # deliberate no-op, not a typo.
    ok = EXPERIENCE.replace("+[gev-pos-1]", "+[google-pos-1]")
    load(write_repo(tmp_path, **{"content/experience.yml": ok}))


def test_missing_section_file_is_an_error(tmp_path):
    bad = VARIANTS.replace("sections: [skills, experience]", "sections: [skills, awards]")
    with pytest.raises(ValidationError) as excinfo:
        load(write_repo(tmp_path, **{"variants.yml": bad}))
    message = str(excinfo.value)
    assert "awards" in message
    assert "experience" in message  # lists what IS available


def test_unknown_block_type_is_an_error(tmp_path):
    bad = SKILLS.replace("type: labels", "type: bullets")
    with pytest.raises(ValidationError) as excinfo:
        load(write_repo(tmp_path, **{"content/skills.yml": bad}))
    message = str(excinfo.value)
    assert "bullets" in message
    assert "labels" in message
    assert "skills.yml" in message


def test_missing_entry_field_is_an_error(tmp_path):
    bad = """
title: Experience
type: entries
entries:
  - location: Ithaca NY
    dates: Jan 2025 - Current
    role: Lead Developer
"""
    with pytest.raises(ValidationError) as excinfo:
        load(write_repo(tmp_path, **{"content/experience.yml": bad}))
    message = str(excinfo.value)
    assert "'org'" in message
    assert "entry 0" in message


def test_malformed_marker_is_an_error(tmp_path):
    bad = EXPERIENCE.replace("+[gev-pos-1] Build", "+[gev-pos-1 Build")
    with pytest.raises(ValidationError) as excinfo:
        load(write_repo(tmp_path, **{"content/experience.yml": bad}))
    assert "unclosed" in str(excinfo.value).lower()


def test_all_problems_reported_in_one_pass(tmp_path):
    bad_skills = SKILLS.replace("type: labels", "type: bullets")
    bad_experience = EXPERIENCE.replace("+[gev-pos-1]", "+[gev-pos-9]")
    with pytest.raises(ValidationError) as excinfo:
        load(
            write_repo(
                tmp_path,
                **{"content/skills.yml": bad_skills, "content/experience.yml": bad_experience},
            )
        )
    assert len(excinfo.value.problems) >= 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_schema.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'cvgen.schema'`

- [ ] **Step 3: Write the implementation**

Create `cvgen/schema.py`:

```python
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
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        problems.append(f"{path.name}: invalid YAML - {exc}")
        return {}


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_schema.py -q`
Expected: PASS — 12 passed

- [ ] **Step 5: Commit**

```bash
git add cvgen/schema.py tests/test_schema.py
git commit -m "Add content loading and validation

Validation collects every problem before raising so one run surfaces all of
them, and each message names the file and item index."
```

---

### Task 3: Selection gates and ordering

**Files:**
- Create: `cvgen/select.py`
- Test: `tests/test_select.py`

**Interfaces:**
- Consumes: `cvgen.schema` — `Config`, `Entry`, `Item`, `Label`, `Section`; `cvgen.marker` — `GENERAL`, `Marker`.
- Produces:
  - `class SelectionError(Exception)`
  - `@dataclass(frozen=True) Document(length: str, variant: str, name: str, profile_name: str, tagline: str, contact: tuple[str, ...], sections: tuple[Section, ...])` where `name` is `f"cv-{length}-{variant}"`
  - `includes(marker: Marker, length: str, variant: str) -> bool`
  - `select(config: Config, length: str, variant: str) -> Document`

- [ ] **Step 1: Write the failing test**

Create `tests/test_select.py`:

```python
import pytest

from cvgen.marker import BOTH, GENERAL, LONG, Marker
from cvgen.schema import Config, Entry, Item, Label, Profile, Section
from cvgen.select import Document, SelectionError, includes, select


@pytest.mark.parametrize(
    "length, variant, expected",
    [
        ("long", "general", False),
        ("long", "gev-pos-1", True),
        ("long", "nvidia-pos-1", False),
        ("short", "google-pos-1", False),
    ],
)
def test_spec_truth_table(length, variant, expected):
    """The worked example from the spec: +[gev-pos-1, google-pos-1]."""
    marker = Marker(LONG, ("gev-pos-1", "google-pos-1"))
    assert includes(marker, length, variant) is expected


@pytest.mark.parametrize("variant", ["general", "gev-pos-1", "nvidia-pos-1"])
@pytest.mark.parametrize("length", ["long", "short"])
def test_general_is_inherited_by_every_variant(length, variant):
    assert includes(Marker(), length, variant) is True


def test_long_only_never_reaches_short():
    assert includes(Marker(LONG, (GENERAL,)), "short", "general") is False
    assert includes(Marker(LONG, (GENERAL,)), "long", "general") is True


def test_empty_only_list_reaches_nothing():
    assert includes(Marker(BOTH, ()), "long", "general") is False
    assert includes(Marker(BOTH, ()), "short", "gev-pos-1") is False


def build_config() -> Config:
    experience = Section(
        "experience",
        "Experience",
        "entries",
        (
            Entry(
                Marker(),
                "Cornell",
                "Ithaca NY",
                "Aug 2024",
                "PhD Researcher",
                (
                    Item(Marker(), "Shared bullet"),
                    Item(Marker(LONG, (GENERAL,)), "Long bullet"),
                ),
            ),
            Entry(Marker(BOTH, ("gev-pos-1",)), "Targeted", "London", "2023", "Consultant", ()),
        ),
    )
    skills = Section(
        "skills", "Technical Skills", "labels", (Label(Marker(), "Programming", "Python"),)
    )
    awards = Section("awards", "Awards", "rows", (Item(Marker(LONG, (GENERAL,)), "An award", "2026"),))
    profile = Profile(
        "Chengxuan Li",
        ("Email: x",),
        (Item(Marker(BOTH, ("gev-pos-1",)), "Targeted headline"), Item(Marker(), "Default headline")),
    )
    return Config(
        profile,
        {"experience": experience, "skills": skills, "awards": awards},
        {
            "long": {"general": ("skills", "experience", "awards"), "gev-pos-1": ("experience", "skills", "awards")},
            "short": {"general": ("skills", "experience", "awards")},
        },
    )


def test_document_name_and_order():
    doc = select(build_config(), "long", "gev-pos-1")
    assert doc.name == "cv-long-gev-pos-1"
    assert [s.name for s in doc.sections] == ["experience", "skills", "awards"]


def test_long_bullets_dropped_from_short():
    doc = select(build_config(), "short", "general")
    entry = doc.sections[1].items[0]
    assert [b.text for b in entry.bullets] == ["Shared bullet"]


def test_targeted_entry_only_in_its_variant():
    general = select(build_config(), "long", "general")
    targeted = select(build_config(), "long", "gev-pos-1")
    assert [e.org for e in general.sections[1].items] == ["Cornell"]
    assert [e.org for e in targeted.sections[0].items] == ["Cornell", "Targeted"]


def test_empty_section_is_dropped():
    # `awards` holds only long-tier content, so it vanishes from short.
    doc = select(build_config(), "short", "general")
    assert [s.name for s in doc.sections] == ["skills", "experience"]


def test_first_surviving_tagline_wins():
    assert select(build_config(), "long", "gev-pos-1").tagline == "Targeted headline"
    assert select(build_config(), "long", "general").tagline == "Default headline"


def test_no_surviving_tagline_raises():
    config = build_config()
    profile = Profile(config.profile.name, config.profile.contact, (Item(Marker(BOTH, ()), "Nope"),))
    broken = Config(profile, config.sections, config.documents)
    with pytest.raises(SelectionError) as excinfo:
        select(broken, "long", "general")
    assert "profile.yml" in str(excinfo.value)
    assert "long/general" in str(excinfo.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_select.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'cvgen.select'`

- [ ] **Step 3: Write the implementation**

Create `cvgen/select.py`:

```python
"""Decide what appears in a document.

This module never formats anything. It answers exactly one question per item:
does it belong in this (length, variant) document?
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .marker import BOTH, GENERAL, Marker
from .schema import Config, Entry, Section


class SelectionError(Exception):
    """A document cannot be assembled."""


@dataclass(frozen=True)
class Document:
    length: str
    variant: str
    name: str
    profile_name: str
    tagline: str
    contact: tuple[str, ...]
    sections: tuple[Section, ...]


def includes(marker: Marker, length: str, variant: str) -> bool:
    """Both gates, in the order the spec states them.

    `general` is an inherited base pool, not a sibling variant: unmarked content
    defaults to `only = (general,)` and therefore flows into every variant.
    """
    tier_ok = marker.tier == BOTH or length == "long"
    variant_ok = GENERAL in marker.only or variant in marker.only
    return tier_ok and variant_ok


def _filter_section(section: Section, length: str, variant: str) -> Section | None:
    kept: list[object] = []
    for item in section.items:
        if not includes(item.marker, length, variant):
            continue
        if isinstance(item, Entry):
            bullets = tuple(b for b in item.bullets if includes(b.marker, length, variant))
            item = replace(item, bullets=bullets)
        kept.append(item)
    if not kept:
        return None
    return replace(section, items=tuple(kept))


def select(config: Config, length: str, variant: str) -> Document:
    """Assemble one document, or raise SelectionError."""
    try:
        order = config.documents[length][variant]
    except KeyError:
        raise SelectionError(f"variants.yml declares no document {length}/{variant}") from None

    sections = tuple(
        filtered
        for name in order
        if (filtered := _filter_section(config.sections[name], length, variant)) is not None
    )

    tagline = next(
        (t.text for t in config.profile.taglines if includes(t.marker, length, variant)), None
    )
    if tagline is None:
        raise SelectionError(
            f"profile.yml: no tagline survives for document {length}/{variant}"
        )

    return Document(
        length=length,
        variant=variant,
        name=f"cv-{length}-{variant}",
        profile_name=config.profile.name,
        tagline=tagline,
        contact=config.profile.contact,
        sections=sections,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_select.py -q`
Expected: PASS — 21 passed

- [ ] **Step 5: Commit**

```bash
git add cvgen/select.py tests/test_select.py
git commit -m "Add inclusion gates and section ordering

Encodes the spec's truth table directly: general is an inherited base pool,
so unmarked content flows into every variant."
```

---

### Task 4: Emitting the .qmd

**Files:**
- Create: `cvgen/emit.py`
- Test: `tests/test_emit.py`

**Interfaces:**
- Consumes: `cvgen.select.Document`; `cvgen.schema` — `Entry`, `Item`, `Label`, `Section`.
- Produces: `render(doc: Document, template_dir: str = "templates") -> str`

Emitted div contract, which `templates/cv.lua` must match exactly:

| Div | Attributes | Contents |
|---|---|---|
| `.cv-head` | — | two child divs, `.cv-head-left` and `.cv-head-right` |
| `.cv-entry` | `dates` | `**Org**, Location` / `*Role*` / bullet list |
| `.cv-row` | `dates` | one paragraph |
| `.cv-prose` | — | one paragraph |
| `.cv-labels` | — | one paragraph of `**Label**: text` lines |

- [ ] **Step 1: Write the failing test**

Create `tests/test_emit.py`:

```python
from cvgen.emit import render
from cvgen.marker import Marker
from cvgen.schema import Entry, Item, Label, Section
from cvgen.select import Document


def build_doc() -> Document:
    return Document(
        length="long",
        variant="general",
        name="cv-long-general",
        profile_name="Chengxuan Li",
        tagline="PhD Candidate in Systems Engineering",
        contact=("Email: [x@y.edu](mailto:x@y.edu)", "Phone: +1 (607) 227 5495"),
        sections=(
            Section("skills", "Technical Skills", "labels", (Label(Marker(), "Programming", "Python, C#"),)),
            Section(
                "experience",
                "Experience",
                "entries",
                (
                    Entry(
                        Marker(),
                        "EnergyAtlas.io",
                        "Ithaca NY",
                        "Jan 2025 - Current",
                        "Lead Developer",
                        (Item(Marker(), "Lead **development** of a [twin](https://x)."),),
                    ),
                ),
            ),
            Section("awards", "Awards & Grants", "rows", (Item(Marker(), "**An award**", "May 2026"),)),
            Section("publications", "Selected Publications", "prose", (Item(Marker(), 'Li, C. "Paper." DOI: [10.1](https://x)'),)),
        ),
    )


def test_front_matter_wires_up_the_templates():
    out = render(build_doc())
    assert out.startswith("---\n")
    assert "format:" in out
    assert "typst:" in out
    assert "include-in-header: templates/cv.typ" in out
    assert "filters: [templates/cv.lua]" in out
    assert "format: pdf" not in out  # never LaTeX


def test_head_carries_name_tagline_and_contact():
    out = render(build_doc())
    assert "::: {.cv-head}" in out
    assert "::: {.cv-head-left}" in out
    assert "# Chengxuan Li" in out
    assert "PhD Candidate in Systems Engineering" in out
    assert "::: {.cv-head-right}" in out
    assert "Email: [x@y.edu](mailto:x@y.edu)  " in out  # hard line break


def test_sections_render_in_order_with_headings():
    out = render(build_doc())
    assert out.index("## Technical Skills") < out.index("## Experience")
    assert out.index("## Experience") < out.index("## Awards & Grants")


def test_entry_div_carries_dates_and_markdown_survives():
    out = render(build_doc())
    assert '::: {.cv-entry dates="Jan 2025 - Current"}' in out
    assert "**EnergyAtlas.io**, Ithaca NY" in out
    assert "*Lead Developer*" in out
    assert "- Lead **development** of a [twin](https://x)." in out


def test_row_and_prose_and_labels():
    out = render(build_doc())
    assert '::: {.cv-row dates="May 2026"}' in out
    assert "::: {.cv-prose}" in out
    assert '"Paper." DOI: [10.1](https://x)' in out
    assert "::: {.cv-labels}" in out
    assert "**Programming**: Python, C#" in out


def test_every_div_is_closed():
    out = render(build_doc())
    assert out.count(":::") == 2 * len([l for l in out.splitlines() if l.startswith("::: {")])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_emit.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'cvgen.emit'`

- [ ] **Step 3: Write the implementation**

Create `cvgen/emit.py`:

```python
"""Turn a selected Document into Quarto markdown.

This module never decides *what* appears - only how it is written. Content is
emitted as markdown inside fenced divs; templates/cv.lua converts those divs
into Typst calls, which is what lets bold, italics and links survive Pandoc.
"""

from __future__ import annotations

from .schema import Entry, Item, Label, Section
from .select import Document

FRONT_MATTER = """---
title: "{title}"
format:
  typst:
    papersize: us-letter
    margin:
      x: 1.6cm
      y: 1.4cm
    mainfont: Arial
    fontsize: 10pt
    include-in-header: {template_dir}/cv.typ
    filters: [{template_dir}/cv.lua]
---
"""


def _div(classes: str, body: list[str], **attrs: str) -> list[str]:
    rendered = "".join(f' {k}="{v}"' for k, v in attrs.items() if v)
    return [f"::: {{{classes}{rendered}}}", *body, ":::", ""]


def _head(doc: Document) -> list[str]:
    left = _div(".cv-head-left", [f"# {doc.profile_name}", "", doc.tagline])
    # Two trailing spaces make each contact line a markdown hard line break.
    right = _div(".cv-head-right", [f"{line}  " for line in doc.contact])
    return _div(".cv-head", [*left, *right])


def _labels(items: tuple[object, ...]) -> list[str]:
    lines = [f"**{i.label}**: {i.text}  " for i in items if isinstance(i, Label)]
    return _div(".cv-labels", lines)


def _entry(entry: Entry) -> list[str]:
    body = [f"**{entry.org}**, {entry.location}", "", f"*{entry.role}*"]
    if entry.bullets:
        body += ["", *[f"- {b.text}" for b in entry.bullets]]
    return _div(".cv-entry", body, dates=entry.dates)


def _section(section: Section) -> list[str]:
    lines = [f"## {section.title}", ""]
    if section.type == "labels":
        return lines + _labels(section.items)
    for item in section.items:
        if section.type == "entries":
            lines += _entry(item)
        elif section.type == "rows":
            lines += _div(".cv-row", [item.text], dates=item.date)
        else:  # prose
            lines += _div(".cv-prose", [item.text])
    return lines


def render(doc: Document, template_dir: str = "templates") -> str:
    """Render a document as Quarto markdown."""
    lines = [
        FRONT_MATTER.format(title=doc.profile_name, template_dir=template_dir),
        *_head(doc),
    ]
    for section in doc.sections:
        lines += _section(section)
    return "\n".join(lines).rstrip() + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_emit.py -q`
Expected: PASS — 6 passed

- [ ] **Step 5: Commit**

```bash
git add cvgen/emit.py tests/test_emit.py
git commit -m "Add qmd emitter

Content goes out as markdown inside fenced divs so Pandoc still processes
bold, italics and links inside every block."
```

---

### Task 5: Typst template and Lua filter

**Files:**
- Create: `templates/cv.typ`, `templates/cv.lua`
- Test: manual render, verified by inspecting the generated `.typ`

This task has no unit test; it is verified by rendering. The Lua filter must match the div contract in Task 4 exactly.

- [ ] **Step 1: Write the Lua filter**

Create `templates/cv.lua`:

```lua
-- Convert fenced divs into Typst function calls.
--
-- Each div becomes a raw Typst opening line, its Pandoc-processed content, and
-- a raw closing line. Sandwiching the content this way is what preserves bold,
-- italics and links: Pandoc still renders them, we only wrap the result.

local function raw(text)
  return pandoc.RawBlock("typst", text)
end

local function append(out, blocks)
  for _, block in ipairs(blocks or {}) do
    table.insert(out, block)
  end
end

local function wrap(open, content, close)
  local out = { raw(open) }
  append(out, content)
  table.insert(out, raw(close))
  return out
end

local function child(div, class)
  for _, block in ipairs(div.content) do
    if block.t == "Div" and block.classes:includes(class) then
      return block.content
    end
  end
  return {}
end

function Div(el)
  local classes = el.classes
  local dates = el.attributes["dates"] or ""

  if classes:includes("cv-head") then
    -- Pandoc walks inner nodes first; the child divs are untouched by this
    -- filter, so they are still present here to be split into grid cells.
    local out = { raw("#cv-head(left: [") }
    append(out, child(el, "cv-head-left"))
    table.insert(out, raw("], right: ["))
    append(out, child(el, "cv-head-right"))
    table.insert(out, raw("])"))
    return out
  elseif classes:includes("cv-entry") then
    return wrap("#cv-entry(dates: [" .. dates .. "])[", el.content, "]")
  elseif classes:includes("cv-row") then
    return wrap("#cv-row(dates: [" .. dates .. "])[", el.content, "]")
  elseif classes:includes("cv-prose") then
    return wrap("#cv-prose[", el.content, "]")
  elseif classes:includes("cv-labels") then
    return wrap("#cv-labels[", el.content, "]")
  end
end
```

- [ ] **Step 2: Write the Typst template**

Create `templates/cv.typ`:

```typst
// All CV styling lives here. build.py never formats; to restyle the CV, edit
// this file and nothing else. Page size, margins, font and base size come from
// the front matter that emit.py writes.

#set par(leading: 0.58em, spacing: 0.62em, justify: false)
#set list(indent: 0.55em, body-indent: 0.42em, spacing: 0.5em, marker: [•])

// Name.
#show heading.where(level: 1): it => text(size: 21pt, weight: "bold")[#it.body]

// Section heading: bold label with a rule directly beneath.
#show heading.where(level: 2): it => block(width: 100%, above: 0.95em, below: 0.5em)[
  #text(size: 11.5pt, weight: "bold")[#it.body]
  #v(-0.62em)
  #line(length: 100%, stroke: 0.7pt)
]

#let cv-head(left: [], right: []) = block(width: 100%, below: 0.55em)[
  #grid(
    columns: (1fr, auto),
    align(bottom)[#left],
    align(bottom + right)[#text(size: 9pt)[#right]],
  )
]

#let cv-entry(dates: [], body) = block(width: 100%, above: 0.55em, below: 0.3em)[
  #grid(columns: (1fr, auto), body, align(top + right)[#dates])
]

#let cv-row(dates: [], body) = block(width: 100%, above: 0.28em, below: 0.28em)[
  #grid(columns: (1fr, auto), body, align(top + right)[#dates])
]

#let cv-prose(body) = block(width: 100%, above: 0.34em, below: 0.34em)[
  #set par(hanging-indent: 1.1em)
  #body
]

#let cv-labels(body) = block(width: 100%, above: 0.2em, below: 0.3em)[#body]
```

- [ ] **Step 3: Render a fixture to verify the pipeline**

Write a throwaway fixture and render it. Use the scratchpad, not the repo.

```bash
python - <<'PY'
from pathlib import Path
from cvgen.emit import render
from cvgen.marker import Marker
from cvgen.schema import Entry, Item, Label, Section
from cvgen.select import Document

doc = Document("long", "general", "cv-long-general", "Chengxuan Li",
    "PhD Candidate in Systems Engineering",
    ("Email: [cl2749@cornell.edu](mailto:cl2749@cornell.edu)", "Phone: +1 (607) 227 5495"),
    (
     Section("skills", "Technical Skills", "labels", (Label(Marker(), "Programming", "Python, C#, .NET"),)),
     Section("experience", "Experience", "entries", (
        Entry(Marker(), "EnergyAtlas.io", "Ithaca NY", "Jan 2025 – Current", "Lead Developer",
              (Item(Marker(), "Lead **development** of a [digital twin](https://x)."),)),)),
     Section("awards", "Awards & Grants", "rows", (Item(Marker(), "**Nemetschek Innovation Award (€60,000)** *Second place*", "May 2026"),)),
    ))
Path(".build").mkdir(exist_ok=True)
# keep-typ makes Quarto leave the generated .typ behind for Step 4 to inspect.
qmd = render(doc).replace("  typst:\n", "  typst:\n    keep-typ: true\n")
Path(".build/fixture.qmd").write_text(qmd, encoding="utf-8")
PY
"/c/Program Files/Quarto/bin/quarto" render .build/fixture.qmd --to typst
```

Expected: `Output created: .build/fixture.pdf`

- [ ] **Step 4: Verify markdown survived into Typst**

Run:
```bash
grep -E '#cv-head|#cv-entry|#cv-row|#strong|#link' .build/fixture.typ
```

Expected — every one of these present, confirming Pandoc processed the content rather than the filter swallowing it:
- `#cv-head(left: [` and `], right: [`
- `#cv-entry(dates: [Jan 2025 – Current])[`
- `#strong[EnergyAtlas.io]`
- `#link("https://x")[digital twin]`
- `#cv-row(dates: [May 2026])[`

If `#strong` or `#link` are missing, the filter is emitting raw Typst where it should be sandwiching Pandoc output — re-check `wrap()`.

- [ ] **Step 5: Open the PDF and check it against the style guide**

Open `.build/fixture.pdf` and confirm: name large and bold at top left, contact small and right-aligned on the same row, section headings bold with a rule directly beneath, entry dates flush right on the org line, bullets tight. Compare against `resources/cv-style-guide.png` — **read-only; never copy it into the repo.**

- [ ] **Step 6: Commit**

```bash
rm -rf .build
git add templates/cv.typ templates/cv.lua
git commit -m "Add Typst template and Lua filter

The filter sandwiches Pandoc output between raw Typst rather than emitting
Typst directly, which is what keeps bold, italics and links working inside
every block. All styling lives in cv.typ."
```

---

### Task 6: The CLI

**Files:**
- Create: `build.py`
- Test: `tests/test_build.py`

**Interfaces:**
- Consumes: `cvgen.schema.load`, `cvgen.schema.ValidationError`, `cvgen.select.select`, `cvgen.select.SelectionError`, `cvgen.emit.render`.
- Produces: `find_quarto() -> str`, `documents_for(config, length, variant) -> list[tuple[str, str]]`, `main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Write the failing test**

Create `tests/test_build.py`:

```python
import pytest

import build
from cvgen.schema import Config, Item, Profile
from cvgen.marker import Marker


def config_with_documents() -> Config:
    documents = {
        "long": {"general": ("skills",), "gev-pos-1": ("skills",)},
        "short": {"general": ("skills",)},
    }
    return Config(Profile("X", (), (Item(Marker(), "T"),)), {}, documents)


def test_documents_for_all():
    assert sorted(build.documents_for(config_with_documents(), None, None)) == [
        ("long", "general"),
        ("long", "gev-pos-1"),
        ("short", "general"),
    ]


def test_documents_for_one_length():
    assert sorted(build.documents_for(config_with_documents(), "long", None)) == [
        ("long", "general"),
        ("long", "gev-pos-1"),
    ]


def test_documents_for_one_document():
    assert build.documents_for(config_with_documents(), "long", "gev-pos-1") == [("long", "gev-pos-1")]


def test_unknown_variant_lists_what_exists():
    with pytest.raises(SystemExit) as excinfo:
        build.documents_for(config_with_documents(), "long", "nope")
    assert "gev-pos-1" in str(excinfo.value)


def test_check_reports_validation_errors(tmp_path, capsys, monkeypatch):
    (tmp_path / "content").mkdir()
    (tmp_path / "variants.yml").write_text("long:\n  sections: [skills]\n  variants:\n    general: {}\n", encoding="utf-8")
    (tmp_path / "content" / "profile.yml").write_text("name: X\ntagline: T\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert build.main(["--check"]) == 1
    assert "skills" in capsys.readouterr().err
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_build.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'build'`

- [ ] **Step 3: Write the implementation**

Create `build.py`:

```python
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
from cvgen.schema import Config, LENGTHS, ValidationError, load
from cvgen.select import SelectionError, select

BUILD_DIR = Path(".build")
OUT_DIR = Path("out")
FALLBACK_QUARTO = Path(r"C:\Program Files\Quarto\bin\quarto.exe")


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
    return pdf


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="build every declared document")
    parser.add_argument("--long", dest="length", action="store_const", const="long")
    parser.add_argument("--short", dest="length", action="store_const", const="short")
    parser.add_argument("--variant", help="build only this variant")
    parser.add_argument("--check", action="store_true", help="validate content, render nothing")
    args = parser.parse_args(argv)

    try:
        config = load(Path.cwd())
    except ValidationError as exc:
        print(f"content is invalid:\n{exc}", file=sys.stderr)
        return 1

    if args.check:
        print(f"content is valid: {len(config.all_documents())} documents declared")
        return 0

    if not (args.all or args.length or args.variant):
        parser.error("choose --all, --long, --short, --variant or --check")

    try:
        documents = documents_for(config, args.length, args.variant)
        quarto = find_quarto()
        for length, variant in documents:
            print(f"building {length}/{variant}")
            print(f"  wrote {build_one(config, quarto, length, variant)}")
    except SelectionError as exc:
        print(f"cannot build: {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"quarto failed with exit code {exc.returncode}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_build.py -q`
Expected: PASS — 5 passed

- [ ] **Step 5: Commit**

```bash
git add build.py tests/test_build.py
git commit -m "Add build CLI

Locates Quarto by PATH with a fallback to the Windows install location, since
Quarto is not on PATH in every shell."
```

---

### Task 7: Seed content and verify end to end

**Files:**
- Create: `variants.yml`, `content/profile.yml`, `content/skills.yml`, `content/experience.yml`, `content/publications.yml`, `content/awards.yml`, `content/education.yml`
- Modify: `README.md` (drop the Status line)
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: everything above. Produces no new API.

**Content rule:** transcribe from `resources/cv-content-ref.docx` **unmarked**, so short and long start identical. Adding `+` markers is the owner's judgment call about their own record — do not invent tiers. Read `resources/` but never copy it into the repo and never let the build read from it.

- [ ] **Step 1: Write `variants.yml`**

Variant names are placeholders; only `general` is real. Ship the example commented out so no fictitious employer names sit in the repo.

```yaml
# Which documents exist. Each (length, variant) pair builds one PDF.
#
# `sections` is the default order for that length; a variant may override it.
# Section names are the filename stems in content/.

long:
  sections: [skills, experience, publications, awards, education]
  variants:
    general: {}
    # example-role: {sections: [skills, experience, awards, publications, education]}

short:
  sections: [skills, experience, education]
  variants:
    general: {}
    # example-role: {}
```

- [ ] **Step 2: Write the content files**

`content/profile.yml`:

```yaml
name: Chengxuan Li
contact:
  - "Email: [cl2749@cornell.edu](mailto:cl2749@cornell.edu)"
  - "Phone: +1 (607) 227 5495"
# A list: the first tagline passing both gates wins. Put targeted lines above
# the unmarked fallback.
tagline:
  - PhD Candidate in Systems Engineering, Minor in Electrical & Computer Engineering
```

`content/skills.yml`:

```yaml
title: Technical Skills
type: labels
items:
  - label: Programming
    text: Python, C#, .NET/ASP.NET, C++
  - label: ML
    text: PyTorch, scikit-learn, statsmodels, pandas, SQL, DuckDB
  - label: Geospatial
    text: GeoPandas, Shapely, NetTopologySuite
  - label: Scientific computing
    text: Optimization, surrogate modeling, Monte Carlo simulation, time-series analysis, signal processing
  - label: Electrical systems
    text: >-
      AC power flow (NR/FDLF), contingency analysis, state estimation, economic
      dispatch, OPF, static security assessment, demand-response and load
      flexibility assessment
```

`content/experience.yml`:

```yaml
title: Experience
type: entries
entries:
  - org: Cornell University, Environmental Systems Lab
    location: Ithaca NY
    dates: Aug 2024 – Current
    role: "PhD Researcher, Advisors: Prof Timur Dogan, Prof Oliver Gao, Prof Jacob Mays"
    bullets:
      - Develop load profile inference methods using machine learning, optimization, and statistical modeling.
      - Research time-series-based inverse modeling and surrogate-learning workflows for model calibration.
  - org: EnergyAtlas.io
    location: Ithaca NY
    dates: Jan 2025 – Current
    role: Lead Developer
    bullets:
      - Lead development of a city-scale utility digital twin and energy simulation platform in C#/.NET.
      - >-
        Design core simulation, geometry, data, and visualization architecture
        integrating building models, geospatial data, smart-meter observations,
        and physical simulation.
      - Build scalable pipelines for LiDAR, shading analysis, time-series processing, and large-scale urban simulations.
  - org: Urban Systems Design MEP Engineers
    location: London UK
    dates: Jul 2023 – Sep 2023
    role: Environmental Engineering Consultant
    bullets:
      - Conduct sustainability assessment with **CBRE GWS** for 13+ **Google** workplace properties in the Americas.
```

`content/publications.yml`:

```yaml
title: Selected Publications
type: prose
items:
  - >-
    Li, C., Wang, Z. J., Dogan, T. "ShadingZip: Within-Building Selective
    Computation of Shading Profiles for Urban Building Energy Models." Accepted
    for ASIM2026.
  - >-
    Li, C., Dogan, T. "Calendars of the City: Deterministic Schedule Libraries
    to Enhance UBEM Load Duration Forecasts." IBPSA SimBuild 2026.
    [DOI: 10.26868/30680611.2026.1321](https://doi.org/10.26868/30680611.2026.1321)
  - >-
    Li, C., Dogan, T. "Deriving High-Fidelity Residential Building Archetypes
    and Typical Usage Patterns from National Energy Use Surveys…" Building
    Simulation 2025.
    [DOI: 10.26868/25222708.2025.1336](https://doi.org/10.26868/25222708.2025.1336)
  - >-
    Dogan, T., Li, C., et al. "A Bottom-Up Urban Building Energy Model for
    Evaluating Thermal Load Electrification Measures." Journal of Building
    Performance Simulation, 2025.
    [DOI: 10.1080/19401493.2025.2536261](https://doi.org/10.1080/19401493.2025.2536261)
```

`content/awards.yml`:

```yaml
title: Awards & Grants
type: rows
items:
  - text: "**Nemetschek Innovation Award (€60,000)** *Second place, with no first place awarded*"
    date: May 2026
  - text: "**IBPSA-USA Simulation Showcase ($600)** *Winner*"
    date: May 2026
  - text: "**New York State Pollution Prevention Institute Competition ($3,000)** *Winner*"
    date: Apr 2026
  - text: "**NYSP2I Research Grant ($4,000)** *Co-PI*"
    date: Nov 2025
  - text: "**Holcim Building Tomorrow Scholarship** *Winner*"
    date: Nov 2025
  - text: "**Bentley Systems Going Digital Awards 2025** *Founders' Honors*"
    date: Oct 2025
```

`content/education.yml`:

```yaml
title: Education
type: entries
entries:
  - org: Cornell University
    location: Ithaca NY
    dates: Aug 2024 – Current
    role: PhD in Systems Engineering, minor in Electrical and Computer Engineering
  - org: Architectural Association
    location: London UK
    dates: Jun 2024
    role: M.Arch
  - org: Architectural Association
    location: London UK
    dates: Jun 2022
    role: BA (Hons)
```

- [ ] **Step 3: Validate the content**

Run: `python build.py --check`
Expected: `content is valid: 2 documents declared`

- [ ] **Step 4: Write the end-to-end test**

Create `tests/test_render.py`:

```python
import re
import subprocess
import sys
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
    return len(re.findall(rb"/Type\s*/Page\b", pdf.read_bytes()))


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
```

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS — all tests, no failures

- [ ] **Step 6: Check the PDFs against the style guide**

Open `out/cv-long-general.pdf` and `out/cv-short-general.pdf`. Compare against `resources/cv-style-guide.png` (read-only). Confirm the short CV is one page and both match the reference layout.

If spacing is off, adjust **`templates/cv.typ` only** — never `cvgen/`.

- [ ] **Step 7: Drop the README status line**

Remove these two lines from `README.md`, since the generator now works:

```markdown
> **Status:** design approved and toolchain verified; the generator is being
> implemented. See [the design spec](docs/superpowers/specs/2026-09-03-cv-gen-design.md).
```

- [ ] **Step 8: Confirm resources/ is still untracked**

Run: `git status --short && git check-ignore -v resources/cv-content-ref.docx`
Expected: `resources/` appears nowhere in `git status`; `check-ignore` reports `.gitignore:2:resources/`

- [ ] **Step 9: Commit**

```bash
git add variants.yml content/ tests/test_render.py README.md
git commit -m "Seed content and verify end to end

Content is transcribed unmarked, so short and long start identical; tiering
is the owner's call. variants.yml ships with general only, with the variant
example commented out."
```

---

## Self-Review

**Spec coverage.** Every spec section maps to a task: marker grammar and its collision table → Task 1; block types, `variants.yml`, all load-time errors → Task 2; the two gates, `general` inheritance, empty-section dropping, tagline selection → Task 3; the div contract → Task 4; the four block renderings and Typst styling → Task 5; the CLI, Quarto discovery, and its errors → Task 6; content seeding and the render smoke test → Task 7.

**Interface consistency.** `Marker`/`Marked`/`parse_item`/`parse_mark` (Task 1) are consumed under those exact names in Tasks 2 and 3. `Item`/`Label`/`Entry`/`Section`/`Profile`/`Config` (Task 2) are used unchanged in Tasks 3, 4 and 6. `Document`'s field names (Task 3) match every access in Task 4. The div classes and the `dates` attribute emitted in Task 4 match the Lua filter's branches in Task 5 exactly, and both match the Typst function signatures `cv-head(left:, right:)`, `cv-entry(dates:)`, `cv-row(dates:)`, `cv-prose(body)`, `cv-labels(body)`.

**Known follow-ups**, deliberately deferred and not blocking:

- The reference CV fits one page, so `cv-long-general` and `cv-short-general` are currently identical apart from the three extra sections. They diverge as soon as `+` markers are added.
- `test_render.py::page_count` counts `/Type /Page` occurrences, which is adequate for Typst output but would need a real PDF parser if the tooling changed.
