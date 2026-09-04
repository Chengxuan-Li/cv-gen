import json
from pathlib import Path
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


VARIANTS_MIN = """
short:
  sections: [skills]
  variants:
    general: {}
"""
PROFILE_MIN = """
name: X
contact:
  - "Email: [you@example.com](mailto:you@example.com)"
tagline: T
"""
SKILLS_MIN = """
title: Skills
type: labels
items:
  - label: Programming
    text: Python
"""


def write_min_repo(root, local: str | None = None):
    (root / "content").mkdir(parents=True, exist_ok=True)
    (root / "variants.yml").write_text(VARIANTS_MIN, encoding="utf-8")
    (root / "content" / "profile.yml").write_text(PROFILE_MIN, encoding="utf-8")
    (root / "content" / "skills.yml").write_text(SKILLS_MIN, encoding="utf-8")
    if local is not None:
        (root / "content" / "profile.local.yml").write_text(local, encoding="utf-8")
    return root


def test_warns_when_local_profile_is_missing(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(write_min_repo(tmp_path))
    assert build.main(["--check"]) == 0
    err = capsys.readouterr().err
    assert "WARNING" in err
    assert "profile.local.yml" in err
    assert "PLACEHOLDER" in err


def test_reports_source_when_local_profile_is_present(tmp_path, capsys, monkeypatch):
    local = 'contact:\n  - "Email: [real@cornell.edu](mailto:real@cornell.edu)"\n'
    monkeypatch.chdir(write_min_repo(tmp_path, local=local))
    assert build.main(["--check"]) == 0
    captured = capsys.readouterr()
    assert "WARNING" not in captured.err
    assert "content/profile.local.yml" in captured.out


def test_check_json_reports_documents_and_contact_source(tmp_path, capsys, monkeypatch):
    local = 'contact:\n  - "Email: [real@cornell.edu](mailto:real@cornell.edu)"\n'
    monkeypatch.chdir(write_min_repo(tmp_path, local=local))
    assert build.main(["--check", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["documents"] == ["short/general"]
    assert payload["contact_source"] == "content/profile.local.yml"


def test_check_json_emits_structured_problems_with_codes(tmp_path, capsys, monkeypatch):
    root = write_min_repo(tmp_path)
    (root / "content" / "skills.yml").write_text(
        "title: Skills\ntype: bogus\nitems: []\n", encoding="utf-8"
    )
    monkeypatch.chdir(root)
    assert build.main(["--check", "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    codes = [p["code"] for p in payload["problems"]]
    assert "unknown_block_type" in codes
    problem = next(p for p in payload["problems"] if p["code"] == "unknown_block_type")
    assert problem["file"] == "skills.yml"
    assert problem["line"] == 2
    assert problem["hint"]


def test_lint_exits_nonzero_on_findings(tmp_path, capsys, monkeypatch):
    root = write_min_repo(tmp_path)
    (root / "content" / "skills.yml").write_text(
        'title: Skills\ntype: labels\nitems:\n  - label: P\n    text: "+Python"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(root)
    assert build.main(["--lint", "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["findings"][0]["code"] == "near_miss_marker"


def test_lint_is_clean_on_valid_content(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(write_min_repo(tmp_path))
    assert build.main(["--lint"]) == 0
    assert "clean" in capsys.readouterr().out


def test_explain_json_shape(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(write_min_repo(tmp_path))
    assert build.main(["--explain", "short/general", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["document"] == "short/general"
    item = payload["items"][0]
    assert item["path"] == "skills/items[0]"
    assert item["included"] is True
    assert item["marker"] == {"tier": "both", "only": ["general"]}


def test_explain_rejects_a_malformed_document_spec(tmp_path, monkeypatch):
    monkeypatch.chdir(write_min_repo(tmp_path))
    with pytest.raises(SystemExit):
        build.main(["--explain", "short"])


def test_explain_unknown_document_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.chdir(write_min_repo(tmp_path))
    assert build.main(["--explain", "long/nope"]) == 1


def test_schema_writes_every_file(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert build.main(["--schema", "--json"]) == 0
    written = json.loads(capsys.readouterr().out)["written"]
    assert len(written) == 3
    for path in written:
        assert Path(path).exists()
