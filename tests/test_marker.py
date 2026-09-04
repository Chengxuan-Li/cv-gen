import pytest

from cvgen.marker import BOTH, GENERAL, LONG, Marker, MarkerError, parse_item, parse_mark


@pytest.mark.parametrize(
    "raw, tier, only, text",
    [
        # Markers, in every shape.
        ("+[gev-pos-1] Research inverse modeling", LONG, ("gev-pos-1",), "Research inverse modeling"),
        ("+[a,b] Text", LONG, ("a", "b"), "Text"),
        ("+[ a , b ] Spaces in the list", LONG, ("a", "b"), "Spaces in the list"),
        ("+ Research inverse modeling", LONG, (GENERAL,), "Research inverse modeling"),
        ("- Shared bullet", BOTH, (GENERAL,), "Shared bullet"),
        ("-[a] Shared but targeted", BOTH, ("a",), "Shared but targeted"),
        # An empty list reaches nothing, per spec.
        ("+[] Reaches nothing", LONG, (), "Reaches nothing"),
        # No marker.
        ("Develop load profile inference methods.", BOTH, (GENERAL,), "Develop load profile inference methods."),
        # Markdown collisions. Each of these is a real construct that must survive.
        ("-[ShadingZip](https://x) is a tool", BOTH, (GENERAL,), "-[ShadingZip](https://x) is a tool"),
        ("[ShadingZip](https://x) is a tool", BOTH, (GENERAL,), "[ShadingZip](https://x) is a tool"),
        ("**Nemetschek Award** *Second place*", BOTH, (GENERAL,), "**Nemetschek Award** *Second place*"),
        ("-5% peak load reduction", BOTH, (GENERAL,), "-5% peak load reduction"),
        # The space after '+' is required. '+Research' is NOT a marker - it is
        # literal text with a stray '+'. Easy to get wrong, and it fails
        # silently in the rendered PDF, so it is pinned here.
        ("+Research inverse modeling", BOTH, (GENERAL,), "+Research inverse modeling"),
        ("-Shared bullet", BOTH, (GENERAL,), "-Shared bullet"),
        # Escapes for a literal leading '+ ' or '- '.
        ("\\+ Literal plus", BOTH, (GENERAL,), "+ Literal plus"),
        ("\\- Literal minus", BOTH, (GENERAL,), "- Literal minus"),
    ],
)
def test_parse_item(raw, tier, only, text):
    marked = parse_item(raw)
    assert marked.marker.tier == tier
    assert marked.marker.only == only
    assert marked.text == text


def test_parse_item_unclosed_bracket_raises():
    with pytest.raises(MarkerError) as excinfo:
        parse_item("+[gev-pos-1 Research inverse modeling")
    assert "unclosed" in str(excinfo.value).lower()


@pytest.mark.parametrize(
    "raw, tier, only",
    [
        (None, BOTH, (GENERAL,)),
        ("+", LONG, (GENERAL,)),
        ("-", BOTH, (GENERAL,)),
        ("+[gev-pos-1]", LONG, ("gev-pos-1",)),
        ("-[a,b]", BOTH, ("a", "b")),
    ],
)
def test_parse_mark(raw, tier, only):
    marker = parse_mark(raw)
    assert marker.tier == tier
    assert marker.only == only


@pytest.mark.parametrize("raw", ["+[a] extra text", "gev-pos-1", "+[a", ""])
def test_parse_mark_rejects_malformed(raw):
    with pytest.raises(MarkerError):
        parse_mark(raw)


def test_marker_is_hashable():
    assert Marker() == Marker()
    assert len({Marker(), Marker()}) == 1
