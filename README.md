# cv-gen

Generate PDF CVs from a single markdown-sourced content set. One body of content
produces many documents: two **lengths** (`short`, `long`) crossed with named
**variants** that target specific roles or employers.

Rendering goes through [Quarto](https://quarto.org) using its bundled
[Typst](https://typst.app) engine — **no LaTeX distribution required**, and
builds take well under a second.

## Setup

```bash
winget install Posit.Quarto
pip install -r requirements.txt
```

### Contact details

`content/profile.yaml` is tracked and carries **placeholder** contact details
(`you@example.com`, `+1 (555) 000-0000`). Real ones go in
`content/profile.local.yaml`, which is gitignored so your phone number never
enters the repository:

```yaml
# content/profile.local.yaml
contact:
  - "Email: [you@real.edu](mailto:you@real.edu)"
  - "Phone: +1 (555) 123 4567"
```

The override is a **shallow top-level merge**: any key present replaces that key
entirely, so `contact:` swaps the whole list and everything else falls through
from `profile.yaml`. You can override `name`, `anticipated_graduation`, or
`tagline` the same way.

One consequence worth knowing: because `contact:` is replaced wholesale, a
non-sensitive line kept in the tracked file — a personal website, say — is
**dropped once the override exists**, so it has to be repeated in both. Only
email addresses and phone numbers are treated as sensitive; `--lint` flags those
in the tracked file and ignores URLs.

This is the one manual step a fresh clone needs. Without it the build still
succeeds, so it warns on every run:

```
WARNING: content/profile.local.yaml not found - using PLACEHOLDER contact details
```

Take that warning seriously — it means the PDF you are about to send has a fake
phone number on it. When the override is found, the build names it instead:

```
contact: content/profile.local.yaml
```

## Build

```bash
python build.py --all                       # every declared document
python build.py --long                      # every long variant
python build.py --long --variant general    # one document, every language
python build.py --lang zh                   # every document, Chinese only
python build.py --check                     # validate content, render nothing
```

PDFs land in `out/cv-<length>-<variant>-<lang>.pdf` — one per declared language,
English included and suffixed like the rest. Both `out/` and the generated
`.build/` intermediates are gitignored — the repo tracks source only.

## Inspecting content

```bash
python build.py --check              # validate; reports every problem at once
python build.py --lint               # silent mistakes a schema cannot catch
python build.py --explain long/general   # why each item is in or out
python build.py --explain long/general/zh   # ...and which fall back to English
python build.py --schema             # regenerate schema/*.json from cvgen/spec.py
```

`--explain` answers the question the marker system otherwise hides — you can see
a decision without rendering a PDF:

```
short/general: 15 of 17 items included
  experience/entries[2]             EXCLUDE gate=tier     tier '+' is long-only, this document is short
  experience/entries[0].bullets[1]  include               unmarked, so inherited from the 'general' base pool
```

Links carry a chain icon and an underline, so a DOI or mailto reads as a link
on paper as well as on screen.

`--lint` catches the two failure modes that pass validation and still produce a
wrong document: a near-miss marker (`+Design…` with no space), and a real email
address or phone number sitting in the tracked `profile.yaml`. It looks for those
two specifically — a public URL such as a personal site is not sensitive and
belongs in the tracked file.

Add `--json` to any of these for machine-readable output. Under `--json`,
**stdout carries only the JSON document** — warnings go to stderr — so it can be
piped straight into a parser. Exit codes are part of the contract: `0` success,
`1` content or build failure, `2` usage error.

```bash
python build.py --check --json | jq '.problems[] | {file, line, code}'
```

Every problem carries a stable `code` (see `cvgen/diagnostics.py`). Branch on the
code, not the prose — messages may be reworded, codes will not be.

## Writing content

Content lives in `content/*.yaml`. Prose fields are **markdown**, so `**bold**`,
`*italic*`, and `[text](url)` work throughout.

The extension is `.yaml`, not `.yml` — [the YAML spec recommends
it](https://yaml.org/faq.html), and discovery globs `*.yaml` only. A stray `.yml`
would otherwise be ignored in silence, so the build reports it instead:

```
content is invalid:
  - awards.yml: this project uses '.yaml', so this file is ignored by the loader
```

### The marker

Any item may carry a leading marker controlling which documents it reaches:

```
('+' | '-') ( '[' variant, variant ']' )?     followed by a space
```

| Marker | Meaning |
|---|---|
| `+` | **long only** — never appears in a short CV |
| `-` | both lengths (identical to no marker; use it when you want to be explicit) |
| *(none)* | both lengths |
| `[a,b]` | restrict to variants `a` and `b`. Defaults to `[general]` when absent. |

```yaml
bullets:
  - Develop load profile inference methods using ML and optimization.
  - + Research time-series-based inverse modeling workflows.
  - +[nvidia-pos-1] Build GPU-accelerated pipelines for large-scale simulation.
```

**`general` is an inherited base pool, not a sibling variant.** Unmarked content
defaults to `only: [general]` and therefore flows into *every* variant. Writing
`[gev-pos-1]` means "gev-pos-1 **in addition to** the general pool", not
"instead of it". So you only ever mark the content that is *special*.

The marker must be followed by a space, which is what keeps it from colliding
with markdown. A link's `]` is always followed by `(`, never a space:

| Text | Read as |
|---|---|
| `+ Research inverse modeling` | marker, then text |
| `+[gev-pos-1] Research inverse modeling` | marker, then text |
| `+Research inverse modeling` | **plain text** — no space after `+` |
| `[ShadingZip](https://…) is a tool` | plain text — no leading `+`/`-` |
| `-[ShadingZip](https://…) is a tool` | plain text — `]` followed by `(` |
| `-5% peak load reduction` | plain text — `-` not followed by `[` or space |

> **The space is not optional.** `+Research …` is not a marker — it renders as a
> literal `+` in the PDF and the item stays in the short CV. Nothing warns you.
> Write `+ Research …` or `+[variant] Research …`.
>
> The rule exists because `-5% peak load reduction` and `-[link](url) …` are
> ordinary content that must not be swallowed as markers. Requiring the space is
> what tells them apart.

To start a line with a literal `+ ` or `- `, escape it: `\+ `.

Experience and Education entries are YAML mappings, so they take the same
grammar in a `mark:` field with the text omitted:

```yaml
- org: EnergyAtlas.io
  location: Ithaca NY
  dates: Jan 2025 – Current
  role: Lead Developer
  mark: "-[nvidia-pos-1]"
  bullets: [...]
```

A marker on an entry removes the whole entry and its bullets when it fails.

### Block types

Each content file declares a `type`, matching one visual pattern. The filename
stem is the section's name in `variants.yaml`.

| type | Used by | Renders as |
|---|---|---|
| `labels` | Skills | `**Label**: text`, one per line |
| `entries` | Experience, Education | **Org**, Location — right-aligned date; *role*; bullets |
| `rows` | Awards & Grants | one line, text left — date right |
| `prose` | Publications | markdown paragraph, hanging indent |

A `rows` item may carry an optional `date:` alongside its `text:`, rendered
right-aligned:

```yaml
items:
  - text: "**IBPSA-USA Simulation Showcase ($600)** *Winner*"
    date: May 2026
```

## Languages

A language is a **third axis**, not a variant. Variant answers *which content*;
language answers *which rendering of the same content*. Every `(length,
variant)` renders once per language declared in `variants.yaml`:

```yaml
languages:
  en: {typst: en, font: Garamond}
  zh: {typst: zh, font: [Garamond, Noto Serif SC]}
```

`en` is the source and is required. `typst` is the code Typst needs for
line-breaking — `zh`, because Chinese has no spaces to wrap at. `font` may be a
stack; list the Latin face first so Latin text keeps it.

Any translatable value is **either a plain string or a language-keyed map**:

```yaml
bullets:
  - Develop load profile inference methods.          # plain: every language
  - en: + Research inverse-modeling workflows.       # map: per language
    zh: 研究反演建模工作流。
```

A plain string serves every language. A map falls back to its `en` entry for
any language it lacks, so a half-translated CV still builds. Nothing existing had
to change: every plain string already *is* the English source.

Three rules that follow from that design:

- **The marker is read from `en` only.** Translation decides how an item reads,
  never whether it is in. A `+ ` or `[…]` at the start of a `zh` value is a lint
  *error* — a translator who repeated it and got it wrong would create a silent
  divergence.
- **A map standing in for a whole item** (in `rows` or `prose`) is recognised
  because every key is a two-letter language code; `{text:, date:}` is not.
- **Untranslated strings are lint *warnings*, not errors** — unfinished, not
  wrong. `--lint` still exits 0 while the list is worked down;
  `--explain long/general/zh` shows which items will fall back.

Punctuation the emitter writes around content — the comma between org and
location, the colon after a skills label — comes from the language too, so
Chinese gets `，` and `：`.

## Adding a variant

Declare it in `variants.yaml` under whichever lengths should build it:

```yaml
long:
  sections: [skills, experience, publications, awards, education]
  variants:
    general:      {}
    gev-pos-1:    {sections: [skills, experience, awards, publications, education]}
    nvidia-pos-1: {}
short:
  sections: [skills, experience, education]
  variants:
    general:      {}
    google-pos-1: {}
```

`sections` on a length is the default order; any variant overrides it with one
line. A variant declared under only one length simply doesn't exist for the
other — marking content for it from the other length is a deliberate no-op, not
an error.

Then tag content with `[your-variant]`. Nothing else to wire up.

## Layout

```
build.py         CLI entry point
cvgen/
  spec.py        the content model, declared as data — the single source
  marker.py      the marker grammar
  schema.py      load and validate, against spec.py
  select.py      the two inclusion gates
  emit.py        selected content → Quarto markdown
  explain.py     why each item is in or out
  lint.py        semantic mistakes no schema can catch
  diagnostics.py Problem, stable codes, YAML line anchoring
  jsonschema.py  emits schema/*.json from spec.py
  localize.py    LStr, language declarations, per-language chrome
variants.yaml    which documents exist, and their section order
content/         profile.yaml + one file per section
                 profile.local.yaml — real contact details, gitignored
schema/          generated JSON Schema — do not hand-edit
templates/       cv.typ (all styling)  cv.lua (markdown → Typst bridge)
                 link-icon.svg — staged into .build/ at render time
tests/           pytest suite
resources/       private reference material — gitignored, never tracked
```

`build.py` decides **what** appears; `templates/cv.typ` decides **how it looks**.
To restyle the CV, edit the Typst template — no Python involved.

**`cvgen/spec.py` is the single source for the content model.** The validator,
the JSON Schema under `schema/`, and this README's block-type table all derive
from it, so adding a field means editing one table. `schema/*.json` is generated
— a test fails if a committed copy drifts from what `spec.py` would produce.

Every content file carries a `# yaml-language-server: $schema=…` header, so an
editor and an agent see the same structural validation as the build.

## Tests

```bash
python -m pytest
```

## Further reading

| Document | What it is |
|---|---|
| [AGENTS.md](AGENTS.md) | Operating rules and invariants for AI agents working here |
| [docs/open-questions.md](docs/open-questions.md) | Decisions deliberately left open — read before proposing improvements |
| [docs/superpowers/specs/…-design.md](docs/superpowers/specs/2026-09-03-cv-gen-design.md) | The design and its rationale |
| [docs/superpowers/plans/…-implementation.md](docs/superpowers/plans/2026-09-03-cv-gen-implementation.md) | How it was built, task by task |
