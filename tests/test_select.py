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


def test_missing_section_in_document_order_raises():
    config = build_config()
    broken = Config(
        config.profile,
        config.sections,
        {
            "long": {"general": ("skills", "missing", "experience"), "gev-pos-1": ("experience", "skills")},
            "short": {"general": ("skills", "experience")},
        },
    )
    with pytest.raises(SelectionError) as excinfo:
        select(broken, "long", "general")
    assert "missing" in str(excinfo.value)
    assert "long/general" in str(excinfo.value)
    assert "awards" in str(excinfo.value) or "experience" in str(excinfo.value)
