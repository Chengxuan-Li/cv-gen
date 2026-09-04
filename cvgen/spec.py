"""The content model, declared as data rather than as code.

This table is the single source of truth for what a `content/*.yml` file may
contain. `schema.py` validates against it and `jsonschema.py` emits a JSON
Schema from it, so the validator, the published schema and the documentation
cannot drift apart - there is only one place to change.

What it deliberately does NOT describe: the marker grammar and the two inclusion
gates. Those are semantics, not structure, and no declarative table or JSON
Schema can express them. They live in `marker.py` and `select.py`, and `--lint`
and `--explain` are how an agent checks them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# How a field's string value is interpreted once structure is valid.
PLAIN = "plain"  # literal text
MARKED = "marked"  # text that may carry a leading marker token
MARK = "mark"  # a bare marker token, no text
MARKED_LIST = "marked_list"  # a list of MARKED strings

# Item forms.
MAPPING = "mapping"  # the item must be a mapping
FLAT = "flat"  # a bare string is shorthand for {text: <string>}


@dataclass(frozen=True)
class FieldSpec:
    name: str
    required: bool = False
    kind: str = PLAIN
    doc: str = ""


@dataclass(frozen=True)
class BlockSpec:
    """One `type:` a content file may declare."""

    type: str
    items_key: str  # the YAML key holding the list of items
    item_form: str
    fields: tuple[FieldSpec, ...]
    renders_as: str
    used_by: str

    @property
    def required_fields(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields if f.required)

    def field(self, name: str) -> FieldSpec | None:
        return next((f for f in self.fields if f.name == name), None)

    @property
    def text_field(self) -> str:
        """The field carrying the item's marked text, for FLAT shorthand."""
        return next(f.name for f in self.fields if f.kind == MARKED)


BLOCKS: dict[str, BlockSpec] = {
    "labels": BlockSpec(
        type="labels",
        items_key="items",
        item_form=MAPPING,
        fields=(
            FieldSpec("label", required=True, doc="The bolded label before the colon."),
            FieldSpec("text", required=True, kind=MARKED, doc="Markdown, may carry a marker."),
        ),
        renders_as="`**Label**: text`, one per line",
        used_by="Skills",
    ),
    "entries": BlockSpec(
        type="entries",
        items_key="entries",
        item_form=MAPPING,
        fields=(
            FieldSpec("org", required=True, doc="Organisation, rendered bold."),
            FieldSpec("location", required=True, doc="Rendered after the org, unbolded."),
            FieldSpec("dates", required=True, doc="Rendered flush right on the org line."),
            FieldSpec("role", required=True, doc="Rendered italic on its own line."),
            FieldSpec("mark", kind=MARK, doc="Marker for the whole entry, e.g. '+' or '-[a,b]'."),
            FieldSpec("bullets", kind=MARKED_LIST, doc="Markdown bullets, each may carry a marker."),
        ),
        renders_as="**Org**, Location - right-aligned date; *italic role*; bullets",
        used_by="Experience, Education",
    ),
    "rows": BlockSpec(
        type="rows",
        items_key="items",
        item_form=FLAT,
        fields=(
            FieldSpec("text", required=True, kind=MARKED, doc="Markdown, may carry a marker."),
            FieldSpec("date", doc="Rendered flush right on the same line."),
        ),
        renders_as="one line, text left - date right",
        used_by="Awards & Grants",
    ),
    "prose": BlockSpec(
        type="prose",
        items_key="items",
        item_form=FLAT,
        fields=(FieldSpec("text", required=True, kind=MARKED, doc="Markdown, may carry a marker."),),
        renders_as="markdown paragraph with hanging indent",
        used_by="Publications",
    ),
}

BLOCK_TYPES = tuple(BLOCKS)

# Keys every section file carries, whatever its type.
SECTION_FIELDS = (
    FieldSpec("title", required=True, doc="The heading rendered above the section."),
    FieldSpec("type", required=True, doc=f"One of: {', '.join(BLOCK_TYPES)}."),
)

LENGTHS = ("long", "short")

# The name that acts as the inherited base pool rather than a sibling variant.
GENERAL = "general"
