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
    assert "include-in-header: ../templates/cv.typ" in out
    assert "filters: [../templates/cv.lua]" in out
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


def test_double_quotes_in_dates_attribute_are_escaped():
    """Verify that double quotes in attribute values are escaped to preserve fence syntax."""
    doc = build_doc()
    # Modify the entry dates to include a double quote
    sections = list(doc.sections)
    exp_section = sections[1]
    entries = list(exp_section.items)
    old_entry = entries[0]
    new_entry = Entry(
        old_entry.marker,
        old_entry.org,
        old_entry.location,
        'Jan 2025 - "Current"',  # dates with double quote
        old_entry.role,
        old_entry.bullets,
    )
    entries[0] = new_entry
    sections[1] = Section(
        exp_section.name,
        exp_section.title,
        exp_section.type,
        tuple(entries),
    )
    modified_doc = Document(
        doc.length,
        doc.variant,
        doc.name,
        doc.profile_name,
        doc.tagline,
        doc.contact,
        tuple(sections),
    )

    out = render(modified_doc)
    # Verify the fence is well-formed: the opening line should be parseable
    assert '::: {.cv-entry dates="Jan 2025 - \\"Current\\""}' in out
    # Verify the closing fence still appears and counts match
    assert out.count(":::") == 2 * len([l for l in out.splitlines() if l.startswith("::: {")])


def test_divs_are_balanced_and_correctly_nested():
    """Verify divs are balanced and correctly nested, not just count-matched."""
    out = render(build_doc())

    stack = []
    for line in out.splitlines():
        if line.startswith("::: {"):
            # Extract class name from "::: {.class-name ...}"
            start = line.index(".")
            end = line.index("}", start)
            class_name = line[start:end].split()[0]
            stack.append(class_name)
        elif line.strip() == ":::":
            # Closing fence
            assert stack, "Found closing ::: with no corresponding opening div"
            stack.pop()

    # Verify all divs are closed
    assert not stack, f"Unclosed divs remain on stack: {stack}"

    # Verify the specific nesting contract: .cv-head contains nested .cv-head-left and .cv-head-right
    # Re-walk to check nesting relationships and order
    stack = []
    head_children_order = []
    for line in out.splitlines():
        if line.startswith("::: {"):
            start = line.index(".")
            end = line.index("}", start)
            class_name = line[start:end].split()[0]

            # Verify .cv-head-left and .cv-head-right are only opened when .cv-head is the parent
            if class_name in (".cv-head-left", ".cv-head-right"):
                assert len(stack) > 0 and stack[-1] == ".cv-head", \
                    f"{class_name} must be directly nested inside .cv-head, but stack is {stack}"
                head_children_order.append(class_name)

            stack.append(class_name)
        elif line.strip() == ":::":
            stack.pop()

    # Verify that .cv-head-left appears before .cv-head-right
    assert head_children_order == [".cv-head-left", ".cv-head-right"], \
        f".cv-head children must appear in order [.cv-head-left, .cv-head-right], got {head_children_order}"
