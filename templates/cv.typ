// All CV styling lives here. build.py never formats; to restyle the CV, edit
// this file and nothing else. Page size, margins, font and base size come from
// the front matter that emit.py writes.

#set par(leading: 0.58em, spacing: 0.62em, justify: false)
#set list(indent: 0.55em, body-indent: 0.42em, spacing: 0.5em, marker: [•])

// Name.
#show heading.where(level: 1): it => block(width: 100%)[#text(size: 21pt, weight: "bold")[#it.body]]

// Suppress page numbering. Quarto's own boilerplate issues a later
// `#set page(numbering: "1")` (Typst #set rules merge per field, so that
// call would silently re-enable a plain `numbering: none` here); setting
// `footer: none` instead suppresses the footer content that numbering
// would otherwise populate, and that field is untouched by Quarto's call.
#set page(numbering: none, footer: none)

// Section heading: bold label with a rule directly beneath.
#show heading.where(level: 2): it => block(width: 100%, above: 0.95em, below: 0.5em)[
  #text(size: 11.5pt, weight: "bold")[#it.body]
  #v(-0.62em)
  #line(length: 100%, stroke: 0.7pt)
]

#let cv-head(left: [], right: []) = block(width: 100%, below: 0.55em)[
  #grid(
    columns: (1fr, auto),
    align(bottom)[#left],
    align(bottom + end)[#text(size: 9pt)[#right]],
  )
]

#let cv-entry(dates: [], body) = block(width: 100%, above: 0.55em, below: 0.3em)[
  #grid(columns: (1fr, auto), body, align(top + right)[#dates])
]

#let cv-row(dates: [], body) = block(width: 100%, above: 0.28em, below: 0.28em)[
  #grid(columns: (1fr, auto), body, align(top + right)[#dates])
]

#let cv-prose(body) = block(width: 100%, above: 0.34em, below: 0.34em)[
  #set par(hanging-indent: 1.1em)
  #body
]

#let cv-labels(body) = block(width: 100%, above: 0.2em, below: 0.3em)[#body]
