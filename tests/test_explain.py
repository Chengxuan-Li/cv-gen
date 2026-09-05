import pytest

from cvgen.explain import TIER, VARIANT, explain, render
from cvgen.marker import BOTH, GENERAL, LONG, Marker
from cvgen.schema import Config, Entry, Item, Label, Profile, Section
from cvgen.select import SelectionError


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
                    Item(Marker(LONG, (GENERAL,)), "Long-only bullet"),
                ),
            ),
            Entry(
                Marker(LONG, (GENERAL,)),
                "Dropped In Short",
                "London",
                "2023",
                "Consultant",
                (Item(Marker(), "A bullet nobody should see in short"),),
            ),
            Entry(Marker(BOTH, ("gev-pos-1",)), "Targeted", "London", "2022", "Intern", ()),
        ),
    )
    skills = Section(
        "skills", "Technical Skills", "labels", (Label(Marker(), "Programming", "Python"),)
    )
    profile = Profile("X", ("Email: x",), (Item(Marker(), "T"),))
    return Config(
        profile,
        {"experience": experience, "skills": skills},
        {
            "long": {"general": ("skills", "experience"), "gev-pos-1": ("skills", "experience")},
            "short": {"general": ("skills", "experience")},
        },
    )


def by_path(decisions):
    return {d.path: d for d in decisions}


def test_long_only_entry_is_excluded_from_short_by_the_tier_gate():
    d = by_path(explain(build_config(), "short", "general"))["experience/entries[1]"]
    assert d.included is False
    assert d.reason == TIER
    assert "long-only" in d.explanation


def test_targeted_entry_is_excluded_from_general_by_the_variant_gate():
    d = by_path(explain(build_config(), "long", "general"))["experience/entries[2]"]
    assert d.included is False
    assert d.reason == VARIANT
    assert "gev-pos-1" in d.explanation


def test_targeted_entry_is_included_in_its_own_variant():
    d = by_path(explain(build_config(), "long", "gev-pos-1"))["experience/entries[2]"]
    assert d.included is True
    assert "gev-pos-1" in d.explanation


def test_bullets_of_an_excluded_entry_are_not_reported_separately():
    """They were never judged on their own markers, so reporting them would lie."""
    paths = by_path(explain(build_config(), "short", "general"))
    assert "experience/entries[1]" in paths
    assert "experience/entries[1].bullets[0]" not in paths
    # A surviving entry's bullets ARE judged individually.
    assert "experience/entries[0].bullets[1]" in paths


def test_long_only_bullet_under_a_surviving_entry():
    paths = by_path(explain(build_config(), "short", "general"))
    assert paths["experience/entries[0].bullets[0]"].included is True
    assert paths["experience/entries[0].bullets[1]"].included is False
    assert paths["experience/entries[0].bullets[1]"].reason == TIER


def test_sections_are_walked_in_document_order():
    config = build_config()
    config.documents["long"]["general"] = ("experience", "skills")
    order = [d.path.split("/")[0] for d in explain(config, "long", "general")]
    assert order[0] == "experience"
    assert order[-1] == "skills"


def test_unknown_document_raises():
    with pytest.raises(SelectionError):
        explain(build_config(), "long", "nope")


def test_render_marks_exclusions_visibly():
    text = render(explain(build_config(), "short", "general"))
    assert "EXCLUDE" in text
    assert "gate=tier" in text


# --- Localization -----------------------------------------------------------

from cvgen.localize import LStr, language_spec  # noqa: E402


def build_zh_config() -> Config:
    """One entry fully translated, one only partly, one not at all."""
    experience = Section(
        "experience",
        LStr("Experience", {"zh": "经历"}),
        "entries",
        (
            Entry(
                Marker(),
                LStr("Cornell", {"zh": "康奈尔"}),
                LStr("Ithaca NY", {"zh": "伊萨卡"}),
                LStr("Aug 2024", {"zh": "2024年8月"}),
                LStr("PhD Researcher", {"zh": "博士研究员"}),
                (
                    Item(Marker(), LStr("Translated bullet", {"zh": "已翻译"})),
                    Item(Marker(), LStr("Untranslated bullet")),
                ),
            ),
            Entry(
                Marker(),
                LStr("Partly", {"zh": "部分"}),
                LStr("London"),  # no zh: the entry falls back
                LStr("2023", {"zh": "2023年"}),
                LStr("Consultant", {"zh": "顾问"}),
                (),
            ),
            Entry(Marker(LONG, (GENERAL,)), LStr("Long only"), LStr("X"), LStr("Y"), LStr("Z"), ()),
        ),
    )
    profile = Profile(LStr("X"), (LStr("Email: x"),), (Item(Marker(), LStr("T")),))
    return Config(
        profile,
        {"experience": experience},
        {"long": {"general": ("experience",)}, "short": {"general": ("experience",)}},
        {
            "en": language_spec("en", {"typst": "en", "font": "Garamond"}),
            "zh": language_spec("zh", {"typst": "zh", "font": ["Garamond", "Noto Serif SC"]}),
        },
    )


def test_english_never_falls_back():
    assert not any(d.fallback for d in explain(build_zh_config(), "long", "general"))
    assert not any(d.fallback for d in explain(build_zh_config(), "long", "general", "en"))


def test_chinese_marks_exactly_the_items_that_fall_back():
    decisions = by_path(explain(build_zh_config(), "long", "general", "zh"))
    assert decisions["experience/entries[0]"].fallback is False  # fully translated
    assert decisions["experience/entries[0].bullets[0]"].fallback is False
    assert decisions["experience/entries[0].bullets[1]"].fallback is True
    assert decisions["experience/entries[1]"].fallback is True  # location untranslated
    assert decisions["experience/entries[2]"].fallback is True  # nothing translated


def test_language_does_not_change_inclusion():
    """Translation decides how an item reads, never whether it is in."""
    en = [(d.path, d.included) for d in explain(build_zh_config(), "short", "general", "en")]
    zh = [(d.path, d.included) for d in explain(build_zh_config(), "short", "general", "zh")]
    assert en == zh
    excluded = by_path(explain(build_zh_config(), "short", "general", "zh"))["experience/entries[2]"]
    assert excluded.included is False and excluded.fallback is False


def test_undeclared_language_raises():
    with pytest.raises(SelectionError) as excinfo:
        explain(build_zh_config(), "long", "general", "fr")
    assert "zh" in str(excinfo.value)


def test_render_flags_fallbacks():
    text = render(explain(build_zh_config(), "long", "general", "zh"))
    assert text.count("[falls back to en]") == 3
    assert "experience/entries[0].bullets[1]" in text
