"""Decide what appears in a document.

This module never formats anything. It answers exactly one question per item:
does it belong in this (length, variant) document?
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .marker import BOTH, GENERAL, Marker
from .schema import Config, Entry, Section


class SelectionError(Exception):
    """A document cannot be assembled."""


@dataclass(frozen=True)
class Document:
    length: str
    variant: str
    name: str
    profile_name: str
    tagline: str
    contact: tuple[str, ...]
    sections: tuple[Section, ...]


def includes(marker: Marker, length: str, variant: str) -> bool:
    """Both gates, in the order the spec states them.

    `general` is an inherited base pool, not a sibling variant: unmarked content
    defaults to `only = (general,)` and therefore flows into every variant.
    """
    tier_ok = marker.tier == BOTH or length == "long"
    variant_ok = GENERAL in marker.only or variant in marker.only
    return tier_ok and variant_ok


def _filter_section(section: Section, length: str, variant: str) -> Section | None:
    kept: list[object] = []
    for item in section.items:
        if not includes(item.marker, length, variant):
            continue
        if isinstance(item, Entry):
            bullets = tuple(b for b in item.bullets if includes(b.marker, length, variant))
            item = replace(item, bullets=bullets)
        kept.append(item)
    if not kept:
        return None
    return replace(section, items=tuple(kept))


def _get_section(config: Config, name: str, length: str, variant: str) -> Section:
    """Fetch a section by name, or raise SelectionError with helpful message."""
    try:
        return config.sections[name]
    except KeyError:
        available = ", ".join(sorted(config.sections.keys()))
        raise SelectionError(
            f"variants.yml: document {length}/{variant} names section '{name}', "
            f"but config.sections has no such section (available: {available})"
        ) from None


def select(config: Config, length: str, variant: str) -> Document:
    """Assemble one document, or raise SelectionError."""
    try:
        order = config.documents[length][variant]
    except KeyError:
        raise SelectionError(f"variants.yml declares no document {length}/{variant}") from None

    sections = tuple(
        filtered
        for name in order
        if (filtered := _filter_section(_get_section(config, name, length, variant), length, variant)) is not None
    )

    tagline = next(
        (t.text for t in config.profile.taglines if includes(t.marker, length, variant)), None
    )
    if tagline is None:
        raise SelectionError(
            f"profile.yml: no tagline survives for document {length}/{variant}"
        )

    return Document(
        length=length,
        variant=variant,
        name=f"cv-{length}-{variant}",
        profile_name=config.profile.name,
        tagline=tagline,
        contact=config.profile.contact,
        sections=sections,
    )
