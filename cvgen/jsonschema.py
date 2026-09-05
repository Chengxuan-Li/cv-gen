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


def _field(spec: FieldSpec) -> dict:
    if spec.kind == MARKED_LIST:
        node: dict = {"type": "array", "items": {"type": "string"}}
    elif spec.kind == MARK:
        node = {"type": "string", "pattern": MARK_PATTERN}
    else:
        node = {"type": "string"}
    if spec.doc:
        node["description"] = spec.doc
    if spec.kind == MARKED:
        node["description"] = (
            f"{spec.doc} A leading '+ ' or '-[variant] ' marker is honoured; "
            "the space is required."
        ).strip()
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
            "title": {"type": "string", "description": "Heading rendered above the section."},
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
    marked = {"type": "string"}
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
            "name": {"type": "string"},
            "anticipated_graduation": {
                "type": "string",
                "description": "Expected graduation date shown beside the name.",
            },
            "contact": {
                "type": "array",
                "items": {"type": "string"},
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
        "description": "variants.yaml: which (length, variant) documents exist.",
        "type": "object",
        "properties": {
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
        "minProperties": 1,
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
