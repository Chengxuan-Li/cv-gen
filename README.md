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

`content/profile.yml` is tracked and carries **placeholder** contact details
(`you@example.com`, `+1 (555) 000-0000`). Real ones go in
`content/profile.local.yml`, which is gitignored so your phone number never
enters the repository:

```yaml
# content/profile.local.yml
contact:
  - "Email: [you@real.edu](mailto:you@real.edu)"
  - "Phone: +1 (555) 123 4567"
```

The override is a **shallow top-level merge**: any key present replaces that key
entirely, so `contact:` swaps the whole list and everything else falls through
from `profile.yml`. You can override `name` or `tagline` the same way.

This is the one manual step a fresh clone needs. Without it the build still
succeeds, so it warns on every run:

```
WARNING: content/profile.local.yml not found - using PLACEHOLDER contact details
```

Take that warning seriously — it means the PDF you are about to send has a fake
phone number on it. When the override is found, the build names it instead:

```
contact: content/profile.local.yml
```

## Build

```bash
python build.py --all                       # every declared document
python build.py --long                      # every long variant
python build.py --long --variant general    # one document
python build.py --check                     # validate content, render nothing
```

PDFs land in `out/cv-<length>-<variant>.pdf`. Both `out/` and the generated
`.build/` intermediates are gitignored — the repo tracks source only.

## Writing content

Content lives in `content/*.yml`. Prose fields are **markdown**, so `**bold**`,
`*italic*`, and `[text](url)` work throughout.

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
  - +Research time-series-based inverse modeling workflows.
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
| `+[gev-pos-1] Research inverse modeling` | marker, then text |
| `[ShadingZip](https://…) is a tool` | plain text — no leading `+`/`-` |
| `-[ShadingZip](https://…) is a tool` | plain text — `]` followed by `(` |
| `-5% peak load reduction` | plain text — `-` not followed by `[` or space |

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
stem is the section's name in `variants.yml`.

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

## Adding a variant

Declare it in `variants.yml` under whichever lengths should build it:

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
cvgen/           marker.py  schema.py  select.py  emit.py
variants.yml     which documents exist, and their section order
content/         profile.yml + one file per section
                 profile.local.yml — real contact details, gitignored
templates/       cv.typ (all styling)  cv.lua (markdown → Typst bridge)
tests/           pytest suite
resources/       private reference material — gitignored, never tracked
```

`build.py` decides **what** appears; `templates/cv.typ` decides **how it looks**.
To restyle the CV, edit the Typst template — no Python involved.

## Tests

```bash
python -m pytest
```
