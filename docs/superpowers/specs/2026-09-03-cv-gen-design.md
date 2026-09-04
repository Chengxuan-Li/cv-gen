# CV Generator — Design

**Date:** 2026-09-03
**Status:** Approved

## Purpose

Generate PDF CVs from a single structured source. One body of content produces
many documents: two **lengths** (`short`, `long`) crossed with named **variants**
that target specific roles or employers. Prose is authored as markdown so that
`**bold**`, `*italic*`, and `[text](url)` work throughout.

Non-goals: HTML output, a web UI, multi-language CVs, and automatic content
rewriting. Section styling matches the reference style guide in `resources/`
(untracked).

## Architecture

```
content/*.yaml  ─┐
variants.yaml   ─┼─► build.py ──► .build/cv-<len>-<variant>.qmd ──► quarto ──► out/cv-<len>-<variant>.pdf
profile.yaml    ─┘   parse marker      markdown + fenced divs      cv.lua → cv.typ
                    apply 2 gates
                    order sections
```

`build.py` decides **what** appears; `templates/cv.typ` decides **how it looks**.
Neither reaches into the other. The Lua filter is the only bridge: it converts
fenced divs into Typst function calls, which is what allows markdown to survive
Pandoc untouched.

Quarto renders via **Typst**, not LaTeX. Typst ships inside Quarto, so the repo
has no LaTeX dependency, and builds take well under a second.

### Modules

| Module | Responsibility | Depends on |
|---|---|---|
| `marker.py` | Parse a marker token into `(tier, only, text)`. Pure function, no I/O. | nothing |
| `schema.py` | Load and validate `content/*.yaml` and `variants.yaml`. Owns every error message. | `marker` |
| `select.py` | Apply the two inclusion gates; order sections for a document. | `schema` |
| `emit.py` | Render selected blocks to `.qmd` markdown. Decides only *how it is written*. | nothing |
| `build.py` | CLI; wires the above; invokes `quarto render`. | all |
| `spec.py` | The content model declared as data. The single source for what a content file may contain. | nothing |
| `diagnostics.py` | `Problem`, the stable `CODES` contract, and YAML line anchoring. | nothing |
| `explain.py` | Per-item include/exclude with the deciding gate. | `select` |
| `lint.py` | Semantic mistakes no schema can catch. | `schema` |
| `jsonschema.py` | Emits `schema/*.json` from `spec.py`. | `spec` |

Each module is independently testable and small enough to hold in context at
once. `select.py` never formats; `emit.py` never filters.

## Content model

### Documents

A **document** is a `(length, variant)` pair declared in `variants.yaml`.
`length` is `long` or `short`. Every document renders to
`out/cv-<length>-<variant>.pdf`.

### Marker grammar

```
marker := ('+' | '-') ( '[' names ']' )?     ; must be followed by whitespace
```

- `+` — **long only**. Excluded from every `short` document.
- `-` — **both lengths**. Identical to omitting the marker; available for
  explicitness.
- `[names]` — comma-separated variant names. Defaults to `[general]` when absent.

The trailing-whitespace requirement makes the grammar collision-proof against
markdown, because a markdown link's `]` is always followed by `(`, never a
space. No escaping is needed for ordinary content.

| Text | Parsed as |
|---|---|
| `+[gev-pos-1] Research inverse modeling` | marker `+`, only `[gev-pos-1]` |
| `+ Research inverse modeling` | marker `+`, only `[general]` |
| `+Research inverse modeling` | **no marker** — no space after `+` |
| `Develop load profile inference…` | no marker; tier both, `[general]` |
| `-[ShadingZip](https://x) is a tool` | no marker — `]` followed by `(` |
| `[ShadingZip](https://x) is a tool` | no marker — no leading `+`/`-` |
| `**Nemetschek Award (€60,000)** *Second place*` | no marker — starts with `*` |
| `-5% peak load reduction` | no marker — `-` not followed by `[` or space |

A literal leading `+ ` or `- ` in prose is the one ambiguous case; write `\+ `
or `\- ` to escape it. The escape is stripped on output.

Entries (Experience, Education) are YAML mappings and carry the marker in an
optional `mark:` field using the identical grammar with the text omitted:
`mark: "+[gev-pos-1]"`, `mark: "+"`, `mark: "-[gev-pos-2,nvidia-pos-1]"`.

### Inclusion rule

An item appears in document *(L, V)* if and only if **both** gates pass:

| Gate | Rule |
|---|---|
| **tier** | `+` requires `L == long`. `-` or unmarked passes for both lengths. |
| **variant** | `general` is in `only`, **or** `V` is in `only`. |

`general` is the **inherited base pool, not a sibling variant**. Unmarked
content defaults to `only: [general]` and therefore flows into every variant.
`only: [gev-pos-1]` means "gev-pos-1 *in addition to* the general pool", not
"instead of it".

Worked example — an item marked `+[gev-pos-1, google-pos-1]`:

| Document | tier gate | variant gate | Result |
|---|---|---|---|
| long / general | pass | fail (`general` not listed) | excluded |
| long / gev-pos-1 | pass | pass | **included** |
| long / nvidia-pos-1 | pass | fail | excluded |
| short / google-pos-1 | fail (long only) | pass | excluded |

The item reaches `long/gev-pos-1` alone. `google-pos-1` is declared only under
`short`, so the `+` tier gate rules it out — a deliberate no-op, not an error.

### Block types

Each `content/*.yaml` declares a `type`, matching the four visual patterns in the
style guide. The filename stem is the section's name in `variants.yaml`.

| type | Used by | Renders as |
|---|---|---|
| `labels` | Skills | `**Label**: text`, one per line |
| `entries` | Experience, Education | **Org**, Location — right-aligned date; *italic role*; bullets |
| `rows` | Awards & Grants | one line, text left — date right |
| `prose` | Publications | markdown paragraph with hanging indent |

```yaml
# content/experience.yaml
title: Experience
type: entries
entries:
  - org: Cornell University, Environmental Systems Lab
    location: Ithaca NY
    dates: Aug 2024 – Current
    role: "PhD Researcher, Advisors: Prof Timur Dogan, Prof Oliver Gao, Prof Jacob Mays"
    bullets:
      - Develop load profile inference methods using machine learning, optimization, and statistical modeling.
      - + Research time-series-based inverse modeling and surrogate-learning workflows for model calibration.
  - org: EnergyAtlas.io
    location: Ithaca NY
    dates: Jan 2025 – Current
    role: Lead Developer
    mark: "-[nvidia-pos-1]"
    bullets:
      - Lead development of a city-scale utility digital twin and energy simulation platform in C#/.NET.
      - +[nvidia-pos-1] Build scalable pipelines for LiDAR, shading analysis, and large-scale urban simulations.
```

A marker on a container (an entry) that fails either gate removes the whole
container and its children. Child markers are evaluated only for surviving
containers, and never widen a parent's reach.

Sections themselves carry **no** marker: whether a section appears, and in what
order, is decided entirely by `variants.yaml`. This keeps document composition in
one file rather than split across every content file.

A section whose items are all filtered out is dropped along with its heading, so
no empty ruled heading is ever rendered.

### profile.yaml

`name` and `contact` are constant across documents. `tagline` accepts either a
plain string or a list of marked strings, in which case the **first item passing
both gates wins** — this is how a variant retargets its headline:

```yaml
name: Chengxuan Li
contact:
  - "Email: [you@example.com](mailto:you@example.com)"
  - "Phone: +1 (555) 000-0000"
tagline:
  - -[nvidia-pos-1] PhD Candidate in Systems Engineering — GPU-accelerated urban simulation
  - PhD Candidate in Systems Engineering, Minor in Electrical & Computer Engineering
```

Order matters: targeted taglines are listed before the unmarked fallback. If no
tagline survives, that is a build error naming `profile.yaml`.

#### Keeping contact details out of the repository

`content/profile.yaml` is tracked and therefore public if the repository ever is.
Its contact values are **placeholders** chosen to look obviously fake
(`you@example.com`, `+1 (555) 000-0000`). Real details live in an untracked
sibling, `content/profile.local.yaml`, matched by the gitignore rule
`content/*.local.yaml`.

The merge is a **shallow top-level key replacement**: a key present in the
override replaces that key entirely. `contact:` therefore swaps the whole list —
element-wise merging of a list has no unambiguous meaning, so it is not
attempted. Error messages name whichever of the two files actually supplied the
offending key.

The real risk this design introduces is not a build failure but a *successful*
build carrying fake details into a PDF someone sends to an employer. Two things
guard against it, and both are load-bearing:

1. The placeholders are unmistakable on sight. Realistic dummy values would be
   far more dangerous than obviously fake ones.
2. Every run reports its source — `contact: content/profile.local.yaml` when the
   override is found, and a `WARNING: ... using PLACEHOLDER contact details` on
   stderr when it is not. The build still succeeds, because a fresh clone must
   work; the warning is what makes the fallback safe.

`*.local.yaml` files are excluded from section discovery, so `profile.local.yaml`
never becomes a section named `profile.local`.

### variants.yaml

```yaml
long:
  sections: [skills, experience, publications, awards, education]
  variants:
    general:      {}
    gev-pos-1:    {sections: [skills, experience, awards, publications, education]}
    gev-pos-2:    {}
    nvidia-pos-1: {}
short:
  sections: [skills, experience, education]
  variants:
    general:      {}
    gev-pos-2:    {}
    google-pos-1: {}
```

`sections` on a length is the default order; a variant may override it with one
line. A section listed for one length and not the other is simply absent there.

## Repository layout

```
cv-gen/
  .gitignore            resources/, .build/, out/, content/*.local.yaml
  README.md             usage: marker grammar, block types, adding a variant
  AGENTS.md             agent operating rules and repo invariants
  requirements.txt      pyyaml; pytest and jsonschema for tests
  build.py              CLI entry point
  cvgen/                spec.py marker.py schema.py select.py emit.py
                        diagnostics.py explain.py lint.py jsonschema.py
  variants.yaml
  content/              profile.yaml skills.yaml experience.yaml
                        publications.yaml awards.yaml education.yaml
                        profile.local.yaml (untracked, real contact details)
  schema/               generated JSON Schema, never hand-edited
  templates/            cv.typ  cv.lua  link-icon.svg
  tests/                one module per cvgen module, plus test_render.py
  docs/open-questions.md   decisions deliberately left open
  .build/               generated .qmd (ignored)
  out/                  rendered PDFs (ignored)
```

### File extension

Content files use **`.yaml`**, which [the YAML spec's FAQ
recommends](https://yaml.org/faq.html); `.yml` is a DOS three-character holdover.
Discovery globs `*.yaml` only.

Choosing one convention creates a silent failure mode: a stray `.yml` would
simply not load, and the missing section would surface later as a confusing
"no content file" error against `variants.yaml`. The `legacy_yml_extension`
diagnostic reports any `.yml` under `content/`, or a `variants.yml` at the root,
turning that into an obvious one-line fix.

Accepting both extensions was the alternative and was rejected: tolerating the
other convention defeats the point of picking one, and `skills.yaml` alongside
`skills.yml` has no sane resolution.

`resources/` holds private reference material. It is gitignored and never
tracked, and nothing in the build reads from it.

## Dependencies

| Dependency | Purpose | Install |
|---|---|---|
| Quarto ≥ 1.10 | Rendering; bundles Typst and Pandoc | `winget install Posit.Quarto` |
| Python ≥ 3.9 | The generator | already present |
| `pyyaml` | Parsing content files | `pip install -r requirements.txt` |
| `pytest` | Tests | same |

No LaTeX distribution is required.

## CLI

```
python build.py --all
python build.py --long                      # every long variant
python build.py --long --variant gev-pos-1  # one document
python build.py --check                     # validate only, render nothing
```

## Error handling

Validation runs to completion and reports **all** problems before any render, so
one run surfaces every issue. Any error means a non-zero exit and no PDF written.

Every problem carries a stable `code` alongside its prose message, plus the file,
a source line, a path into the document, and a hint. `diagnostics.CODES` is the
published contract: rewording a message is safe, changing or removing a code is
breaking. Agents branch on the code.

| Condition | `code` | Message contains |
|---|---|---|
| Variant name in `only`/`mark` declared nowhere in `variants.yaml` | `undeclared_variant` | the name, its file and item index, and the declared variants |
| Variant declared only under the other length | — | *nothing* — deliberate no-op |
| Section in `variants.yaml` with no `content/` file | `missing_section_file` | the section and the available section names |
| A `.yml` file the loader will not see | `legacy_yml_extension` | the file, and the `.yaml` name to rename it to |
| Unknown block `type` | `unknown_block_type` | the file and the four valid types |
| Missing required field on an entry | `missing_required_field` | file, item index, field name |
| `contact` not given as a list | `invalid_field_type` | the file that supplied the key |
| Malformed marker (unclosed `[`) | `malformed_marker` | file, item index, the offending text |
| Empty or non-mapping content file | `empty_file`, `not_a_mapping` | the file |
| No `tagline` survives both gates | `no_surviving_tagline` | `profile.yaml` and the document being built |
| `quarto` not on PATH | — | `winget install Posit.Quarto` |

Two further checks are warnings rather than load errors, reported by
`build.py --lint`: `near_miss_marker` (a `+text` with no space, which renders a
literal `+`) and `real_contact_in_tracked_profile`, which looks specifically for
an email address or a phone number. A public URL is not sensitive and belongs in
the tracked file — but because `contact:` is replaced wholesale by the override,
such a line must be repeated in both files or it disappears once the override
exists.

## Inspection surfaces

Beyond `--check`, three commands make the model inspectable without rendering:

| Command | Answers |
|---|---|
| `--explain LENGTH/VARIANT` | for each item, included or excluded, and which gate decided it |
| `--lint` | the two silent mistakes above, which no schema can catch |
| `--schema` | regenerates `schema/*.json` from `cvgen/spec.py` |

`--json` on any of them emits machine-readable output. **Under `--json`, stdout
carries only the JSON document** — warnings go to stderr — so it pipes straight
into a parser. Exit codes: `0` success, `1` content or build failure, `2` usage.

## Testing

`pytest`, weighted toward the selection logic, which is where the behaviour lives.

- **`test_marker.py`** — the marker parse table above, parametrized verbatim,
  including every markdown collision case and the `\+` escape.
- **`test_select.py`** — the `+[gev-pos-1, google-pos-1]` truth table; `general`
  inheritance into all variants; container markers removing children; per-variant
  section order and override.
- **`test_schema.py`** — each error condition raises with a message naming the
  file and item; marker and `date` parsing on `labels`, `rows`, and `prose`
  items.
- **`test_emit.py`** — the Lua-filter div contract: each block type renders the
  wrapper divs the template expects, in the shape the sandwiching technique
  requires.
- **`test_build.py`** — `documents_for` resolves `--all`/`--long`/`--short`/
  `--variant` flag combinations to the right (length, variant) pairs; the CLI's
  JSON shapes and exit codes; that `build_one` raises rather than reporting
  success when Quarto produces no PDF.
- **`test_diagnostics.py`** — path formatting and YAML line anchoring, including
  that a malformed file still yields problems, just without line numbers.
- **`test_explain.py`** — which gate decides each item, and that bullets under an
  excluded entry are not reported separately, since they were never judged on
  their own markers.
- **`test_lint.py`** — both rules fire, and neither false-positives on `-5% peak
  load reduction` or a `+1 (555)` phone number.
- **`test_schema_export.py`** — the committed `schema/*.json` matches what
  `spec.py` generates, each schema is itself valid, it accepts every real content
  file, and it **rejects** malformed input. That last group matters: a schema
  accepting everything would pass a sync check while being useless.
- **`test_render.py`** — smoke test: every document builds, PDFs are non-trivial
  in size, the short variant is exactly one page, and markdown formatting
  survives into the PDF text layer.

## Decisions and rationale

| Decision | Why |
|---|---|
| Typst over LaTeX | Ships inside Quarto — no LaTeX install. Sub-second builds. The template is short enough to edit directly. |
| Markdown strings inside YAML | Keeps prose in markdown while giving the structure that filtering and ordering need. Avoids ~25 extra small files. |
| Marker requires trailing whitespace | Makes the grammar unambiguous against `[text](url)` with no escaping. |
| `general` inherited, not a sibling | Otherwise every targeted variant would start empty and shared content would need listing on every item. |
| Lua filter rather than emitting raw Typst | Raw Typst blocks would bypass Pandoc, breaking `**bold**` and links inside content. |
| Template assets staged into `.build/` | Typst sandboxes file access to its project root, which is `.build/`. A `../templates/...` path is rejected as escaping the sandbox, so `stage_assets()` copies them in and `cv.typ` uses bare filenames. |
| Rendered PDFs gitignored | Repo stays source-only and reproducible. Trivially reversible if linkable PDFs are wanted later. |
| `.yaml`, not `.yml` | The YAML spec recommends it. Discovery globs `*.yaml` only, and `legacy_yml_extension` reports strays so the choice cannot fail silently. |
| Content model declared in `spec.py` | The validator and the published JSON Schema derive from one table, so they cannot drift. Adding a field is a one-line edit. |
| Declarative table over Pydantic | Pydantic would replace only the structural half while rewriting code that is already correct and well-tested, and cannot express the marker grammar or the two gates either. |
| Stable diagnostic `code`s | Agents branch on codes; prose can then be reworded freely. Removing a code is the breaking change. |
| Line numbers via `yaml.compose` | Stashing a `__line__` key during construction pollutes every mapping and leaks into anything iterating keys. |
| Real contact in an untracked `.local.yaml` | Keeps a phone number out of tracked files. Placeholders are unmistakable, and the build reports which source it used, since the dangerous outcome is a successful build carrying fake details. |
