# IEUMUN 2026 study guides: project conventions

## Rebuilding everything

```bash
./make -j8        # or plain `make -j8` once the Xcode licence is accepted
```

This converts every Word source in `SG_assets/` and writes the PDFs into one flat `out/` folder, all named `<short>_ieumun2026.pdf` (e.g. `interpol_ieumun2026.pdf`, `crisis-a_ieumun2026.pdf`). Only what changed is redone:

| You change | What rebuilds |
|---|---|
| a Word file or cover in `SG_assets/` | that guide |
| `SG_config/<slug>.json` | that guide |
| `scripts/` | every guide is reconverted |
| `template/` | every PDF is rebuilt |

Other targets: `./make wto` (one guide), `./make check` (build checks for all guides), `./make preview` (PNG pages in `.preview/`), `./make list`, `./make clean`.

`./make` is a small wrapper that finds a working GNU make, because `/usr/bin/make` refuses to run until the Xcode licence is accepted (`sudo xcodebuild -license`).

## Where things live

| Path | Contents | Edit? |
|---|---|---|
| `SG_assets/` | Word sources (folder = colour) and `COVER IMAGES/` | Never touched by the build |
| `SG_config/<slug>.json` | Everything specific to one guide | **Yes: all manual fixes go here** |
| `template/` | LaTeX class and cover | Yes (affects every guide) |
| `scripts/docx2guide.py` | Word to LaTeX converter (automatic rules) | Yes (affects every guide) |
| `guides/<slug>/` | Generated LaTeX and build files | No: wiped on every conversion |
| `out/` | Final PDFs | No |
| `reference/interpol-handmade/` | The original hand-made INTERPOL example | Reference only |

## A guide's config: `SG_config/<slug>.json`

```json
{
  "source": "SG_assets/RED/WTO _ IEUMUN 2026.docx",
  "cover": "SG_assets/COVER IMAGES/WTO.png",
  "output": "World Trade Organization (WTO) _ IEUMUN 2026.pdf",
  "language": "english",
  "meta": {
    "committee": "WTO",
    "longname": "World Trade Organization",
    "topic": "Balancing National Security and Free Trade ...",
    "authors": "Farhan, Céline & Yassine",
    "authors_label": "Chairs",
    "editor": "",
    "editor_label": "Edited by"
  },
  "convert": {
    "text_fixes": [["Framgworfi", "Framework"]],
    "headings": [{"match": "(?i)^bloc positions and key stakeholders$", "level": "top"}],
    "drop": [{"from": "^MOCKUP$", "until": "^Welcome Letter"}],
    "auto_lead": true,
    "letter_fallback": "The Chairs"
  },
  "patches": [
    {"file": "content/*about-the-topic.tex", "find": "old text", "replace": "new text", "regex": false}
  ]
}
```

- **Required:** `source`, `cover`, `output` (the PDF file name in `out/`, following the `<short>_ieumun2026.pdf` pattern). The source's folder sets the colour (`category` overrides it).
- **`meta`** fills the cover and running header. `authors_label` and `editor_label` change the "Written by" and "Edited by" captions. Leave a value empty to hide it.
- **`language`:** `spanish` switches the fixed wording (Índice, Escrito por, ...) and hyphenation.
- **`convert`** steers the converter:
  - `text_fixes` replaces text in the Word file before conversion.
  - `headings` forces lines matching a regex to be a heading. `level` is `"top"` for a numbered section, a Word heading level (`1`, `2`, ...), or `null` for "not a heading".
  - `drop` removes a stretch of the document.
  - `auto_lead: false` turns off the large first paragraph.
  - `top_level` and `pdf_mode` override detection.
- **`patches`** edit the generated LaTeX after conversion, for editorial touches such as `\pullquote` and `keypoints` boxes (see `interpol.json`) or for repairing text the Word file scrambled (see `wto.json`). A patch that stops matching stops the build, so edits are never lost silently.

## How source files arrive

- Word files come in folders named after their accent colour: **BLUE**, **BLACK**, **RED**. A `.doc` that is really a `.docx` (most are) is read directly; an old binary `.doc` is converted with `textutil` into `build/src/` first.
- Covers are in **COVER IMAGES**, matched by committee name. All four Crisis Cabinets share `CRISIS.png`.

## Accent colours

| Category | Hex | `\guidecategory{...}` |
|---|---|---|
| Blue | `#000153` | `blue` |
| Black | `#000000` | `black` |
| Red | `#DA1420` | `red` |

## Layout rules

- Page background is pure white (`#FFFFFF`).
- Cover: the full cover image, with the title block overlaid on its lower third.
- Every page after the cover has a full-width **banner** at the top: the bottom strip of that guide's cover image, cropped to a **1080 × 150** proportion. This happens automatically from `\guidecover{...}`.

## Build checks

`publish` (run by make) and `./make check` report, per guide: LaTeX errors, undefined references, missing files, lines running into the margin, sections that end on a nearly empty page, and whether the number of footnotes in the PDF matches the LaTeX and the Word source. The reports are also saved in `build/reports/`.

See [HOW-TO-CONVERT.md](HOW-TO-CONVERT.md) and [template/README.md](template/README.md).
