from cvgen.emit import render
from cvgen.marker import Marker
from cvgen.schema import Entry, Item, Label, Section
from cvgen.select import Document


def build_doc() -> Document:
    return Document(
        length="long",
        variant="general",
        name="cv-long-general",
        profile_name="Chengxuan Li",
        tagline="PhD Candidate in Systems Engineering",
        contact=("Email: [x@y.edu](mailto:x@y.edu)", "Phone: +1 (607) 227 5495"),
        sections=(
            Section("skills", "Technical Skills", "labels", (Label(Marker(), "Programming", "Python, C#"),)),
            Section(
                "experience",
                "Experience",
                "entries",
                (
                    Entry(
                        Marker(),
                        "EnergyAtlas.io",
                        "Ithaca NY",
                        "Jan 2025 - Current",
                        "Lead Developer",
                        (Item(Marker(), "Lead **development** of a [twin](https://x)."),),
                    ),
                ),
            ),
            Section("awards", "Awards & Grants", "rows", (Item(Marker(), "**An award**", "May 2026"),)),
            Section("publications", "Selected Publications", "prose", (Item(Marker(), 'Li, C. "Paper." DOI: [10.1](https://x)'),)),
        ),
    )


def test_front_matter_wires_up_the_templates():
    out = render(build_doc())
    assert out.startswith("---\n")
    assert "format:" in out
    assert "typst:" in out
    assert "include-in-header: templates/cv.typ" in out
    assert "filters: [templates/cv.lua]" in out
    assert "format: pdf" not in out  # never LaTeX


def test_head_carries_name_tagline_and_contact():
    out = render(build_doc())
    assert "::: {.cv-head}" in out
    assert "::: {.cv-head-left}" in out
    assert "# Chengxuan Li" in out
    assert "PhD Candidate in Systems Engineering" in out
    assert "::: {.cv-head-right}" in out
    assert "Email: [x@y.edu](mailto:x@y.edu)  " in out  # hard line break


def test_sections_render_in_order_with_headings():
    out = render(build_doc())
    assert out.index("## Technical Skills") < out.index("## Experience")
    assert out.index("## Experience") < out.index("## Awards & Grants")


def test_entry_div_carries_dates_and_markdown_survives():
    out = render(build_doc())
    assert '::: {.cv-entry dates="Jan 2025 - Current"}' in out
    assert "**EnergyAtlas.io**, Ithaca NY" in out
    assert "*Lead Developer*" in out
    assert "- Lead **development** of a [twin](https://x)." in out


def test_row_and_prose_and_labels():
    out = render(build_doc())
    assert '::: {.cv-row dates="May 2026"}' in out
    assert "::: {.cv-prose}" in out
    assert '"Paper." DOI: [10.1](https://x)' in out
    assert "::: {.cv-labels}" in out
    assert "**Programming**: Python, C#" in out


def test_every_div_is_closed():
    out = render(build_doc())
    assert out.count(":::") == 2 * len([l for l in out.splitlines() if l.startswith("::: {")])
