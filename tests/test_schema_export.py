"""The emitted JSON Schema must stay in sync with the validator, and must
actually accept the real content - a schema that accepts everything would pass
a sync check while being useless.
"""

import json
from pathlib import Path

import pytest
import yaml

from cvgen.jsonschema import FILES, all_schemas, serialise
from cvgen.schema import LOCAL_SUFFIX
from cvgen.spec import BLOCKS

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schema"

jsonschema = pytest.importorskip("jsonschema")


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def committed(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(FILES))
def test_committed_schema_matches_generated(name):
    """Regenerate with `python build.py --schema` if this fails."""
    assert (SCHEMA_DIR / name).read_text(encoding="utf-8") == serialise(all_schemas()[name])


@pytest.mark.parametrize("name", sorted(FILES))
def test_each_schema_is_itself_valid(name):
    jsonschema.Draft202012Validator.check_schema(committed(name))


@pytest.mark.parametrize(
    "path",
    sorted(
        p
        for p in (ROOT / "content").glob("*.yaml")
        if p.stem != "profile" and not p.name.endswith(LOCAL_SUFFIX)
    ),
)
def test_real_section_files_validate(path):
    jsonschema.validate(load_yaml(path), committed("cv-section.schema.json"))


def test_real_profile_validates():
    jsonschema.validate(
        load_yaml(ROOT / "content" / "profile.yaml"), committed("cv-profile.schema.json")
    )


def test_real_variants_file_validates():
    jsonschema.validate(load_yaml(ROOT / "variants.yaml"), committed("cv-variants.schema.json"))


def test_every_block_type_is_represented():
    branches = committed("cv-section.schema.json")["oneOf"]
    assert {b["properties"]["type"]["const"] for b in branches} == set(BLOCKS)


@pytest.mark.parametrize(
    "bad, why",
    [
        ({"title": "X", "type": "bogus", "items": []}, "unknown type"),
        ({"type": "prose", "items": []}, "missing title"),
        ({"title": "X", "type": "prose"}, "missing items"),
        ({"title": "X", "type": "entries", "entries": [{"org": "A"}]}, "entry missing fields"),
        ({"title": "X", "type": "prose", "items": [], "extra": 1}, "unknown key"),
        ({"title": "X", "type": "entries", "entries": [{"org": "A", "location": "B",
          "dates": "C", "role": "D", "mark": "not-a-marker"}]}, "malformed mark"),
    ],
)
def test_schema_rejects_invalid_sections(bad, why):
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, committed("cv-section.schema.json"))


def test_flat_items_accept_both_shorthand_and_mapping():
    schema = committed("cv-section.schema.json")
    jsonschema.validate({"title": "X", "type": "prose", "items": ["a bare string"]}, schema)
    jsonschema.validate(
        {"title": "X", "type": "rows", "items": [{"text": "a", "date": "May 2026"}]}, schema
    )
