from cvgen.diagnostics import Problem, format_path, line_index

DOC = """title: Experience
type: entries
entries:
  - org: Cornell
    location: Ithaca NY
  - org: EnergyAtlas.io
    bullets:
      - first
      - second
"""


def test_format_path():
    assert format_path(()) == ""
    assert format_path(("entries",)) == "entries"
    assert format_path(("entries", 0)) == "entries[0]"
    assert format_path(("entries", 0, "org")) == "entries[0].org"
    assert format_path(("entries", 1, "bullets", 2)) == "entries[1].bullets[2]"


def test_line_index_anchors_each_path():
    index = line_index(DOC)
    assert index[("title",)] == 1
    assert index[("entries", 0)] == 4
    assert index[("entries", 0, "location")] == 5
    assert index[("entries", 1)] == 6
    assert index[("entries", 1, "bullets", 1)] == 9


def test_line_index_survives_malformed_yaml():
    # A broken file still needs to report problems, just without line anchors.
    assert line_index("a: [unclosed") == {}
    assert line_index("") == {}


def test_problem_as_dict_omits_empty_fields():
    bare = Problem(file="a.yaml", code="empty_file", message="a.yaml: empty file")
    assert bare.as_dict() == {"file": "a.yaml", "code": "empty_file", "message": "a.yaml: empty file"}

    full = Problem(
        file="a.yaml",
        code="missing_required_field",
        message="a.yaml: entry 0: missing required field 'org'",
        line=4,
        path="entries[0]",
        field="org",
        hint="entries requires: org",
    )
    assert full.as_dict()["line"] == 4
    assert full.as_dict()["field"] == "org"
    assert str(full) == full.message
