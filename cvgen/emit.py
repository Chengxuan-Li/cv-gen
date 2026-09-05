"""Turn a selected Document into Quarto markdown, in one language.

This module never decides *what* appears - only how it is written. Content is
emitted as markdown inside fenced divs; templates/cv.lua converts those divs
into Typst calls, which is what lets bold, italics and links survive Pandoc.

Language is resolved here and nowhere else. Every translatable value arrives as
an LStr whose str value is the English source; `render()` asks each one for the
target language and falls back to the source when there is no translation. The
punctuation and fixed labels written around content - the comma between org and
location, the colon after a skill label - come from the language too, since
Chinese uses full-width forms.
"""

from __future__ import annotations

from .localize import LanguageSpec, LStr, default_languages
from .schema import Entry, Label, Section
from .select import Document

# `mainfont` is deliberately absent. Quarto rejects a YAML list for it, and a
# single font cannot carry a CJK fallback. With it omitted, Quarto's own
# `set text(font: font) if font != none` is a no-op and the font stack is set by
# a raw Typst block at the top of the body instead - see render(). `lang` is a
# top-level Quarto key and drives Typst's line-breaking, which matters for
# Chinese: there are no spaces to wrap at.
FRONT_MATTER = """---
lang: {lang}
format:
  typst:
    papersize: us-letter
    margin:
      x: 1.6cm
      y: 1.4cm
    fontsize: 10pt
    include-in-header: {template_dir}/cv.typ
    filters: [{template_dir}/cv.lua]
---
"""

FONT_BLOCK = """```{{=typst}}
#set text(font: ({fonts}))
```
"""


def _t(value: object, lang: str) -> str:
    """The text of a translatable value in `lang`, or the source if it has none."""
    if isinstance(value, LStr):
        return value.in_(lang)
    return "" if value is None else str(value)


def _div(classes: str, body: list[str], **attrs: str) -> list[str]:
    # Escaping is hoisted into a plain variable (rather than nested inside the
    # f-string expression below) because Python < 3.12 cannot parse an
    # f-string expression that reuses its own quote character.
    parts = []
    for k, v in attrs.items():
        if not v:
            continue
        escaped = v.replace('"', '\\"')
        parts.append(f' {k}="{escaped}"')
    rendered = "".join(parts)
    return [f"::: {{{classes}{rendered}}}", *body, ":::", ""]


def _head(doc: Document, lang: LanguageSpec) -> list[str]:
    code = lang.code
    name = f"# {_t(doc.profile_name, code)}"
    graduation = _t(doc.anticipated_graduation, code)
    if graduation:
        name += f" [{lang.graduation}{lang.colon}{graduation}]{{.cv-graduation}}"
    left = _div(".cv-head-left", [name, "", _t(doc.tagline, code)])
    # Two trailing spaces make each contact line a markdown hard line break.
    right = _div(".cv-head-right", [f"{_t(line, code)}  " for line in doc.contact])
    return _div(".cv-head", [*left, *right])


def _labels(items: tuple[object, ...], lang: LanguageSpec) -> list[str]:
    """One paragraph per label, separated by a blank line.

    These were previously joined with markdown hard line breaks, which made the
    whole section a single paragraph: every label sat at the template's line
    height, the spacing meant for *wrapped* lines, so separate skills read as if
    they were continuations of one another. A blank line makes each its own
    paragraph and lets the wider paragraph gap apply.
    """
    body: list[str] = []
    for item in items:
        if not isinstance(item, Label):
            continue
        if body:
            body.append("")
        body.append(f"**{_t(item.label, lang.code)}**{lang.colon}{_t(item.text, lang.code)}")
    return _div(".cv-labels", body)


def _entry(entry: Entry, lang: LanguageSpec) -> list[str]:
    code = lang.code
    body = [
        f"**{_t(entry.org, code)}**{lang.sep}{_t(entry.location, code)}",
        "",
        f"*{_t(entry.role, code)}*",
    ]
    if entry.bullets:
        body += ["", *[f"- {_t(b.text, code)}" for b in entry.bullets]]
    return _div(".cv-entry", body, dates=_t(entry.dates, code))


def _section(section: Section, lang: LanguageSpec) -> list[str]:
    code = lang.code
    lines = [f"## {_t(section.title, code)}", ""]
    if section.type == "labels":
        return lines + _labels(section.items, lang)
    for item in section.items:
        if section.type == "entries":
            lines += _entry(item, lang)
        elif section.type == "rows":
            lines += _div(".cv-row", [_t(item.text, code)], dates=_t(item.date, code))
        else:  # prose
            lines += _div(".cv-prose", [_t(item.text, code)])
    return lines


def render(
    doc: Document,
    template_dir: str = "../templates",
    lang: LanguageSpec | None = None,
) -> str:
    """Render a document as Quarto markdown in one language.

    `template_dir` is written into the `include-in-header` and `filters`
    front matter fields. Quarto resolves both paths relative to the
    generated .qmd file's own directory, not the repo root and not the
    working directory the render command is invoked from. The default
    assumes the .qmd is written one level below the repo root (e.g. into
    `.build/`), which is where the generator currently places it.

    `lang` defaults to English so callers that predate localization are
    unaffected.
    """
    if lang is None:
        lang = default_languages()["en"]
    fonts = ", ".join(f'"{f}"' for f in lang.fonts)
    lines = [
        FRONT_MATTER.format(template_dir=template_dir, lang=lang.typst),
        FONT_BLOCK.format(fonts=fonts),
        *_head(doc, lang),
    ]
    for section in doc.sections:
        lines += _section(section, lang)
    return "\n".join(lines).rstrip() + "\n"
