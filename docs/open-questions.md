# Open questions

Decisions the owner has deliberately left open. **None of these are bugs, and
none should be "fixed" on an agent's own initiative** — each is a judgment call
that belongs to the owner. Bring them up, do not resolve them.

Last reviewed: 2026-09-04.

---

## 1. Content is untiered — `short` and `long` differ only by section

**State:** every item in `content/*.yml` is unmarked, so it appears in both
lengths. The two CVs differ only because `variants.yml` gives `short` three
sections and `long` five. The marker machinery is fully built and tested but
unexercised on real content.

**Why it is open:** which bullets are long-only is a judgment about the owner's
own career, not a technical decision. An agent must not invent a tiering.

**A proposal was drafted on 2026-09-03 and reverted unapplied**, pending the
owner's call. It was three markers:

| Where | Marker | Rationale |
|---|---|---|
| `content/experience.yml`, EnergyAtlas.io, the "Design core simulation, geometry, data, and visualization architecture…" bullet | prefix `+ ` | Longest bullet at three lines; elaborates *how* the bullet above it was achieved, which already states the outcome. |
| `content/experience.yml`, `Urban Systems Design MEP Engineers` entry | `mark: "+"` | A three-month 2023 internship, the oldest and least aligned item with the PhD/software trajectory. |
| `content/education.yml`, `BA (Hons)` entry | `mark: "+"` | Superseded by the M.Arch from the same institution. |

The Urban Systems one is the contested one: it is the only industry consulting
role and carries CBRE and Google as recognisable names, which may outweigh the
two lines it costs on a short CV aimed at industry rather than academia.

Skills were deliberately left untouched — the short CV has half a page free, so
cutting skill lines would thin it for no gain.

**Note the real payoff is additive.** With tiering in place the long CV can grow
— more publications, deeper detail, a second page — while the short one holds at
one page automatically. Today tiering mostly just makes `short` slightly tighter.

---

## 2. Making the repo agent-facing

**State:** the content schema exists only as imperative Python in
`cvgen/schema.py`. An agent authoring content must read that module to infer the
rules, then write a file and parse prose errors that give an item *index* rather
than a *line*.

**Why it is open:** the roadmap below was proposed on 2026-09-04 and the owner
chose not to schedule it yet. It is a real improvement, not a defect.

Five capabilities, in dependency order:

1. **Declarative spec** (`cvgen/spec.py`) — lift the per-block-type rules out of
   `_load_section`'s branches into a data table that validation is generated
   from. This is the spine; 2 and 3 derive from it.
2. **Emit JSON Schema** from that table via `build.py --schema`, with a test
   asserting a committed `schema/cv-content.schema.json` stays in sync. Add a
   `# yaml-language-server: $schema=` header to content files so editors and
   agents see identical validation. Covers structure only — it cannot express
   marker semantics or the two gates.
3. **Structured diagnostics** — `--check --json` emitting
   `{file, line, path, code, field, message, hint}`. The **stable `code` values
   matter more than the JSON envelope**, since agents should branch on
   `missing_required_field` rather than on prose. Line numbers need a
   `SafeLoader` subclass stashing `node.start_mark.line`.
4. **`build.py --explain long/general [--json]`** — per item, included/excluded
   and which gate decided it. Highest value for the least work: today the only
   way to confirm marker semantics is to render a PDF and read it.
5. **`build.py --lint`** for the traps no schema can catch: text matching
   `^[+-][^\s\[]` (the near-miss marker, item 3 below), and real-looking contact
   details in the tracked `content/profile.yml`.

**Design decision inside this:** derive JSON Schema from a declarative table
(recommended, no new dependency, keeps the existing error-message quality) versus
adopting Pydantic (less code long-term, but rewrites the half that is already
correct and well-tested while leaving the custom marker/gate logic uncovered).

**Deliberately excluded** as not addressing the actual gap: stub generators, a
REST/MCP wrapper, stdin validation.

Suggested phasing: items 4 and 5 first (independent of the refactor), then 1 and
3, then 2.

---

## 3. The near-miss marker is silent

`+Research …` is not a marker — it renders a literal `+` into the PDF and the
item stays in the short CV. Only `+ ` (with a space) and `+[variant]` parse.

This is **correct and intentional**: the space is what stops `-5% peak load
reduction` and `-[link](url) …` from being swallowed as markers. Do not relax it.

But it is silent, and it has already caught one agent following the README's own
example, which was wrong until 2026-09-04. The behaviour is now pinned in
`tests/test_marker.py` and documented in README and `AGENTS.md`. Open question is
only whether to add the `--lint` rule in item 2.5 above.

---

## 4. Git history contains real contact details

The working tree carries only placeholders, but commit `fb3c936` and neighbours
contain the owner's real email and phone. The owner decided on 2026-09-03 **not**
to rewrite history.

**Consequence: if this repo is ever pushed, it must be private.** Do not propose
`git filter-repo` again unless the owner raises it.

---

## 5. No remote

The repo exists only on the owner's machine. Nothing is backed up. See item 4
before proposing anything public.
