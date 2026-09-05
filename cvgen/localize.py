"""Optionally-localized strings and language declarations.

Any translatable value in the content is either a plain string or a
language-keyed mapping:

    org: Cornell University                       # plain: serves every language
    org: {en: Cornell University, zh: 康奈尔大学}   # map: per language

The English value is the source. Resolving for a language returns its entry if
present and otherwise falls back to the source, so a partially translated CV
still renders. `en` is therefore required in every map.

Language is a third axis of a document, (length, variant, lang), not a variant:
`general` is an inherited base pool, so a `zh` variant would receive every
English item as well as its own. Markers are parsed from the source string only
- translation decides how an item reads, never whether it is included - which is
why `select.py` is untouched by all of this.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SOURCE_LANG = "en"

# BCP-47-shaped: 'en', 'zh', 'zh-CN'. Two letters exactly, so no field name can
# be mistaken for a language - including the three-letter 'org'. This is what
# makes a mapping-as-item unambiguous in rows and prose: if every key is a
# language code it is a localized string, otherwise it is a field mapping.
LANG_CODE = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")

DEFAULT_FONT = "Garamond"


class LStr(str):
    """A string that may carry translations. Its str value is the source text.

    Subclassing str keeps every existing consumer working unchanged - f-strings,
    equality against plain strings, sorting - while `in_()` gives the emitter a
    per-language view. Only the emitter should ever call `in_()`.
    """

    translations: dict[str, str]

    def __new__(cls, source: str, translations: dict[str, str] | None = None) -> "LStr":
        obj = super().__new__(cls, source)
        obj.translations = dict(translations or {})
        return obj

    def in_(self, lang: str) -> str:
        """The text for `lang`, falling back to the source."""
        if lang == SOURCE_LANG:
            return str(self)
        return self.translations.get(lang, str(self))

    def has(self, lang: str) -> bool:
        return lang == SOURCE_LANG or lang in self.translations

    def __repr__(self) -> str:
        if not self.translations:
            return f"LStr({str(self)!r})"
        return f"LStr({str(self)!r}, {self.translations!r})"


def is_lang_map(raw: object) -> bool:
    """True if `raw` is a non-empty mapping whose every key is a language code."""
    return (
        isinstance(raw, dict)
        and bool(raw)
        and all(isinstance(k, str) and LANG_CODE.match(k) for k in raw)
    )


@dataclass(frozen=True)
class LanguageSpec:
    """One declared output language and the rendering facts that go with it."""

    code: str
    typst: str  # what Typst's `lang:` needs - drives CJK line-breaking
    fonts: tuple[str, ...]
    # Chrome: the punctuation and fixed labels the emitter writes around content.
    # Data, not styling, which is why it lives beside the language rather than in
    # cv.typ. Full-width forms for Chinese.
    sep: str = ", "
    colon: str = ": "
    graduation: str = "Anticipated graduation"

    @property
    def mainfont(self) -> str:
        return self.fonts[0]

    @property
    def suffix(self) -> str:
        return f"-{self.code}"


# Chrome defaults keyed by Typst language code, so a declaration need only name
# the code and a font. Anything here can be overridden per declaration.
CHROME: dict[str, dict[str, str]] = {
    "en": {"sep": ", ", "colon": ": ", "graduation": "Anticipated graduation"},
    "zh": {"sep": "，", "colon": "：", "graduation": "预计毕业"},
}


def default_languages() -> dict[str, LanguageSpec]:
    return {SOURCE_LANG: LanguageSpec(SOURCE_LANG, SOURCE_LANG, (DEFAULT_FONT,))}


def language_spec(code: str, raw: dict | None) -> LanguageSpec:
    """Build a LanguageSpec from one `languages:` entry in variants.yaml."""
    raw = raw or {}
    typst = str(raw.get("typst", code.split("-")[0]))
    font = raw.get("font", DEFAULT_FONT)
    fonts = tuple(str(f) for f in font) if isinstance(font, list) else (str(font),)
    chrome = {**CHROME.get(typst, CHROME["en"])}
    for key in ("sep", "colon", "graduation"):
        if key in raw:
            chrome[key] = str(raw[key])
    return LanguageSpec(code, typst, fonts, **chrome)
