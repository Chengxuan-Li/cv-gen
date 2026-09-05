"""Optionally-localized strings: loading, resolution, fallback, and the errors."""

from pathlib import Path

import pytest

from cvgen.localize import LStr, is_lang_map
from cvgen.schema import ValidationError, load

VARIANTS = """
languages:
  en: {typst: en, font: Garamond}
  zh: {typst: zh, font: [Garamond, Noto Serif SC]}
long:
  sections: [experience, publications]
  variants:
    general: {}
short:
  sections: [experience]
  variants:
    general: {}
"""

VARIANTS_EN_ONLY = """
long:
  sections: [experience, publications]
  variants:
    general: {}
"""

PROFILE = """
name: {en: Chengxuan Li, zh: 李承轩}
contact:
  - "Email: [you@example.com](mailto:you@example.com)"
tagline: {en: A tagline, zh: 一句话}
"""

EXPERIENCE = """
title: {en: Experience, zh: 工作经历}
type: entries
entries:
  - org: {en: Cornell University, zh: 康奈尔大学}
    location: Ithaca NY
    dates: {en: Aug 2024 - Present, zh: 2024年8月 - 至今}
    role: PhD Researcher
    bullets:
      - Develop load profile inference methods.
      - en: + Research inverse-modeling workflows.
        zh: 研究反演建模工作流。
"""

PUBLICATIONS = """
title: Publications
type: prose
items:
  - en: "Li, C. **Paper**."
    zh: "李，C. **论文**。"
  - A plain publication.
  - text: {en: "With a date", zh: "带日期"}
"""


def write_repo(root: Path, **overrides: str) -> Path:
    files = {
        "variants.yaml": VARIANTS,
        "content/profile.yaml": PROFILE,
        "content/experience.yaml": EXPERIENCE,
        "content/publications.yaml": PUBLICATIONS,
    }
    files.update(overrides)
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


# --- LStr itself -------------------------------------------------------------


def test_lstr_behaves_as_its_source_string():
    s = LStr("Cornell", {"zh": "康奈尔"})
    assert s == "Cornell"
    assert f"{s}" == "Cornell"
    assert s.in_("en") == "Cornell"
    assert s.in_("zh") == "康奈尔"
    assert s.in_("fr") == "Cornell"  # no such translation: fall back
    assert s.has("en") and s.has("zh") and not s.has("fr")


def test_is_lang_map_requires_every_key_to_be_a_language_code():
    assert is_lang_map({"en": "a", "zh": "b"})
    assert is_lang_map({"zh-CN": "b"})
    assert not is_lang_map({"text": "a", "date": "b"})
    assert not is_lang_map({"en": "a", "text": "b"})
    assert not is_lang_map({"org": "a"})  # three letters: never a language here
    assert not is_lang_map({})
    assert not is_lang_map("a string")


# --- Loading -----------------------------------------------------------------


def test_plain_strings_load_as_lstr_and_fall_back(tmp_path):
    config = load(write_repo(tmp_path))
    entry = config.sections["experience"].items[0]
    assert isinstance(entry.location, LStr)
    assert entry.location.translations == {}
    assert entry.location.in_("zh") == "Ithaca NY"


def test_language_map_resolves_per_language(tmp_path):
    config = load(write_repo(tmp_path))
    section = config.sections["experience"]
    entry = section.items[0]
    assert entry.org == "Cornell University"  # the str view is always the source
    assert entry.org.in_("zh") == "康奈尔大学"
    assert entry.dates.in_("zh") == "2024年8月 - 至今"
    assert section.title.in_("zh") == "工作经历"
    assert config.profile.name.in_("zh") == "李承轩"
    assert config.profile.taglines[0].text.in_("zh") == "一句话"


def test_marker_is_parsed_from_the_source_only(tmp_path):
    bullet = load(write_repo(tmp_path)).sections["experience"].items[0].bullets[1]
    assert bullet.marker.tier == "long"
    assert bullet.text == "Research inverse-modeling workflows."  # marker stripped
    assert bullet.text.in_("zh") == "研究反演建模工作流。"  # translation untouched


def test_language_map_as_a_flat_item_is_shorthand_for_text(tmp_path):
    items = load(write_repo(tmp_path)).sections["publications"].items
    assert items[0].text == "Li, C. **Paper**."
    assert items[0].text.in_("zh") == "李，C. **论文**。"
    assert items[1].text.in_("zh") == "A plain publication."
    assert items[2].text.in_("zh") == "带日期"  # explicit text: with a map value


def test_undeclared_language_in_a_map_is_an_error(tmp_path):
    bad = EXPERIENCE.replace("zh: 康奈尔大学", "fr: Universite Cornell")
    with pytest.raises(ValidationError) as excinfo:
        load(write_repo(tmp_path, **{"content/experience.yaml": bad}))
    problem = next(p for p in excinfo.value.problems if p.code == "undeclared_language")
    assert "'fr'" in problem.message
    assert problem.file == "experience.yaml"
    assert problem.line is not None


def test_a_map_without_the_source_language_is_an_error(tmp_path):
    bad = EXPERIENCE.replace(
        "org: {en: Cornell University, zh: 康奈尔大学}", "org: {zh: 康奈尔大学}"
    )
    with pytest.raises(ValidationError) as excinfo:
        load(write_repo(tmp_path, **{"content/experience.yaml": bad}))
    assert any(p.code == "missing_source_language" for p in excinfo.value.problems)


def test_a_map_with_only_en_declared_rejects_zh(tmp_path):
    """Declaring the language is what makes a map legal; nothing is implicit."""
    with pytest.raises(ValidationError) as excinfo:
        load(write_repo(tmp_path, **{"variants.yaml": VARIANTS_EN_ONLY}))
    assert any(p.code == "undeclared_language" for p in excinfo.value.problems)


# --- Language declarations ---------------------------------------------------


def test_languages_default_to_english_alone(tmp_path):
    plain = EXPERIENCE.replace("{en: Cornell University, zh: 康奈尔大学}", "Cornell University")
    plain = plain.replace("{en: Experience, zh: 工作经历}", "Experience")
    plain = plain.replace("{en: Aug 2024 - Present, zh: 2024年8月 - 至今}", "Aug 2024 - Present")
    plain = plain.replace("      - en: + Research inverse-modeling workflows.\n        zh: 研究反演建模工作流。\n", "      - + Research.\n")
    config = load(
        write_repo(
            tmp_path,
            **{
                "variants.yaml": VARIANTS_EN_ONLY,
                "content/profile.yaml": "name: X\ncontact: []\ntagline: T\n",
                "content/experience.yaml": plain,
                "content/publications.yaml": "title: P\ntype: prose\nitems: [A]\n",
            },
        )
    )
    assert list(config.languages) == ["en"]
    assert config.languages["en"].mainfont == "Garamond"
    assert config.all_renders() == [(l, v, "en") for l, v in config.all_documents()]


def test_declared_languages_carry_typst_code_fonts_and_chrome(tmp_path):
    config = load(write_repo(tmp_path))
    zh = config.languages["zh"]
    assert zh.typst == "zh"
    assert zh.fonts == ("Garamond", "Noto Serif SC")
    assert zh.mainfont == "Garamond"
    assert (zh.sep, zh.colon) == ("，", "：")
    assert config.languages["en"].sep == ", "
    assert len(config.all_renders()) == 2 * len(config.all_documents())
    assert ("long", "general", "zh") in config.all_renders()


def test_languages_without_english_is_an_error(tmp_path):
    bad = VARIANTS.replace("  en: {typst: en, font: Garamond}\n", "")
    with pytest.raises(ValidationError) as excinfo:
        load(write_repo(tmp_path, **{"variants.yaml": bad}))
    assert any(p.code == "missing_source_language" for p in excinfo.value.problems)
