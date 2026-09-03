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
        ("long", "general"),
        ("long", "gev-pos-1"),
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
