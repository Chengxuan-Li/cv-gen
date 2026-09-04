"""Explain why each item does or does not appear in a document.

The two inclusion gates are the product's core semantics and, until now, the
only way to confirm them was to render a PDF and read it. This makes the
decision inspectable directly: for every item, which gate decided it and why.
"""

from __future__ import annotations

from dataclasses import dataclass

from .marker import BOTH, GENERAL, Marker
from .schema import Config, Entry, Label, Section
from .select import SelectionError

PASS = "pass"
TIER = "tier"
VARIANT = "variant"


@dataclass(frozen=True)
class Decision:
    path: str
    label: str
    included: bool
    reason: str
    tier: str
    only: tuple[str, ...]
    explanation: str

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "label": self.label,
            "included": self.included,
            "reason": self.reason,
            "marker": {"tier": self.tier, "only": list(self.only)},
            "explanation": self.explanation,
        }


def _decide(marker: Marker, length: str, variant: str) -> tuple[bool, str, str]:
    tier_ok = marker.tier == BOTH or length == "long"
    variant_ok = GENERAL in marker.only or variant in marker.only
    if not tier_ok:
        return False, TIER, f"tier '+' is long-only, this document is {length}"
    if not variant_ok:
        listed = ", ".join(marker.only) or "(none)"
        return False, VARIANT, f"only=[{listed}] excludes '{variant}' and lacks '{GENERAL}'"
    if marker.only == (GENERAL,):
        return True, PASS, f"unmarked, so inherited from the '{GENERAL}' base pool"
    return True, PASS, f"targets '{variant}'"


def _label(item: object) -> str:
    if isinstance(item, Entry):
        return item.org
    if isinstance(item, Label):
        return item.label
    text = getattr(item, "text", "")
    return text if len(text) <= 60 else text[:57] + "..."


def _items_key(section: Section) -> str:
    return "entries" if section.type == "entries" else "items"


def explain(config: Config, length: str, variant: str) -> list[Decision]:
    """Every item's fate in one document, in document order.

    Sections are walked in the document's own order. A section absent from that
    order is not reported at all - it was never a candidate.
    """
    try:
        order = config.documents[length][variant]
    except KeyError:
        raise SelectionError(f"variants.yml declares no document {length}/{variant}") from None

    out: list[Decision] = []
    for name in order:
        section = config.sections.get(name)
        if section is None:
            continue
        key = _items_key(section)
        for index, item in enumerate(section.items):
            included, reason, why = _decide(item.marker, length, variant)
            out.append(
                Decision(
                    path=f"{name}/{key}[{index}]",
                    label=_label(item),
                    included=included,
                    reason=reason,
                    tier=item.marker.tier,
                    only=item.marker.only,
                    explanation=why,
                )
            )
            if not included:
                # A failing container removes its children; reporting each one
                # separately would imply they were judged on their own markers.
                continue
            for b_index, bullet in enumerate(getattr(item, "bullets", ())):
                b_included, b_reason, b_why = _decide(bullet.marker, length, variant)
                out.append(
                    Decision(
                        path=f"{name}/{key}[{index}].bullets[{b_index}]",
                        label=_label(bullet),
                        included=b_included,
                        reason=b_reason,
                        tier=bullet.marker.tier,
                        only=bullet.marker.only,
                        explanation=b_why,
                    )
                )
    return out


def render(decisions: list[Decision]) -> str:
    """Fixed-width text form, aligned so the include/exclude column scans."""
    if not decisions:
        return "(no items)"
    width = max(len(d.path) for d in decisions)
    lines = []
    for d in decisions:
        verdict = "include" if d.included else "EXCLUDE"
        gate = "" if d.included else f" gate={d.reason}"
        lines.append(f"  {d.path:<{width}}  {verdict}{gate}  {d.explanation}")
    return "\n".join(lines)
