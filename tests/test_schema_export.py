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


# --- Localization -----------------------------------------------------------


def test_translatable_fields_accept_a_language_map():
    schema = committed("cv-section.schema.json")
    jsonschema.validate(
        {
            "title": {"en": "Experience", "zh": "经历"},
            "type": "entries",
            "entries": [
                {
                    "org": {"en": "Cornell", "zh": "康奈尔"},
                    "location": "Ithaca NY",
                    "dates": {"en": "Aug 2024", "zh": "2024年8月"},
                    "role": "PhD",
                    "bullets": ["plain", {"en": "+ marked", "zh": "翻译"}],
                }
            ],
        },
        schema,
    )


def test_a_language_map_can_stand_in_for_a_flat_item():
    schema = committed("cv-section.schema.json")
    jsonschema.validate(
        {"title": "P", "type": "prose", "items": [{"en": "Paper.", "zh": "论文。"}]}, schema
    )


@pytest.mark.parametrize(
    "bad, why",
    [
        ({"title": "P", "type": "prose", "items": [{"zh": "论文。"}]}, "map without en"),
        ({"title": "P", "type": "prose", "items": [{"en": "a", "text": "b"}]}, "mixed keys"),
        ({"title": "P", "type": "prose", "items": [{"eng": "a"}]}, "three-letter key"),
        (
            {"title": "X", "type": "entries", "entries": [{"org": "A", "location": "B",
             "dates": "C", "role": "D", "mark": {"en": "+", "zh": "+"}}]},
            "mark is never localized",
        ),
    ],
)
def test_schema_rejects_malformed_language_maps(bad, why):
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, committed("cv-section.schema.json"))


def test_variants_schema_accepts_and_constrains_languages():
    schema = committed("cv-variants.schema.json")
    base = {"short": {"sections": ["skills"], "variants": {"general": {}}}}
    jsonschema.validate(
        {**base, "languages": {"en": {"typst": "en", "font": "Garamond"},
                               "zh": {"typst": "zh", "font": ["Garamond", "Noto Serif SC"]}}},
        schema,
    )
    with pytest.raises(jsonschema.ValidationError):  # en is the required source
        jsonschema.validate({**base, "languages": {"zh": {"typst": "zh"}}}, schema)
    with pytest.raises(jsonschema.ValidationError):  # unknown per-language key
        jsonschema.validate({**base, "languages": {"en": {"typeface": "x"}}}, schema)


def test_profile_schema_accepts_localized_name_and_contact():
    jsonschema.validate(
        {
            "name": {"en": "Chengxuan Li", "zh": "李承轩"},
            "contact": ["Email: x", {"en": "Web: y", "zh": "网站：y"}],
            "tagline": [{"en": "A", "zh": "甲"}, "B"],
            "anticipated_graduation": {"en": "May 2028", "zh": "2028年5月"},
        },
        committed("cv-profile.schema.json"),
    )
