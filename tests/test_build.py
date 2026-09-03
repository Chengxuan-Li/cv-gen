import pytest

import build
from cvgen.schema import Config, Item, Profile
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
