"""Parse the marker token that prefixes a content item.

    marker := ('+' | '-') ( '[' names ']' )?     must be followed by whitespace

The trailing-whitespace requirement is what keeps this grammar from colliding
with markdown. A markdown link's ']' is always followed by '(', never a space,
so '-[ShadingZip](url) is a tool' is plain text and needs no escaping.

Do not relax that rule. Doing so silently corrupts any item beginning with a
link.
"""

from __future__ import annotations

from dataclasses import dataclass

GENERAL = "general"
LONG = "long"
BOTH = "both"

_TIERS = {"+": LONG, "-": BOTH}


class MarkerError(ValueError):
    """A marker token is malformed."""


@dataclass(frozen=True)
class Marker:
    tier: str = BOTH
    only: tuple[str, ...] = (GENERAL,)


@dataclass(frozen=True)
class Marked:
    marker: Marker
    text: str


DEFAULT = Marker()


def _names(raw: str) -> tuple[str, ...]:
    return tuple(name.strip() for name in raw.split(",") if name.strip())


def parse_item(raw: str) -> Marked:
    """Split a content string into its marker and its text."""
    if raw[:2] in ("\\+", "\\-"):
        return Marked(DEFAULT, raw[1:])

    tier = _TIERS.get(raw[:1])
    if tier is None:
        return Marked(DEFAULT, raw)

    rest = raw[1:]

    if rest.startswith("["):
        close = rest.find("]")
        if close == -1:
            raise MarkerError(f"unclosed '[' in marker: {raw!r}")
        after = rest[close + 1 :]
        if not after[:1].isspace():
            # ']' is followed by '(' or similar: a markdown link, not a marker.
            return Marked(DEFAULT, raw)
        return Marked(Marker(tier, _names(rest[1:close])), after.strip())

    if rest[:1].isspace():
        return Marked(Marker(tier, (GENERAL,)), rest.strip())

    # '-5%' and friends: a sign, not a marker.
    return Marked(DEFAULT, raw)


def parse_mark(raw: str | None) -> Marker:
    """Parse a bare `mark:` field, which carries a marker and no text."""
    if raw is None:
        return DEFAULT

    text = raw.strip()
    tier = _TIERS.get(text[:1])
    if tier is None:
        raise MarkerError(f"mark must start with '+' or '-': {raw!r}")

    rest = text[1:]
    if not rest:
        return Marker(tier, (GENERAL,))
    if not (rest.startswith("[") and rest.endswith("]")):
        raise MarkerError(f"mark must be '+', '-' or '+[names]': {raw!r}")
    return Marker(tier, _names(rest[1:-1]))
