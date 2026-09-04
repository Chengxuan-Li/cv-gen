// All CV styling lives here. build.py never formats; to restyle the CV, edit
// this file and nothing else. Page size, margins, font and base size come from
// the front matter that emit.py writes.

// Three spacing values, and only three. Every gap in the document is one of
// them, so the vertical rhythm stays consistent and each level of separation is
// visibly distinct from the one below it:
//
//   LEADING  < PARA-GAP < ENTRY-GAP
//   within a   between     between
//   paragraph  paragraphs  entries
//
// The ordering is the point. If PARA-GAP ever fell below LEADING, wrapped lines
// would look further apart than separate paragraphs; if ENTRY-GAP fell below
// PARA-GAP, entries would stop reading as units. Earlier revisions kept that
// ordering by overriding leading per wrapper, which made line height differ
// between sections - awards were set at 0.3em against 0.52em elsewhere. The
// separation now comes entirely from block spacing, so leading is uniform.
#let LEADING = 0.44em
#let PARA-GAP = 0.54em
#let ENTRY-GAP = 0.78em

#set par(leading: LEADING, spacing: PARA-GAP, justify: false)
#set list(indent: 0.55em, body-indent: 0.42em, spacing: PARA-GAP, marker: [•])

// Pandoc's typst writer emits bare #link[...] with no styling, so a DOI or
// mailto link is visually indistinguishable from plain text. Underline it and
// prefix a mark, so a link is discernible on paper as well as on screen -
// underlining alone reads as emphasis once the document is printed.
//
// The mark is a Google Material Symbols link glyph, copied from resources/ into
// templates/ so the build never reads from resources/ - that directory is human
// reference material and is gitignored.
//
// The path is bare, and must stay bare. Quarto inlines include-in-header content
// into the generated .typ in .build/, and Typst sandboxes file access to its
// project root - which is .build/, since build.py runs quarto with that as its
// working directory. A "../templates/..." path is rejected as escaping the
// sandbox, so build.py stages template assets into .build/ alongside the .qmd.
//
// The source SVG ships with fill="#e3e3e3", intended for a dark background and
// nearly invisible on white; the copied asset is filled #000000 instead.
// The mark trails the text: a reader takes in the label first and the icon then
// confirms it is a link, rather than the icon interrupting the line before the
// word it belongs to.
#let link-mark = box(baseline: 0.10em, image("link-icon.svg", height: 0.82em))
#show link: it => [#underline[#it]#h(0.08em)#link-mark]

// Name.
#show heading.where(level: 1): it => block(width: 100%)[#text(size: 21pt, weight: "bold")[#it.body]]

// Suppress page numbering. Quarto's own boilerplate issues a later
// `#set page(numbering: "1")` (Typst #set rules merge per field, so that
// call would silently re-enable a plain `numbering: none` here); setting
// `footer: none` instead suppresses the footer content that numbering
// would otherwise populate, and that field is untouched by Quarto's call.
#set page(numbering: none, footer: none)

// Section heading: bold label with a rule directly beneath.
#show heading.where(level: 2): it => block(width: 100%, above: ENTRY-GAP, below: PARA-GAP)[
  #text(size: 11.5pt, weight: "bold")[#it.body]
  #v(-0.62em)
  #line(length: 100%, stroke: 0.7pt)
]

// Quarto's own template (included after this file) issues its own
// `#set par(justify: true, ...)` around the document body, which - because
// it is a `set` inside that template's own function scope - wins over the
// top-level `justify: false` above for everything the body contains. Each
// wrapper below re-asserts `justify: false` one scope deeper, inside its own
// block, which is what actually takes effect for its content.

#let cv-head(left: [], right: []) = block(width: 100%, below: ENTRY-GAP)[
  #set par(justify: false)
  #grid(
    columns: (1fr, auto),
    align(bottom)[#left],
    align(bottom + end)[#text(size: 9pt)[#right]],
  )
]

// Only the org line shares a row with the date; the role and bullets below it
// span the full text width. Putting the whole entry in the grid's 1fr column
// would narrow every bullet by the width of the date beside it, wrapping long
// bullets a word or two early for no reason.
//
// An entry reads as one unit because ENTRY-GAP below it exceeds the PARA-GAP
// between its own paragraphs and bullets - not because anything inside it is
// set tighter. `below` carries that separation rather than `above`: Typst
// collapses adjacent block spacing to the larger of the two, so `below` opens
// the gap after the last bullet while leaving heading-to-first-entry and
// entry-to-next-heading alone. Raising `above` would loosen all three.
#let cv-entry(dates: [], head: [], body) = block(width: 100%, above: PARA-GAP, below: ENTRY-GAP)[
  #set par(justify: false)
  #grid(columns: (1fr, auto), head, align(top + end)[#dates])
  #body
]

// A row that wraps to a second line must still read as one entry. That holds
// because LEADING joins its wrapped lines while ENTRY-GAP separates it from the
// next row - the same ordering every other block relies on, rather than the
// locally tightened leading an earlier revision used here.
#let cv-row(dates: [], body) = block(width: 100%, above: PARA-GAP, below: ENTRY-GAP)[
  #set par(justify: false)
  #grid(columns: (1fr, auto), body, align(top + end)[#dates])
]

#let cv-prose(body) = block(width: 100%, above: PARA-GAP, below: PARA-GAP)[
  #set par(hanging-indent: 1.1em, justify: false)
  #body
]

#let cv-labels(body) = block(width: 100%, above: PARA-GAP, below: PARA-GAP)[
  #set par(justify: false)
  #body
]
