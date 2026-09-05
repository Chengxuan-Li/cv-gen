# Translating the CV

A working guide for whoever adds a language. It assumes you have read
[README.md](../README.md) once. Everything here is content work — it never
requires touching `cvgen/`, `templates/` or `build.py`.

## The model in one paragraph

Every document is `(length, variant, lang)`. Language is a **third axis**, not a
variant: `general` is inherited by every variant, so a `zh` variant would carry
all the English content too. Instead, every translatable value in `content/` is
either a plain string or a language-keyed map. A plain string serves every
language; a map supplies translations and **falls back to `en`** for any
language it lacks. So a half-translated CV always builds, and translating is a
matter of turning strings into maps one at a time.

## Where languages are declared

```yaml
# variants.yaml
languages:
  en: {typst: en, font: Garamond}
  zh: {typst: zh, font: [Garamond, Noto Serif SC]}
```

`en` is required. Adding a language here is the only step that creates a new set
of PDFs; everything else is optional refinement of them.

## How to translate a value

Turn the string into a map with the original under `en`:

```yaml
# before
org: Cornell University
# after
org: {en: Cornell University, zh: 康奈尔大学}
```

Long values read better in block form:

```yaml
bullets:
  - Develop load profile inference methods.          # plain: every language
  - en: + Research inverse-modeling workflows.       # map
    zh: 研究反演建模工作流。
```

For `rows` and `prose` items, a map may stand in for the whole item:

```yaml
items:
  - en: "Li, C. **ShadingZip** …"
    zh: "李，C. **ShadingZip** …"
```

That works because every key is a two-letter language code; `{text:, date:}`
is a field mapping and is told apart by its keys.

### What is translatable

| Translatable | Never translatable |
|---|---|
| section `title` | `type` |
| `org`, `location`, `dates`, `role` | `mark` (the entry-level marker) |
| bullets, `text`, `date`, `label` | URLs inside markdown links |
| profile `name`, `tagline`, `contact` lines, `anticipated_graduation` | anything in `variants.yaml` other than `languages` |

## Five rules

**1. The marker stays on `en`.** A `+ ` or `+[variant] ` at the start of a bullet
decides whether it is included; translation decides how it reads. Write the
marker once, on the English text, and never on a translation:

```yaml
- en: + Research inverse-modeling workflows.     # marker here
  zh: 研究反演建模工作流。                          # never here
```

A marker in a `zh` value is a lint **error** (`marker_in_translation`).

**2. `en` is required in every map.** A map without it is a load error.

**3. Do not add Chinese punctuation the emitter already writes.** The comma
between org and location, the colon after a skills label, and the
`预计毕业：` caption are written by the build, full-width for `zh`. Translate
`org: 康奈尔大学`, not `org: 康奈尔大学，`.

**4. Strings that should stay identical get an explicit map.** Paper titles,
product names like `EnergyAtlas.io`, and DOIs usually stay as they are. A plain
string is reported as untranslated forever; `{en: X, zh: X}` says "deliberately
the same" and silences the warning:

```yaml
- text: {en: "**EnergyAtlas.io**", zh: "**EnergyAtlas.io**"}
```

**5. Contact lines live in two files, and the untracked one wins.**
`content/profile.yaml` carries placeholder contact details and is tracked;
`content/profile.local.yaml` carries the real ones, is gitignored, and
**replaces the whole `contact` list** when present. A `zh` translation of an
`Email:` line added only to `profile.yaml` will never render on the owner's
machine. Translate the contact lines in `profile.local.yaml` too — that file
exists only on the owner's machine, so this is theirs to do or to be asked for.

## The worklist

```bash
python build.py --lint
```

Every untranslated string is a **warning** (`untranslated_string`), with file,
line and path. Warnings do not fail the build; the count going down is the
progress meter. Errors do fail it — a marker in a translation, an undeclared
language key, a map without `en`.

```bash
python build.py --explain long/general/zh
```

The same inclusion decisions as the English document — language never changes
whether an item is in — plus `[falls back to en]` on each included item that
will render in English, and a count in the summary line. Use this to see the
effect per document rather than per string.

## The loop

```bash
python build.py --check                     # structure valid, four renders declared
python build.py --lint                      # warnings = what is left
python build.py --explain long/general/zh   # what this document will show
python build.py --lang zh                   # build the Chinese PDFs only
```

Then open `out/cv-long-general-zh.pdf`. Output names are suffixed with the
language, `en` included. The one-page test covers the English short CV; if the
Chinese one runs longer or shorter that is not a test failure, but worth a look.

## Chinese specifics

- **Dates**: `Aug 2024 – Present` → `2024年8月 – 至今`. The dash is content;
  keep whichever you prefer, consistently.
- **Names**: `name` is translatable. Whether to render the owner's name in
  Chinese, or keep the Latin form, is the owner's call — ask.
- **Fonts**: Latin text stays in Garamond; CJK falls through to Noto Serif SC.
  Nothing to do per string.
- **Line-breaking**: handled by Typst from `typst: zh`. Nothing to do.

## What not to do

- Do not remove `zh` from `variants.yaml` to silence the warnings. That is the
  worklist, not noise.
- Do not translate `mark:` or a `type:`. The schema rejects it.
- Do not put a marker on a translation. Lint rejects it.
- Do not change spacing, fonts or the template to fit Chinese. That is
  development work; say what looks wrong instead.
