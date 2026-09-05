"""Emit JSON Schema from the declarative spec.

Generated, never hand-written: `spec.py` is the source and `tests/test_schema_export.py`
asserts the committed files under `schema/` still match. That is what stops the
published schema from drifting away from the validator.

Structure only. The marker grammar and the two inclusion gates are semantics no
JSON Schema can express - `--lint` and `--explain` cover those.
"""

from __future__ import annotations

import json
from pathlib import Path

from .localize import LANG_CODE, SOURCE_LANG
from .spec import (
    BLOCKS,
    FLAT,
    GENERAL,
    LENGTHS,
    MARK,
    MARKED,
    MARKED_LIST,
    BlockSpec,
    FieldSpec,
)

DRAFT = "https://json-schema.org/draft/2020-12/schema"

# '+', '-', '+[a,b]' - the mark: field only, which carries no text.
MARK_PATTERN = r"^[+-](\[[^\]]*\])?$"

SCHEMA_DIR = "schema"
FILES = {
    "cv-section.schema.json": "section",
    "cv-profile.schema.json": "profile",
    "cv-variants.schema.json": "variants",
}


# A language-keyed map: {en: ..., zh: ...}. The schema admits any two-letter
# code; the loader enforces the set declared in variants.yaml, which a static
# schema cannot know. `en` is required because it is the source every other
# language falls back to. The key pattern is what makes a map standing in for a
# rows or prose item unambiguous: no field name is two lowercase letters.
LANG_MAP = {
    "type": "object",
    "description": (
        "Per-language text. 'en' is the source; any declared language may be "
        "added and falls back to en when absent."
    ),
    "propertyNames": {"pattern": LANG_CODE.pattern},
    "additionalProperties": {"type": "string"},
    "required": [SOURCE_LANG],
    "minProperties": 1,
}


def _localized(node: dict) -> dict:
    """A string node, or the same text as a language map."""
    description = node.pop("description", None)
    out: dict = {"oneOf": [node, LANG_MAP]}
    if description:
        out["description"] = description
    return out


def _field(spec: FieldSpec) -> dict:
    if spec.kind == MARKED_LIST:
        node: dict = {"type": "array", "items": _localized({"type": "string"})}
    elif spec.kind == MARK:
        node = {"type": "string", "pattern": MARK_PATTERN}
    else:
        node = {"type": "string"}
    if spec.doc:
        node["description"] = spec.doc
    if spec.kind == MARKED:
        node["description"] = (
            f"{spec.doc} A leading '+ ' or '-[variant] ' marker is honoured; "
            "the space is required, and it is read from the en text only."
        ).strip()
    if spec.kind == MARKED or spec.translatable:
        return _localized(node)
    return node


def _item(block: BlockSpec) -> dict:
    mapping = {
        "type": "object",
        "properties": {f.name: _field(f) for f in block.fields},
        "required": list(block.required_fields),
        "additionalProperties": False,
    }
    if block.item_form == FLAT:
        return {
            "oneOf": [
                {"type": "string", "description": f"Shorthand for {{{block.text_field}: ...}}."},
                {**LANG_MAP, "description": f"Localized shorthand for {{{block.text_field}: ...}}."},
                mapping,
            ]
        }
    return mapping


def _block(block: BlockSpec) -> dict:
    return {
        "title": f"{block.type} section",
        "description": f"{block.used_by}. Renders as: {block.renders_as}",
        "type": "object",
        "properties": {
            "title": _localized(
                {"type": "string", "description": "Heading rendered above the section."}
            ),
            "type": {"const": block.type},
            block.items_key: {"type": "array", "items": _item(block)},
        },
        "required": ["title", "type", block.items_key],
        "additionalProperties": False,
    }


def section_schema() -> dict:
    return {
        "$schema": DRAFT,
        "$id": "cv-section.schema.json",
        "title": "cv-gen section file",
        "description": (
            "One content/*.yaml section file. The 'type' key selects which shape "
            "applies. Structure only - marker semantics are not expressible here."
        ),
        "type": "object",
        "oneOf": [_block(b) for b in BLOCKS.values()],
    }


def profile_schema() -> dict:
    marked = _localized({"type": "string"})
    return {
        "$schema": DRAFT,
        "$id": "cv-profile.schema.json",
        "title": "cv-gen profile file",
        "description": (
            "content/profile.yaml, and the untracked content/profile.local.yaml that "
            "shallow-overrides its top-level keys. No key is required here, because "
            "the override file is partial by design - 'name' is enforced after the "
            "merge, at load time, which is the only point where it can be."
        ),
        "type": "object",
        "properties": {
            "name": _localized({"type": "string"}),
            "anticipated_graduation": _localized(
                {
                    "type": "string",
                    "description": "Expected graduation date shown beside the name.",
                }
            ),
            "contact": {
                "type": "array",
                "items": _localized({"type": "string"}),
                "description": "One markdown line per contact method.",
            },
            "tagline": {
                "description": "A string, or a list where the first item passing both gates wins.",
                "oneOf": [marked, {"type": "array", "items": marked}],
            },
        },
        "additionalProperties": False,
    }


def variants_schema() -> dict:
    sections = {
        "type": "array",
        "items": {"type": "string"},
        "description": "Section names, which are content/ filename stems, in render order.",
    }
    return {
        "$schema": DRAFT,
        "$id": "cv-variants.schema.json",
        "title": "cv-gen variants file",
        "description": (
            "variants.yaml: which (length, variant) documents exist, and which "
            "languages each renders in."
        ),
        "type": "object",
        "properties": {
            "languages": {
                "type": "object",
                "description": (
                    "Output languages. A third axis: every (length, variant) renders "
                    "once per language. 'en' is the source and is required if this "
                    "key is present; when absent, English alone is built."
                ),
                "propertyNames": {"pattern": LANG_CODE.pattern},
                "required": [SOURCE_LANG],
                "additionalProperties": {
                    "type": ["object", "null"],
                    "properties": {
                        "typst": {
                            "type": "string",
                            "description": "Typst `lang` code; drives line-breaking (zh for Chinese).",
                        },
                        "font": {
                            "description": "A font, or a fallback stack; Latin first, then CJK.",
                            "oneOf": [
                                {"type": "string"},
                                {"type": "array", "items": {"type": "string"}, "minItems": 1},
                            ],
                        },
                        "sep": {"type": "string", "description": "Between org and location."},
                        "colon": {"type": "string", "description": "After a skills label."},
                        "graduation": {"type": "string", "description": "Label beside the name."},
                    },
                    "additionalProperties": False,
                },
            },
            **{
                length: {
                "type": "object",
                "properties": {
                    "sections": sections,
                    "variants": {
                        "type": "object",
                        "description": (
                            f"Variant name to optional overrides. '{GENERAL}' is the "
                            "inherited base pool, not a sibling variant."
                        ),
                        "additionalProperties": {
                            "type": ["object", "null"],
                            "properties": {"sections": sections},
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["sections", "variants"],
                "additionalProperties": False,
            }
                for length in LENGTHS
            },
        },
        "anyOf": [{"required": [length]} for length in LENGTHS],
        "additionalProperties": False,
    }


BUILDERS = {
    "section": section_schema,
    "profile": profile_schema,
    "variants": variants_schema,
}


def all_schemas() -> dict[str, dict]:
    """Filename -> schema document."""
    return {name: BUILDERS[kind]() for name, kind in FILES.items()}


def serialise(schema: dict) -> str:
    return json.dumps(schema, indent=2) + "\n"


def write(root: Path) -> list[Path]:
    """Write every schema under root/schema/, returning the paths written."""
    out_dir = root / SCHEMA_DIR
    out_dir.mkdir(exist_ok=True)
    written = []
    for name, schema in all_schemas().items():
        path = out_dir / name
        path.write_text(serialise(schema), encoding="utf-8")
        written.append(path)
    return written
