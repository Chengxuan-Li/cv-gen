// All CV styling lives here. build.py never formats; to restyle the CV, edit
// this file and nothing else. Page size, margins, font and base size come from
// the front matter that emit.py writes.

#set par(leading: 0.52em, spacing: 0.55em, justify: false)
#set list(indent: 0.55em, body-indent: 0.42em, spacing: 0.4em, marker: [•])

// Pandoc's typst writer emits bare #link[...] with no styling, so a DOI or
// mailto link is visually indistinguishable from plain text. Underline it,
// as a reader would expect from a hyperlink.
#show link: underline

// Name.
#show heading.where(level: 1): it => block(width: 100%)[#text(size: 21pt, weight: "bold")[#it.body]]

// Suppress page numbering. Quarto's own boilerplate issues a later
// `#set page(numbering: "1")` (Typst #set rules merge per field, so that
// call would silently re-enable a plain `numbering: none` here); setting
// `footer: none` instead suppresses the footer content that numbering
// would otherwise populate, and that field is untouched by Quarto's call.
#set page(numbering: none, footer: none)

// Section heading: bold label with a rule directly beneath.
#show heading.where(level: 2): it => block(width: 100%, above: 0.75em, below: 0.42em)[
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

#let cv-head(left: [], right: []) = block(width: 100%, below: 0.55em)[
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
#let cv-entry(dates: [], head: [], body) = block(width: 100%, above: 0.42em, below: 0.22em)[
  #set par(justify: false)
  #grid(columns: (1fr, auto), head, align(top + end)[#dates])
  #body
]

// A row that wraps to a second line must still read as one entry. Its leading
// is therefore tighter than the space between rows: within-entry lines sit
// closer together than the gap separating one award from the next. If these
// two numbers ever cross, wrapped rows visually merge with their neighbours.
#let cv-row(dates: [], body) = block(width: 100%, above: 0.42em, below: 0.42em)[
  #set par(leading: 0.3em, justify: false)
  #grid(columns: (1fr, auto), body, align(top + end)[#dates])
]

#let cv-prose(body) = block(width: 100%, above: 0.34em, below: 0.34em)[
  #set par(hanging-indent: 1.1em, justify: false)
  #body
]

#let cv-labels(body) = block(width: 100%, above: 0.2em, below: 0.3em)[
  #set par(justify: false)
  #body
]
