"""The two translation lint rules: a marker in a translation is wrong; an
untranslated string is merely unfinished."""

from pathlib import Path

from cvgen.lint import lint

VARIANTS_ZH = """
languages:
  en: {typst: en, font: Garamond}
  zh: {typst: zh, font: [Garamond, Noto Serif SC]}
short:
  sections: [awards]
  variants:
    general: {}
"""

VARIANTS_EN = """
short:
  sections: [awards]
  variants:
    general: {}
"""

PROFILE_ZH = """
name: {en: Chengxuan Li, zh: 李承轩}
contact:
  - {en: "Email: [you@example.com](mailto:you@example.com)", zh: "邮箱：[you@example.com](mailto:you@example.com)"}
tagline: {en: A tagline, zh: 一句话}
"""

PROFILE_EN = """
name: Chengxuan Li
contact:
  - "Email: [you@example.com](mailto:you@example.com)"
tagline: A tagline
"""


def write(root: Path, awards: str, variants: str = VARIANTS_ZH, profile: str = PROFILE_ZH) -> Path:
    (root / "content").mkdir(parents=True, exist_ok=True)
    (root / "variants.yaml").write_text(variants, encoding="utf-8")
    (root / "content" / "profile.yaml").write_text(profile, encoding="utf-8")
    (root / "content" / "awards.yaml").write_text(awards, encoding="utf-8")
    return root


def test_fully_translated_content_has_no_translation_findings(tmp_path):
    awards = """
title: {en: Awards, zh: 奖项}
type: rows
items:
  - text: {en: "**An award**", zh: "**一个奖项**"}
    date: {en: May 2026, zh: 2026年5月}
"""
    assert lint(write(tmp_path, awards)) == []


def test_untranslated_strings_are_warnings_not_errors(tmp_path):
    awards = """
title: Awards
type: rows
items:
  - text: "**An award**"
    date: May 2026
"""
    findings = lint(write(tmp_path, awards))
    assert findings, "every plain string lacks zh and should be reported"
    assert {f.code for f in findings} == {"untranslated_string"}
    assert not any(f.is_error for f in findings)
    assert {f.field for f in findings} == {"zh"}
    assert {"title", "items[0].text", "items[0].date"} <= {f.path for f in findings}
    assert all(f.line is not None for f in findings)


def test_no_translation_warnings_when_only_english_is_declared(tmp_path):
    awards = """
title: Awards
type: rows
items:
  - text: "**An award**"
"""
    assert lint(write(tmp_path, awards, variants=VARIANTS_EN, profile=PROFILE_EN)) == []


def test_marker_in_a_translation_is_an_error(tmp_path):
    awards = """
title: {en: Awards, zh: 奖项}
type: rows
items:
  - text: {en: "+ **An award**", zh: "+ **一个奖项**"}
    date: {en: May 2026, zh: 2026年5月}
"""
    findings = lint(write(tmp_path, awards))
    errors = [f for f in findings if f.is_error]
    assert [f.code for f in errors] == ["marker_in_translation"]
    assert errors[0].path == "items[0].text.zh"
    assert errors[0].field == "zh"
    assert errors[0].line is not None


def test_translation_rules_stay_quiet_when_content_does_not_load(tmp_path):
    """Structure is the problem then; --check reports it, lint does not pile on."""
    awards = "title: Awards\ntype: bogus\nitems: []\n"
    codes = {f.code for f in lint(write(tmp_path, awards))}
    assert "untranslated_string" not in codes
    assert "marker_in_translation" not in codes
