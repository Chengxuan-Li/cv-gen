import pytest

import build
from cvgen.schema import Config, Item, Profile, Section
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


def test_check_catches_selection_errors_after_schema_passes(tmp_path, capsys, monkeypatch):
    # Schema-valid content: variants.yml and profile.yml both parse fine, and
    # 'skills' has a content file, so load() alone would pass. But the tagline
    # is marked long-only ("+") while the only declared document is "short",
    # so no tagline survives select() for short/general.
    (tmp_path / "content").mkdir()
    (tmp_path / "variants.yml").write_text(
        "short:\n  sections: [skills]\n  variants:\n    general: {}\n", encoding="utf-8"
    )
    (tmp_path / "content" / "profile.yml").write_text(
        "name: X\ntagline: '+ T'\n", encoding="utf-8"
    )
    (tmp_path / "content" / "skills.yml").write_text(
        "type: prose\nitems:\n  - some skill\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    assert build.main(["--check"]) == 1
    err = capsys.readouterr().err
    assert "short/general" in err
    assert not (tmp_path / ".build").exists()
    assert not (tmp_path / "out").exists()


def test_build_one_raises_when_quarto_produces_no_pdf(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(build.subprocess, "run", lambda *a, **k: None)

    config = Config(
        Profile("X", (), (Item(Marker(), "T"),)),
        {"skills": Section("skills", "Skills", "prose", (Item(Marker(), "Some skill"),))},
        {"long": {"general": ("skills",)}},
    )

    with pytest.raises(build.BuildError) as excinfo:
        build.build_one(config, "fake-quarto", "long", "general")
    assert "long/general" in str(excinfo.value)


def test_long_and_short_together_is_rejected():
    with pytest.raises(SystemExit):
        build.main(["--all", "--long", "--short"])
