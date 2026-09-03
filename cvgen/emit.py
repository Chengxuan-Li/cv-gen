"""Turn a selected Document into Quarto markdown.

This module never decides *what* appears - only how it is written. Content is
emitted as markdown inside fenced divs; templates/cv.lua converts those divs
into Typst calls, which is what lets bold, italics and links survive Pandoc.
"""

from __future__ import annotations

from .schema import Entry, Item, Label, Section
from .select import Document

FRONT_MATTER = """---
title: "{title}"
format:
  typst:
    papersize: us-letter
    margin:
      x: 1.6cm
      y: 1.4cm
    mainfont: Arial
    fontsize: 10pt
    include-in-header: {template_dir}/cv.typ
    filters: [{template_dir}/cv.lua]
---
"""


def _div(classes: str, body: list[str], **attrs: str) -> list[str]:
    rendered = "".join(f' {k}="{v}"' for k, v in attrs.items() if v)
    return [f"::: {{{classes}{rendered}}}", *body, ":::", ""]


def _head(doc: Document) -> list[str]:
    left = _div(".cv-head-left", [f"# {doc.profile_name}", "", doc.tagline])
    # Two trailing spaces make each contact line a markdown hard line break.
    right = _div(".cv-head-right", [f"{line}  " for line in doc.contact])
    return _div(".cv-head", [*left, *right])


def _labels(items: tuple[object, ...]) -> list[str]:
    lines = [f"**{i.label}**: {i.text}  " for i in items if isinstance(i, Label)]
    return _div(".cv-labels", lines)


def _entry(entry: Entry) -> list[str]:
    body = [f"**{entry.org}**, {entry.location}", "", f"*{entry.role}*"]
    if entry.bullets:
        body += ["", *[f"- {b.text}" for b in entry.bullets]]
    return _div(".cv-entry", body, dates=entry.dates)


def _section(section: Section) -> list[str]:
    lines = [f"## {section.title}", ""]
    if section.type == "labels":
        return lines + _labels(section.items)
    for item in section.items:
        if section.type == "entries":
            lines += _entry(item)
        elif section.type == "rows":
            lines += _div(".cv-row", [item.text], dates=item.date)
        else:  # prose
            lines += _div(".cv-prose", [item.text])
    return lines


def render(doc: Document, template_dir: str = "templates") -> str:
    """Render a document as Quarto markdown."""
    lines = [
        FRONT_MATTER.format(title=doc.profile_name, template_dir=template_dir),
        *_head(doc),
    ]
    for section in doc.sections:
        lines += _section(section)
    return "\n".join(lines).rstrip() + "\n"
