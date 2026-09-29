# Converting a Word study guide

## 1. Add it to the build

Put the Word file in `SG_assets/<COLOUR>/` and the cover in `SG_assets/COVER IMAGES/`, then create `SG_config/<slug>.json` with at least `source`, `cover`, `output` and `meta` (copy an existing one). Run `./make <slug>`; the PDF appears in `out/<COLOUR>/`. See [GUIDES.md](GUIDES.md) for every config option.

The converter can also run on its own:

```bash
python3 scripts/docx2guide.py "Security Council.docx" guides/unsc \
    --config SG_config/unsc.json --category blue --cover cover.png --force
cd guides/unsc && latexmk main.tex
```

It needs only Python 3, with no extra packages. It creates:

| Output | Contents |
|---|---|
| `main.tex` | Metadata (from the config, else guessed from the Word cover page) and one `\input` per section |
| `content/NN-*.tex` | One file per top-level section |
| `assets/figure-NN.*` | Every embedded image. GIF/TIFF/BMP become PNG with `sips`; EMF/WMF are tried with `inkscape`, `soffice` and `qlmanage`, and flagged if none works. Tiny images (spacers) are skipped. |
| `sources-extracted.md` | Every footnote, numbered, for checking |
| `front-matter.txt` | Text found before the first section (the Word cover), for reference |
| `convert-report.json` | Counts and warnings used by the build checks |

## 2. What the converter does automatically

- **Structure.** Finds the level that holds the guide's main sections (Welcome letter, Abbreviations, About the Committee, ... Bibliography), whether it is Word's *Title* style, *Heading 1* or *Heading 2*, a large font, a bold line, or a one-cell table used as a heading box. Deeper levels become subsections; bold or short title-like lines become minor headings. Typed numbering ("01", "a.", "1.2", "Section 3:") is removed, since the class numbers sections itself. ALL-CAPS headings become title case; acronyms stay uppercase.
- **Clean-up.** Drops the Word table of contents (automatic or typed), page labels such as "Title Page", and headings repeated by section breaks. A sentence styled as a heading by mistake becomes text again.
- **Letters.** Welcome letters become `chairletter` blocks with `\signoff[closing]{name}`. Chair names are completed from the config (`"Nils & Julius"` becomes the full names) or from "My name is ..." in the letter. Crisis staff introductions ("Chair - Name") get one block per person.
- **Abbreviations** in any typed form ("GDP: ...", "GDP – ...", "GDP⇥...", several per line, two-column tables) become an `abbreviations` list.
- **References, Bibliography, Further Readings** become a `referencelist`; a URL on its own line joins its entry.
- **Footnotes.** Word footnotes are kept verbatim. Documents converted from PDF, with notes typed at the foot of each page and superscript numbers in the text, get real footnotes rebuilt, and paragraphs cut by a page break are joined again.
- **Tables** get column widths from their content and may run across pages. One-row side-by-side boxes are unwrapped into text.
- **Images** keep their Word width; a caption in the same paragraph, or a "Figure 3:" or "Source:" line next to the image, becomes the caption.
- **Text repair.** PDF ligatures (ﬁ, ﬂ), a broken heading font seen in PDF conversions ("SĒudD" for "Study"), and underlines (which can't break across lines) are fixed.
- **Lead.** A section's first paragraph, or its first sentence, is set as a `\lead`.

## 3. Fixing what the rules get wrong

Never edit `guides/<slug>/`: it is regenerated. Put the fix in `SG_config/<slug>.json` instead:

1. Wrong or missing cover text: `meta`.
2. A typo or broken characters in the Word file: `convert.text_fixes`.
3. A line that should (or shouldn't) be a heading: `convert.headings`.
4. Editorial touches (`\pullquote`, `keypoints`) or text the Word file scrambled: `patches`.

If the same problem shows up in several guides, improve the rule in `scripts/docx2guide.py` instead, and every guide benefits on the next `./make`.

## 4. Review checklist

- `./make check` is clean: no errors, no nearly empty pages, footnote counts match.
- Cover: the title block sits in the dark lower third of the artwork.
- The contents page lists the expected sections.
- Letters, abbreviations and references look right; images are sharp and captioned.
