# IEUMUN 2026 study guide template

One LaTeX class for every committee guide. A guide only supplies metadata, a category colour, the cover artwork, and its content; the class handles all typography and layout.

## Design system

- **Type:** Montserrat throughout. Body 11/17 pt, **justified** (body, letters, lists, footnotes), with light hyphenation and microtype letter-width adjustment for even spacing. Headings, pull quotes and the References list stay left-aligned. Headings in tight-tracked Montserrat Bold; small labels in tracked uppercase.
- **Margins:** 2.1 cm left and right, 2.3 cm at the bottom. The top holds the banner and header.
- **No stranded lines:** a page never starts or ends with a single line of a paragraph, never breaks after a hyphen, and a letter's closing and signature (`\signoff`) always stay with the end of the letter.
- **Short-page fixer:** when a section's last page holds under 30% of a page, the next run tightens only that section, one step per run: shorter paragraphs where possible, then tighter leading, then tighter spacing (and tighter reference lists), then one and two extra lines per page (the footer stays put), and finally a more compact section opening with the lead set as normal text. `latexmk` reruns until the layout settles. If a section still ends short, the build log shows `Section N ends with a nearly empty page`, and every section's fill is logged as `IEUMUN short-page check`.
- **Contents on one page:** if the full contents list would not fit on one page, it is set tighter; if it still doesn't fit, only the sections are listed (logged as `IEUMUN contents`).
- **Colour:** near-black text `#1D1D1F`, grey `#6E6E73`, hairlines `#D2D2D7`, surfaces `#F5F5F7`, plus one category accent.
- **Categories** (shared across committees):

  | `\guidecategory{...}` | Accent | Example |
  |---|---|---|
  | `black` | `#000000` | INTERPOL |
  | `red` | `#DA1420` | |
  | `blue` | `#000153` | |

  To try a different shade, use `\guideaccent{HEX}` instead.
- **Banner:** every page after the cover shows the bottom strip of the cover image across the top, cropped to a 1080 × 150 proportion. It comes from `\guidecover`, so there's nothing extra to set.
- **Layout:** pure white pages. Each `\section` opens a new page with a large thin section number (`01`, `02`, …) and a 34 pt title. The header, below the banner, shows `IEUMUN 2026 | COMMITTEE` and the current section.

## Building

All guides are built from the project root with `./make` (see [GUIDES.md](../GUIDES.md)). A single guide can also be built by hand:

```bash
cd guides/interpol
latexmk main.tex        # lualatex + biber, settings come from latexmkrc
```

Requires TeX Live (LuaLaTeX, biber, biblatex-apa; Montserrat ships with TeX Live).

On macOS, TeX Live's `biber` fails with a `lipo` / Xcode-licence error unless the Xcode licence has been accepted. Either run `sudo xcodebuild -license`, or run `python3 scripts/fix-biber.py` once; `latexmkrc` picks up the fixed copy automatically.

## Metadata

```latex
\documentclass{ieumun-guide}
\guidecommittee{INTERPOL}
\guidelongname{International Criminal Police Organization}
\guidetopic{Financial Sovereignty, Offshore Secrecy, and ...}
\guideauthors{Christian Galindo, Anastasiia Bolkhovitina \& ...}
\guideeditor{Ariane Sorsen Albisu}      % leave empty to hide
\guidecover{assets/cover.jpg}           % full-bleed A4 artwork
\guidecategory{black}
\addbibresource{refs.bib}
```

Optional: `\guideauthorslabel{Chairs}` and `\guideeditorlabel{Crisis Director}` change the cover captions ("Written by", "Edited by"); `\guidelanguage{spanish}` switches the fixed wording and hyphenation to Spanish. A long committee name is scaled down to fit the cover on one line.

## Sources and references

Two ways to cite, and they can be mixed:

1. **`\source{key}`** with an entry in `refs.bib` (APA 7). The first citation of a work prints the full reference in a footnote. Later citations print `Author (Year), "Title"`. This matches how the original Word guides cite. Options:
   - `\source[art.~3]{interpolConstitution}` adds a pinpoint.
   - `\source{deflem2002,interpolKeyDates}` cites several works in one note.

   `\printbibliography` then lists every cited work under **References**, with hanging indents and clickable links.
2. **Plain `\footnote{...}`** with the author's original wording (which the Word converter produces), plus a typed bibliography:

   ```latex
   \unnumberedsection{References}
   \begin{referencelist}
     \refitem INTERPOL. (2024). Constitution ... \url{https://...}
   \end{referencelist}
   ```

## Components

| Command / environment | Use |
|---|---|
| `\lead{...}` | Large opening paragraph of a section |
| `\begin{chairletter}[Role]{Name} ... \signoff[Closing line,]{First name} \end{chairletter}` | Welcome letters (the closing and name never start a page alone) |
| `\pullquote[Attribution]{Quote}` | Magazine pull quote with accent bar |
| `\begin{keypoints}[Title] \item ... \end{keypoints}` | Rounded grey callout (footnotes inside still go to the page bottom) |
| `\begin{abbreviations} \abbr{GDP}{Gross Domestic Product} \end{abbreviations}` | Abbreviation list with hairline rows |
| `\guidefig[Caption]{assets/figure.png}[0.6]` | Figure, max 45% of page height; the optional last argument is its width as a fraction of the text width |
| `\begin{guidetable}[Y{0.6}Y{1.4}]{2} a & b \\ \midrule ... \end{guidetable}` | Table with light rules that may run across pages; the optional spec sets relative column widths |
| `\minorheading{...}` | Fourth heading level: a bold accent line that stays with the text below |
| `\email{name@example.com}` | Mail link |
| `\unnumberedsection{Title}` | Unnumbered section that still appears in the contents |
| `\todo{...}` | Dashed "to be completed" note |

## New guide

For a Word source, see [HOW-TO-CONVERT.md](../HOW-TO-CONVERT.md). To start by hand, copy `reference/interpol-handmade/` (the original hand-made example, which uses `\source{}` citations and `refs.bib`), change the metadata and category, and replace `assets/cover.jpg`, `content/`, and `refs.bib`.
