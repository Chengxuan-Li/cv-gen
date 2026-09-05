from pathlib import Path

from cvgen.lint import lint

PROFILE_PLACEHOLDER = """
name: Chengxuan Li
contact:
  - "Email: [you@example.com](mailto:you@example.com)"
  - "Phone: +1 (555) 000-0000"
tagline: A tagline
"""

VARIANTS = """
short:
  sections: [awards]
  variants:
    general: {}
"""


def write(root: Path, awards: str, profile: str = PROFILE_PLACEHOLDER) -> Path:
    (root / "content").mkdir(parents=True, exist_ok=True)
    (root / "variants.yaml").write_text(VARIANTS, encoding="utf-8")
    (root / "content" / "profile.yaml").write_text(profile, encoding="utf-8")
    (root / "content" / "awards.yaml").write_text(awards, encoding="utf-8")
    return root


def codes(findings):
    return [f.code for f in findings]


def test_clean_content_produces_no_findings(tmp_path):
    awards = """
title: Awards
type: rows
items:
  - text: "**An award** *Winner*"
    date: May 2026
"""
    assert lint(write(tmp_path, awards)) == []


def test_near_miss_marker_is_flagged_with_a_line(tmp_path):
    awards = """
title: Awards
type: rows
items:
  - text: "+Long-only award"
    date: May 2026
"""
    findings = lint(write(tmp_path, awards))
    assert codes(findings) == ["near_miss_marker"]
    assert findings[0].line == 5
    assert findings[0].path == "items[0].text"
    assert "\\+" in findings[0].hint


def test_a_real_marker_is_not_flagged(tmp_path):
    awards = """
title: Awards
type: rows
items:
  - text: "+ Long-only award"
    date: May 2026
  - text: "+[general] Targeted award"
    date: May 2026
"""
    assert lint(write(tmp_path, awards)) == []


def test_leading_minus_before_a_digit_is_not_flagged(tmp_path):
    """'-5% peak load reduction' is ordinary content, not a broken marker."""
    awards = """
title: Awards
type: rows
items:
  - text: "-5% peak load reduction achieved"
    date: May 2026
"""
    assert lint(write(tmp_path, awards)) == []


def test_placeholder_phone_number_is_not_flagged(tmp_path):
    """'+1 (555) 000-0000' starts with '+' but is a phone number, not a marker."""
    awards = """
title: Awards
type: rows
items:
  - text: "An award"
"""
    assert lint(write(tmp_path, awards)) == []


def test_real_looking_contact_in_the_tracked_profile_is_flagged(tmp_path):
    real = """
name: Chengxuan Li
contact:
  - "Email: [someone@cornell.edu](mailto:someone@cornell.edu)"
tagline: A tagline
"""
    awards = """
title: Awards
type: rows
items:
  - text: "An award"
"""
    findings = lint(write(tmp_path, awards, profile=real))
    assert codes(findings) == ["real_contact_in_tracked_profile"]
    assert findings[0].path == "contact[0]"
    assert "profile.local.yaml" in findings[0].message


def test_the_untracked_local_profile_is_never_linted(tmp_path):
    """It is supposed to hold real details - flagging it would be backwards."""
    awards = """
title: Awards
type: rows
items:
  - text: "An award"
"""
    root = write(tmp_path, awards)
    (root / "content" / "profile.local.yaml").write_text(
        'contact:\n  - "Email: [real@cornell.edu](mailto:real@cornell.edu)"\n', encoding="utf-8"
    )
    assert lint(root) == []


def test_the_real_repository_has_no_lint_errors():
    """Warnings are allowed: with zh declared, every untranslated string is one.
    Errors are not - they mean the content is wrong rather than unfinished."""
    findings = lint(Path(__file__).resolve().parent.parent)
    assert [f for f in findings if f.is_error] == []


AWARD = """
title: Awards
type: rows
items:
  - text: "An award"
"""


def profile_with(*contact: str) -> str:
    lines = [f'  - "{c}"' for c in contact]
    return "\n".join(["name: Chengxuan Li", "contact:", *lines, "tagline: A tagline", ""])


def test_a_public_url_in_the_tracked_profile_is_not_flagged(tmp_path):
    """A personal site is not sensitive - it belongs in the tracked file."""
    profile = profile_with(
        "Email: [you@example.com](mailto:you@example.com)",
        "Phone: +1 (555) 000-0000",
        "Web: [chengxuan-li.github.io](https://chengxuan-li.github.io)",
    )
    assert lint(write(tmp_path, AWARD, profile=profile)) == []


def test_a_real_phone_number_is_flagged(tmp_path):
    profile = profile_with("Phone: +1 (607) 227 5495")
    findings = lint(write(tmp_path, AWARD, profile=profile))
    assert codes(findings) == ["real_contact_in_tracked_profile"]
    assert "phone number" in findings[0].message


def test_a_real_email_is_flagged_and_names_the_domain(tmp_path):
    profile = profile_with("Email: [a@cornell.edu](mailto:a@cornell.edu)")
    findings = lint(write(tmp_path, AWARD, profile=profile))
    assert "cornell.edu" in findings[0].message


def test_placeholder_email_and_phone_are_not_flagged(tmp_path):
    profile = profile_with(
        "Email: [you@example.com](mailto:you@example.com)",
        "Phone: +1 (555) 000-0000",
    )
    assert lint(write(tmp_path, AWARD, profile=profile)) == []
