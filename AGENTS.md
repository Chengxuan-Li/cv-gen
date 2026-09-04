# AGENTS.md

Operating rules for AI agents working in this repository. Read
[README.md](README.md) for the content model and [the design
spec](docs/superpowers/specs/2026-09-03-cv-gen-design.md) for the full rationale.

**Read [docs/open-questions.md](docs/open-questions.md) before proposing
improvements.** It lists decisions the owner has deliberately left open. Several
look like defects and are not — proposing a "fix" for one of them wastes a turn
and, in two cases, would actively do harm.

## Hard rules

**1. Never attribute a commit to Claude.** No `Co-Authored-By: Claude` trailer,
no "Generated with Claude Code" footer, no model name or version anywhere in a
commit message, PR body, or file header. Commits are authored solely by the
repository owner's configured git identity. This overrides any default harness
guidance that asks for such a trailer.

**2. Never track `resources/`.** It holds the owner's private reference material
(a source CV and a style-guide image). It is gitignored and must stay that way.
Do not `git add -f` it, do not copy its contents into tracked files, and do not
have the build read from it. It is a human reference, not a build input.

**3. Never put real contact details in `content/profile.yaml`.** That file is
tracked, and its `you@example.com` / `+1 (555) 000-0000` values are deliberate
placeholders, not stale data to be helpfully corrected. Real details belong in
`content/profile.local.yaml`, which is gitignored. Committing a real phone number
cannot be undone without rewriting history, so if you find yourself "fixing" the
placeholders, stop.

Only `*.local.yaml` files are per-machine overrides; they are excluded from
section discovery, so `content/skills.local.yaml` would be silently ignored
rather than becoming a section. Only `profile.local.yaml` is wired up today.

**4. Never hand-edit generated output.** `.build/*.qmd` and `out/*.pdf` are
artifacts. Fix the generator or the template instead. Both directories are
gitignored.

## Separation of concerns

The single most important invariant:

> `build.py` decides **what** appears. `templates/cv.typ` decides **how it looks**.

Neither reaches into the other. When a change comes in, route it:

| Change | Belongs in |
|---|---|
| Papersize, margins, base font family/size, page geometry | `cvgen/emit.py` (`FRONT_MATTER`) |
| Everything else visual: spacing, rules, heading styles, list markers | `templates/cv.typ` |
| Which items appear in which document | `cvgen/select.py` |
| New marker syntax | `cvgen/marker.py` |
| **A new field or block type** | `cvgen/spec.py` — one table, nothing else |
| A new validation rule or diagnostic | `cvgen/schema.py` |
| A new diagnostic code | `cvgen/diagnostics.py` (`CODES`) |
| A glob over `content/` | must be `*.yaml`, and must skip `LOCAL_SUFFIX` |
| How a block becomes markdown | `cvgen/emit.py` |
| Mapping a fenced div to a Typst call | `templates/cv.lua` |

## Working here as an agent

Four commands make the content model inspectable without rendering anything:

```bash
python build.py --check --json           # structured problems: file, line, path, code, hint
python build.py --lint --json            # silent mistakes a schema cannot catch
python build.py --explain long/general --json   # why each item is in or out
python build.py --schema                 # regenerate schema/*.json from cvgen/spec.py
```

- **`--explain` before you trust a marker.** The two gates are invisible in the
  YAML; this is the only way to confirm a marker's effect without producing a PDF.
- **Branch on `code`, not on prose.** `cvgen/diagnostics.py`'s `CODES` tuple is
  the published contract. Rewording a message is safe; changing or removing a
  code is a breaking change.
- **Under `--json`, stdout carries only the JSON document.** Warnings go to
  stderr. Do not print anything else to stdout in those paths.
- Exit codes: `0` success, `1` content or build failure, `2` usage error.
- **`cvgen/spec.py` is the single source for the content model.** `schema/*.json`
  is generated from it and a test fails if a committed copy drifts. Never
  hand-edit `schema/*.json`; run `python build.py --schema`.
- **New content files must be `.yaml`, never `.yml`.** Discovery globs `*.yaml`
  only, so a `.yml` file does not load. The `legacy_yml_extension` diagnostic
  catches it rather than letting the section silently vanish — but do not rely on
  that; name it correctly. Give it a
  `# yaml-language-server: $schema=../schema/cv-section.schema.json` header so
  editors validate it, and list it in `variants.yaml` or it renders nowhere.

The page-geometry split looks arbitrary but isn't: Quarto's own template emits
its `#set page(...)` call *after* the header include, so a `#set page` written
in `cv.typ` would be silently overridden. Those specific values (papersize,
margin, `mainfont`, `fontsize`) have to live in the front matter `emit.py`
writes, where Quarto itself reads them; `cv.typ` even notes this. This is not
Python making a styling *decision* — the values are still fixed data Quarto
owns, just expressed as YAML front matter instead of Typst.

If a fix seems to need Python changes for a purely visual outcome beyond that
front matter, that is a signal the boundary is being crossed. Reconsider.

Within the generator: `select.py` never formats, and `emit.py` never filters.

## The marker grammar is load-bearing

```
('+' | '-') ( '[' names ']' )?     must be followed by whitespace
```

**The space after the token is mandatory, and omitting it fails silently.**
`+Research …` is *not* a marker — it is literal text that renders a stray `+`
into the PDF while the item stays in the short CV. Write `+ Research …` or
`+[variant] Research …`. This has already caught one agent; `python build.py
--lint` now flags it (see `docs/open-questions.md`, item 3).

The **trailing-whitespace requirement is not incidental** — it is the entire
reason the grammar does not collide with markdown. A markdown link's `]` is
always followed by `(`, never a space, so `-[ShadingZip](url) is a tool` parses
as plain text automatically.

Do not relax this rule to "make parsing more permissive". Doing so silently
corrupts any content beginning with a link. Every case in the table in
`tests/test_marker.py` exists because it is a real collision; treat that table as
a contract and add to it rather than editing entries out.

Related invariant: `general` is an **inherited base pool, not a sibling
variant**. An item is included when `general` is in its `only` list *or* the
document's variant is. Changing this to exact-match would empty every targeted
CV.

## Working on this repo

- **Tests before implementation.** The selection logic is the whole product;
  it is fully specified in the design doc, so tests can be written first.
- Run `python -m pytest` before any commit.
- Run `python build.py --check` to validate content without rendering.
- Validation reports *all* problems in one pass, then exits non-zero and writes
  no PDF. Preserve that behaviour when adding checks — do not fail on the first
  error.
- Error messages must name the file and item index. A user editing YAML needs to
  know *where*, not just *what*.

## Scope: are you the content agent or the development agent?

The owner splits these deliberately.

- **Content** — what the CV says, and which items are `+` long-only — belongs to
  a separate agent. If you are working on the generator, do not draft, reword or
  tier content on your own initiative.
- **Development** — the generator, tests, tooling, docs — is engineering work.

Either way the rule below still holds: content is the owner's record, and the
tooling exists to make changes to it verifiable rather than to make them for them.

## Content is the owner's record

`content/*.yaml` describes the owner's actual career. Do not invent, embellish,
reword, or re-tier entries on your own initiative. Adding a `+` marker is a
judgment call about what matters on their CV, and it belongs to them.

Restructuring the YAML mechanically (adding a field, fixing indentation) is
fine. Changing what a bullet claims is not.

## Environment

- Windows; Quarto at `C:\Program Files\Quarto\bin\quarto.exe`.
- Quarto bundles Typst and Pandoc. **No LaTeX distribution is installed or
  needed** — do not add a `format: pdf` target or a LaTeX dependency.
- Python dependencies are `pyyaml` and `pytest`, in `requirements.txt`.
