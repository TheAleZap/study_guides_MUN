#!/usr/bin/env python3
"""Convert a Word (.docx) study guide into an IEUMUN LaTeX guide folder.

    python3 scripts/docx2guide.py SOURCE.docx guides/<slug> \
        [--config SG_config/<slug>.json] [--category black|red|blue] \
        [--cover IMAGE] [--force]

Produces:
    guides/<slug>/main.tex               metadata + one \\input per section
    guides/<slug>/content/*.tex          one file per top-level section
    guides/<slug>/assets/                embedded images (+ cover if given)
    guides/<slug>/sources-extracted.md   every footnote, numbered, for review
    guides/<slug>/front-matter.txt       the Word cover page text, for reference
    guides/<slug>/convert-report.json    counts used by the build checks
    guides/<slug>/latexmkrc

The conversion is rule based and deterministic, so a guide can be regenerated
at any time. Everything that is specific to one guide (metadata, text fixes,
heading overrides) comes from the optional JSON config; see GUIDES.md.

Word footnotes become \\footnote{...} with their original wording and links.
Documents that were converted from PDF (notes typed at the bottom of every
page, marked by superscript numbers in the text) get real footnotes rebuilt.
Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import statistics
import struct
import subprocess
import sys
import zipfile
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "v": "urn:schemas-microsoft-com:vml",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
}
W = "{%s}" % NS["w"]
R = "{%s}" % NS["r"]
WP = "{%s}" % NS["wp"]

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT / "template"

LATEX_READY_IMAGES = {".png", ".jpg", ".jpeg", ".pdf"}
SIPS_CONVERTIBLE = {".gif", ".tif", ".tiff", ".bmp", ".heic", ".webp"}
VECTOR_FORMATS = {".emf", ".wmf", ".emz", ".wmz"}

SMALL_WORDS = {
    "a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "into",
    "nor", "of", "on", "or", "per", "the", "to", "via", "vs", "with",
    "de", "del", "la", "las", "el", "los", "y", "en", "para", "que", "con",
}
COMMON_CAPS_WORDS = {
    "THE", "AND", "OF", "TO", "IN", "FOR", "ON", "WITH", "A", "AN", "IS", "ARE",
    "BE", "AS", "AT", "BY", "OR", "NOT", "NO", "YES", "ALL", "NEW",
}

# Superscript numbers are kept as tokens until the notes are resolved:
# \ue000 + kind (f = body, c = caption) + digits + \ue001.
TOK_OPEN, TOK_CLOSE, TOK_FLUSH = "\ue000", "\ue001", "\ue002"
TOKEN_RE = re.compile("\ue000([fc])([^\ue001]*)\ue001")

LIGATURES = str.maketrans({
    "\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi", "\ufb04": "ffl",
    "\ufb05": "st", "\ufb06": "st", "\u200b": "", "\u200c": "", "\u200d": "",
    "\ufeff": "", "\u2028": " ", "\u2029": " ", "\u00ad": "", "\uf0b7": "•",
})

CONTENTS_RE = re.compile(r"^(table of contents?|contents?|index|índice|indice)$", re.I)
SECTION_KINDS = [
    ("contents", CONTENTS_RE),
    ("drop", re.compile(r"^(title page|study guide|onglet \d+|mockup|cover|cover page)$", re.I)),
    ("staff", re.compile(r"staff introductions?|meet the (staff|chairs|dais)|crisis staff", re.I)),
    ("welcome", re.compile(r"welcome|letter|carta|crisis director", re.I)),
    ("abbreviations", re.compile(r"abbreviation|acronym|glossary|abreviaciones|siglas", re.I)),
    ("references", re.compile(
        r"^(references?|bibliography|works cited|sources|reference list|further readings?|"
        r"referencias|bibliograf[ií]a|lecturas? (adicionales|recomendadas)|"
        r"further readings? and bibliography|bibliography and further readings?)$", re.I)),
]
# Titles that mark a top-level section in the IEUMUN guide structure.
TOPISH_RE = re.compile(
    r"welcome|letter|carta de|abbreviation|abreviaciones|acronym|glossary|about the (committee|topic)|"
    r"sobre el (comit|tema)|current situation|situaci[oó]n actual|bloc|stakeholder|posiciones|"
    r"questions|qarma|warma|preguntas|further reading|bibliograph|references|referencias|annex|"
    r"crisis director|staff introduction|initial situation|role of the cabinet|topic introduction|"
    r"introduction to the topic and|types of journalism|table of content|^contents?$|^index$", re.I)
# Untagged bold or centred lines that are unmistakably top-level titles.
TOP_TITLE_RE = re.compile(
    r"^(welcome letters?( from the chairs?)?|letters? from the chairs?|chairs?'? letter|letter from chairs|"
    r"list of abbreviations?|abbreviations|about the committee|about the topic|current situation|"
    r"key stakeholders( and| &)? blocs?( positions)?|blocs? positions( and key stakeholders)?|"
    r"stakeholders? (and|&) bloc positions|"
    r"questions a resolution must answer( \(?qarmas?\)?)?|qarmas?|further readings?|bibliography|"
    r"references|annex(es)?)$", re.I)

HEADING_PREFIXES = [
    (re.compile(r"^(?:section\s+)?\d+\.\d+\.\d+\.?\s*[:.\-–]?\s*", re.I), 2),
    (re.compile(r"^(?:section\s+)?\d+\.\d+\.?\s*[:.\-–]?\s*", re.I), 1),
    (re.compile(r"^(?:section|sección|part|parte)\s+\d+\s*(?:[:\-–]|\.(?!\d))\s*", re.I), 0),
    (re.compile(r"^(?:section|sección)\s+[IVXLC]+\s*[:.\-–]\s*", re.I), 0),
    (re.compile(r"^[a-h][.)]\s+"), 1),
    (re.compile(r"^(?:ii|iii|iv|vi|vii|viii|ix|x|i|v)[.)]\s+"), 2),
    (re.compile(r"^[IVX]+[.)]\s+"), None),
    (re.compile(r"^(?:0\d\s+|\d{1,2}\.\s+|\d{1,2}\s{2,})"), None),
]

CAPTION_RE = re.compile(r"^(figure|fig\.|image|imagen|figura|map|mapa|chart|gráfico|graph|illustration)\s*\d*\s*[:.\-–]\s*", re.I)
SOURCE_RE = re.compile(r"^(source|sources|fuente|credit)\s*[:.]", re.I)
BULLET_RE = re.compile(r"^\s*[•●◦▪▫■□○‣⁃∙·\-–]\s+")
NUMBERED_RE = re.compile(r"^\s*\d{1,2}[.)]\s+")
EMAIL_RE = re.compile(r"(?<![\w.@/])([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})(?![\w@])")
YEAR_RE = re.compile(r"\((?:\d{4}[a-z]?|n\.\s?d\.?|s\.\s?f\.?)(?:[^()]{0,40})\)")

CLOSING_RE = re.compile(
    r"^(?:(?:with\s+)?(?:best|kind|kindest|warm|warmest|all\s+the\s+best)(?:\s+regards|\s+wishes)?|"
    r"regards|sincerely|yours(?:\s+sincerely|\s+truly|\s+faithfully)?|cheers|see you[^.]*|"
    r"looking forward[^.]*|hope to see you[^.]*|until (?:then|november)[^.]*|best of luck[^.]*|"
    r"un saludo[^.]*|saludos[^.]*|atentamente|con cariño|nos vemos[^.]*|your chairs?|"
    r"diplomatically yours|love)\s*[,.!]*$", re.I)
ROLE_WORDS_RE = re.compile(r"\b(chairs?|co-chairs?|director|president[ae]?s?|presidentas?|moderator|"
                           r"committee|ieumun|backroomer|secretary|dais|staff)\b", re.I)


# ---------------------------------------------------------------------------
# LaTeX escaping
# ---------------------------------------------------------------------------

_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    "\u00a0": "~",
    "\u2011": "-",
    "\u00ad": "",
    "\t": " ",
    "\n": " ",
}
URL_RE = re.compile("(https?://[^\\s<>\"\ue000\ue001]+|file:///[^\\s<>\"\ue000\ue001]+|www\\.[^\\s<>\"\ue000\ue001]+)")


def escape_text(text: str) -> str:
    return "".join(_ESCAPES.get(ch, ch) for ch in text)


def escape_url(url: str) -> str:
    return url.replace("\\", "/").replace("%", r"\%").replace("#", r"\#").replace("{", "").replace("}", "")


def escape_with_urls(text: str) -> str:
    """Escape plain text, turning bare URLs and e-mail addresses into links."""
    out = []
    pos = 0
    for m in URL_RE.finditer(text):
        out.append(escape_emails(text[pos:m.start()]))
        url = m.group(0)
        trail = ""
        while url and url[-1] in ".,;:)]":
            if url[-1] == ")" and url.count("(") >= url.count(")"):
                break
            trail = url[-1] + trail
            url = url[:-1]
        target = url if url.startswith(("http", "file:")) else "https://" + url
        if target == url:
            out.append(r"\url{%s}" % escape_url(url))
        else:
            out.append(r"\href{%s}{\nolinkurl{%s}}" % (escape_url(target), escape_url(url)))
        out.append(escape_text(trail))
        pos = m.end()
    out.append(escape_emails(text[pos:]))
    return "".join(out)


def escape_emails(text: str) -> str:
    out = []
    pos = 0
    for m in EMAIL_RE.finditer(text):
        out.append(escape_text(text[pos:m.start()]))
        out.append(r"\email{%s}" % m.group(1).replace("%", r"\%"))
        pos = m.end()
    out.append(escape_text(text[pos:]))
    return "".join(out)


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:40] or "section"


def clean(text: str) -> str:
    """Plain text without note tokens, with whitespace collapsed."""
    text = TOKEN_RE.sub("", text).replace(TOK_FLUSH, "")
    return re.sub(r"\s+", " ", text).strip()


def norm(text: str) -> str:
    """Comparable form of a heading: lower case, no numbering, brackets or punctuation."""
    text = clean(text)
    text, _ = strip_heading_prefix(text)
    text = text.replace("&", " and ").replace("[", "").replace("]", "")
    text = re.sub(r"[^\w\s']", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def strip_heading_prefix(text: str):
    """Remove typed numbering ("01", "a.", "1.2", "Section 3:"); return (text, rank hint)."""
    for rx, rank in HEADING_PREFIXES:
        m = rx.match(text)
        if m and len(text) > m.end():
            return text[m.end():].strip(), rank
    return text, None


# ---------------------------------------------------------------------------
# Package parts
# ---------------------------------------------------------------------------

class Package:
    def __init__(self, path: Path):
        self.zip = zipfile.ZipFile(path)
        self.names = set(self.zip.namelist())

    def xml(self, name: str):
        if name not in self.names:
            return None
        return ET.fromstring(self.zip.read(name))

    def rels(self, part: str) -> dict[str, tuple[str, str]]:
        folder, _, base = part.rpartition("/")
        rel_name = f"{folder}/_rels/{base}.rels"
        root = self.xml(rel_name)
        result = {}
        if root is None:
            return result
        for rel in root.findall("rel:Relationship", NS):
            result[rel.get("Id")] = (rel.get("Target"), rel.get("TargetMode", ""))
        return result


def on(el) -> bool:
    if el is None:
        return False
    return el.get(W + "val", "true").lower() not in {"0", "false", "none", "off"}


@dataclass
class Styles:
    names: dict[str, str] = field(default_factory=dict)
    based_on: dict[str, str] = field(default_factory=dict)
    outline: dict[str, int] = field(default_factory=dict)
    bold: dict[str, bool] = field(default_factory=dict)
    italic: set[str] = field(default_factory=set)
    sizes: dict[str, float] = field(default_factory=dict)
    default_size: float = 11.0
    default_para: str | None = None

    @classmethod
    def load(cls, root):
        s = cls()
        if root is None:
            return s
        dd = root.find("w:docDefaults/w:rPrDefault/w:rPr/w:sz", NS)
        if dd is not None and dd.get(W + "val", "").isdigit():
            s.default_size = int(dd.get(W + "val")) / 2
        for st in root.findall("w:style", NS):
            sid = st.get(W + "styleId")
            name = st.find("w:name", NS)
            s.names[sid] = (name.get(W + "val") if name is not None else sid).lower()
            if st.get(W + "type") == "paragraph" and st.get(W + "default") in {"1", "true"}:
                s.default_para = sid
            based = st.find("w:basedOn", NS)
            if based is not None:
                s.based_on[sid] = based.get(W + "val")
            lvl = st.find("w:pPr/w:outlineLvl", NS)
            if lvl is not None:
                s.outline[sid] = int(lvl.get(W + "val"))
            rpr = st.find("w:rPr", NS)
            if rpr is not None:
                b = rpr.find("w:b", NS)
                if b is not None:
                    s.bold[sid] = on(b)
                if on(rpr.find("w:i", NS)):
                    s.italic.add(sid)
                sz = rpr.find("w:sz", NS)
                if sz is not None and sz.get(W + "val", "").isdigit():
                    s.sizes[sid] = int(sz.get(W + "val")) / 2
        return s

    def chain(self, sid):
        seen = []
        if sid is None:
            sid = self.default_para
        while sid and sid not in seen:
            seen.append(sid)
            sid = self.based_on.get(sid)
        return seen

    def heading_level(self, sid) -> int | None:
        for s in self.chain(sid):
            name = self.names.get(s, s.lower())
            if name == "title":
                return 0
            if name == "subtitle":
                return None
            m = re.match(r"heading\s*(\d)", name)
            if m:
                return int(m.group(1))
            if s in self.outline and self.outline[s] < 9:
                return self.outline[s] + 1
        return None

    def is_bold(self, sid) -> bool:
        for s in self.chain(sid):
            if s in self.bold:
                return self.bold[s]
        return False

    def size(self, sid) -> float:
        for s in self.chain(sid):
            if s in self.sizes:
                return self.sizes[s]
        return self.default_size

    def name(self, sid) -> str:
        return self.names.get(sid, (sid or "").lower())


class Numbering:
    def __init__(self, root):
        self.formats: dict[tuple[str, int], str] = {}
        if root is None:
            return
        abstract = {}
        for an in root.findall("w:abstractNum", NS):
            aid = an.get(W + "abstractNumId")
            levels = {}
            for lv in an.findall("w:lvl", NS):
                fmt = lv.find("w:numFmt", NS)
                levels[int(lv.get(W + "ilvl"))] = fmt.get(W + "val") if fmt is not None else "bullet"
            abstract[aid] = levels
        for num in root.findall("w:num", NS):
            nid = num.get(W + "numId")
            ref = num.find("w:abstractNumId", NS)
            if ref is None:
                continue
            for lvl, fmt in abstract.get(ref.get(W + "val"), {}).items():
                self.formats[(nid, lvl)] = fmt

    def kind(self, num_id: str, level: int) -> str:
        fmt = self.formats.get((num_id, level), "bullet")
        return "itemize" if fmt in {"bullet", "none"} else "enumerate"


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------

@dataclass
class Block:
    kind: str  # para | heading | table | image | page | sep | caption
    text: str = ""          # LaTeX, may contain note tokens
    plain: str = ""         # plain text, may contain note tokens
    level: float = 0        # raw heading level (0 = Title style)
    style: str = ""
    list_kind: str | None = None
    list_level: int = 0
    rows: list = field(default_factory=list)
    plain_rows: list = field(default_factory=list)
    image: str = ""
    width: float = 1.0
    caption: str = ""
    all_bold: bool = False
    size: float = 0.0
    align: str = ""
    numbered: bool = False  # heading carries Word list numbering
    source: str = ""        # how a heading was found: style | table | size | title | bold | line
    rank: int | None = None
    force_top: bool = False
    rank_hint: int | None = None

    @property
    def clean(self) -> str:
        return clean(self.plain)


class Converter:
    def __init__(self, pkg: Package, out_dir: Path, fixes: list | None = None):
        self.pkg = pkg
        self.out_dir = out_dir
        self.fixes = fixes or []
        self.styles = Styles.load(pkg.xml("word/styles.xml"))
        self.numbering = Numbering(pkg.xml("word/numbering.xml"))
        self.doc_rels = pkg.rels("word/document.xml")
        self.footnotes = self._load_notes("word/footnotes.xml", "w:footnote")
        self.endnotes = self._load_notes("word/endnotes.xml", "w:endnote")
        self.footnote_log: list[str] = []
        self.images: list[str] = []
        self.warnings: list[str] = []
        self._image_cache: dict[str, tuple[str, float] | None] = {}
        self.text_width_emu = 5731510  # A4 with 1 inch margins; replaced from sectPr below
        self.word_notes = 0

    # -- notes --------------------------------------------------------------
    def _load_notes(self, part, tag):
        root = self.pkg.xml(part)
        notes = {}
        if root is None:
            return notes
        rels = self.pkg.rels(part)
        for note in root.findall(tag, NS):
            if note.get(W + "type") in {"separator", "continuationSeparator", "continuationNotice"}:
                continue
            notes[note.get(W + "id")] = (note, rels)
        return notes

    def _note_text(self, table, nid) -> str:
        if nid not in table:
            return ""
        note, rels = table[nid]
        parts = []
        plains = []
        for p in note.iter(W + "p"):
            text, plain, _, _ = self.inline(p, rels, in_note=True)
            text = TOKEN_RE.sub(lambda m: r"\textsuperscript{%s}" % m.group(2), text).strip()
            if text:
                parts.append(text)
                plains.append(clean(plain))
        self.footnote_log.append(" ".join(plains))
        self.word_notes += 1
        return " ".join(parts)

    # -- images -------------------------------------------------------------
    def _image(self, rid, rels, cx=None):
        if rid not in rels:
            return None
        target, mode = rels[rid]
        if mode == "External":
            return None
        part = target.lstrip("/") if target.startswith("/") else "word/" + target
        part = re.sub(r"[^/]+/\.\./", "", part)
        if part in self._image_cache:
            return self._image_cache[part]
        if part not in self.pkg.names:
            return None
        data = self.pkg.zip.read(part)
        dims = image_size(data)
        if len(data) < 1200 or (dims and min(dims) < 24):
            self._image_cache[part] = None
            return None
        assets = self.out_dir / "assets"
        assets.mkdir(parents=True, exist_ok=True)
        ext = Path(part).suffix.lower()
        index = len([v for v in self._image_cache.values() if v]) + 1
        dest = assets / f"figure-{index:02d}{ext}"
        dest.write_bytes(data)
        final = dest
        if ext in SIPS_CONVERTIBLE or ext in VECTOR_FORMATS:
            final = convert_image(dest)
            if final is None:
                self.warnings.append(f"{dest.name}: {ext} image could not be converted to PNG; convert it by hand.")
                self._image_cache[part] = None
                return None
        width = 1.0
        if cx:
            width = max(0.25, min(1.0, cx / self.text_width_emu))
            if width > 0.85:
                width = 1.0
        rel = (f"assets/{final.name}", round(width, 2))
        self._image_cache[part] = rel
        self.images.append(rel[0])
        return rel

    # -- runs ---------------------------------------------------------------
    def fix_text(self, text: str) -> str:
        text = fix_garbled(text, force=self._garbled)
        text = text.translate(LIGATURES)
        return text.replace("fff", "ff")

    _garbled = False

    def inline(self, p, rels, in_note=False, pstyle=None):
        """Return (latex, plain_text, images, stats) for a paragraph element."""
        raw = "".join(t.text or "" for t in p.iter(W + "t"))
        saved, self._garbled = self._garbled, is_garbled(raw)
        try:
            return self._inline(p, rels, in_note, pstyle)
        finally:
            self._garbled = saved

    def _inline(self, p, rels, in_note=False, pstyle=None):
        segments: list[tuple[str, tuple]] = []
        plain: list[str] = []
        images: list[tuple[str, float]] = []
        fields: list[dict] = []
        stats = {"chars": 0, "bold": 0, "sizes": defaultdict(int)}
        style_bold = self.styles.is_bold(pstyle)
        style_size = self.styles.size(pstyle)

        def emit(latex, fmt=()):
            if fields and not fields[-1]["separated"]:
                return
            target = fields[-1]["result"] if fields else segments
            target.append((latex, fmt))

        def run_format(r):
            rpr = r.find("w:rPr", NS)
            fmt = set()
            bold = style_bold
            size = style_size
            if rpr is not None:
                rs = rpr.find("w:rStyle", NS)
                rstyle = rs.get(W + "val") if rs is not None else None
                if rstyle:
                    name = self.styles.name(rstyle)
                    if self.styles.is_bold(rstyle) or name == "strong":
                        bold = True
                    if rstyle in self.styles.italic or name == "emphasis":
                        fmt.add("i")
                    if "hyperlink" in name:
                        fmt.add("link")
                b = rpr.find("w:b", NS)
                if b is not None:
                    bold = on(b)
                if on(rpr.find("w:i", NS)):
                    fmt.add("i")
                u = rpr.find("w:u", NS)
                if u is not None and u.get(W + "val", "single") != "none":
                    fmt.add("u")
                va = rpr.find("w:vertAlign", NS)
                if va is not None:
                    if va.get(W + "val") == "superscript":
                        fmt.add("sup")
                    elif va.get(W + "val") == "subscript":
                        fmt.add("sub")
                pos = rpr.find("w:position", NS)
                if pos is not None and pos.get(W + "val", "0").lstrip("-").isdigit() and int(pos.get(W + "val")) > 2:
                    fmt.add("raised")
                if on(rpr.find("w:smallCaps", NS)):
                    fmt.add("sc")
                sz = rpr.find("w:sz", NS)
                if sz is not None and sz.get(W + "val", "").isdigit():
                    size = int(sz.get(W + "val")) / 2
            if bold:
                fmt.add("b")
            if "link" in fmt:
                fmt.discard("u")
                fmt.discard("link")
            return fmt, size

        def text_run(text, fmt, size):
            text = self.fix_text(text)
            for find, repl in self.fixes:
                text = text.replace(find, repl)
            if ("sup" in fmt or "raised" in fmt) and re.fullmatch(r"[\d\s,;–\-]*\d[\d\s,;–\-]*", text):
                digits = text.strip()
                plain.append(TOK_OPEN + "f" + digits + TOK_CLOSE)
                emit(TOK_OPEN + "f" + digits + TOK_CLOSE, ())
                return
            plain.append(text)
            visible = len(text.strip())
            stats["chars"] += visible
            if "b" in fmt:
                stats["bold"] += visible
            stats["sizes"][size] += visible
            fmt = tuple(sorted(f for f in fmt if f != "raised"))
            emit(escape_text(text), fmt)

        def walk(el):
            tag = el.tag
            if tag == W + "r":
                fmt, size = run_format(el)
                for child in el:
                    ctag = child.tag
                    if ctag == W + "t":
                        text_run(child.text or "", fmt, size)
                    elif ctag in {W + "tab", W + "ptab"}:
                        plain.append("\t")
                        emit(" ", ())
                    elif ctag in {W + "br", W + "cr"}:
                        if child.get(W + "type") not in {"page", "column"}:
                            plain.append("\n")
                            emit(r"\newline ", ())
                    elif ctag == W + "noBreakHyphen":
                        plain.append("-")
                        emit("-", ())
                    elif ctag == W + "softHyphen":
                        continue
                    elif ctag == W + "sym":
                        char = chr(int(child.get(W + "char", "20"), 16))
                        if 0xF000 <= ord(char) <= 0xF0FF:
                            char = "•" if ord(char) in {0xF0B7, 0xF0A7, 0xF076} else ""
                        plain.append(char)
                        emit(escape_text(char), ())
                    elif ctag == W + "footnoteReference" and not in_note:
                        emit(r"\footnote{%s}" % self._note_text(self.footnotes, child.get(W + "id")))
                    elif ctag == W + "endnoteReference" and not in_note:
                        emit(r"\footnote{%s}" % self._note_text(self.endnotes, child.get(W + "id")))
                    elif ctag in {W + "drawing", W + "pict", W + "object"}:
                        cx = None
                        ext = child.find(".//wp:extent", NS)
                        if ext is not None and ext.get("cx", "").isdigit():
                            cx = int(ext.get("cx"))
                        for blip in child.iter("{%s}blip" % NS["a"]):
                            img = self._image(blip.get(R + "embed"), rels, cx)
                            if img:
                                images.append(img)
                        for imd in child.iter("{%s}imagedata" % NS["v"]):
                            img = self._image(imd.get(R + "id"), rels, cx)
                            if img:
                                images.append(img)
                        seen_tb = False
                        for tb in child.iter(W + "txbxContent"):
                            if seen_tb:
                                break  # Choice and Fallback repeat the same box
                            seen_tb = True
                            for tp in tb.findall("w:p", NS):
                                t, pl, im, _ = self.inline(tp, rels, in_note)
                                if pl.strip():
                                    plain.append(" " + pl)
                                    emit(" " + t, ())
                                images.extend(im)
                        stats["drawing"] = True
                    elif ctag == W + "fldChar":
                        kind = child.get(W + "fldCharType")
                        if kind == "begin":
                            fields.append({"instr": "", "result": [], "separated": False})
                        elif kind == "separate" and fields:
                            fields[-1]["separated"] = True
                        elif kind == "end" and fields:
                            finish_field(fields.pop())
                    elif ctag == W + "instrText" and fields:
                        fields[-1]["instr"] += child.text or ""
                    elif ctag == "{%s}AlternateContent" % NS["mc"]:
                        choice = child.find("mc:Choice", NS)
                        if choice is None:
                            choice = child.find("mc:Fallback", NS)
                        if choice is not None:
                            for sub in choice:
                                wrapper = ET.Element(W + "r")
                                wrapper.append(sub)
                                walk(wrapper)
            elif tag == W + "hyperlink":
                rid = el.get(R + "id")
                start = len(segments)
                pstart = len(plain)
                for child in el:
                    walk(child)
                inner = merge(segments[start:])
                del segments[start:]
                url = rels.get(rid, ("", ""))[0] if rid else ""
                text_plain = clean("".join(plain[pstart:]))
                if url.startswith("mailto:"):
                    segments.append((r"\email{%s}" % escape_text(url[7:]), ()))
                elif url:
                    if URL_RE.fullmatch(text_plain or "") or text_plain.startswith(("http", "www.")):
                        segments.append((r"\url{%s}" % escape_url(url), ()))
                    elif inner.strip():
                        segments.append((r"\href{%s}{%s}" % (escape_url(url), inner), ()))
                else:
                    segments.append((inner, ()))
            elif tag == W + "fldSimple":
                fld = {"instr": el.get(W + "instr", ""), "result": [], "separated": True}
                fields.append(fld)
                for child in el:
                    walk(child)
                finish_field(fields.pop())
            elif tag in {W + "ins", W + "smartTag", W + "customXml", W + "sdt", W + "sdtContent",
                         W + "bdo", W + "dir"}:
                for child in el:
                    walk(child)
            elif tag == "{%s}AlternateContent" % NS["mc"]:
                choice = el.find("mc:Choice", NS)
                if choice is None:
                    choice = el.find("mc:Fallback", NS)
                if choice is not None:
                    for child in choice:
                        walk(child)

        def finish_field(fld):
            instr = fld["instr"].strip()
            result = merge(fld["result"])
            m = re.match(r'HYPERLINK\s+"([^"]+)"', instr)
            if m and not instr.startswith("HYPERLINK \\l"):
                url = m.group(1)
                result_plain = re.sub(r"\\[a-z]+\{|\}", "", result)
                if URL_RE.fullmatch(result_plain.strip()):
                    latex = r"\url{%s}" % escape_url(url)
                else:
                    latex = r"\href{%s}{%s}" % (escape_url(url), result)
            elif instr.split(" ")[0] in {"PAGEREF", "TOC", "PAGE", "NUMPAGES", "SEQ", "REF"}:
                latex = result if instr.split(" ")[0] in {"SEQ", "REF"} else ""
            else:
                latex = result
            if fields and fields[-1]["separated"]:
                fields[-1]["result"].append((latex, ()))
            elif not fields:
                segments.append((latex, ()))

        for child in p:
            if child.tag == W + "pPr":
                continue
            walk(child)

        latex = merge(segments)
        latex = linkify(latex)
        return latex, "".join(plain), images, stats


GARBLE_MARKS = re.compile(r"[a-zA-Z][Ē™½«]|[Ē™½«][a-zA-Z]")
GARBLED_DIGITS = re.compile(r"\b(?=[0-9OV]*[0-9])(?=[0-9OV]*[OV])[0-9OV]{3,}\b")


def fix_digits(text: str) -> str:
    """Years typed in the same broken font: "2OOV" is 2004, "15VO" is 1540."""
    return GARBLED_DIGITS.sub(lambda m: m.group().replace("O", "0").replace("V", "4"), text)


def is_garbled(text: str) -> bool:
    return "e" not in text and len(GARBLE_MARKS.findall(text)) >= 1 and len(re.findall(r"[a-z]", text)) >= 5


def fix_garbled(text: str, force: bool = False) -> str:
    """Undo a broken font encoding seen in PDF-converted headings.

    "Casg SĒudD: Thg SouĒh China Sga DispuĒgs (2O16 - ™rgsgnĒ)" is
    "Case Study: The South China Sea Disputes (2016 - Present)". Such runs never
    contain a real "e", which keeps ordinary text (and names with Ē) untouched."""
    if not force and ("e" in text or not GARBLE_MARKS.search(text)):
        return fix_digits(text)
    text = text.replace("Ē", "t").replace("™", "P").replace("½", "R").replace("«", "E")
    text = text.replace("\ufb01", "k")
    text = fix_digits(re.sub(r"(?<=\d)O|O(?=\d)", "0", text))
    text = re.sub(r"(?<=\w)D\b", "y", text)
    # "g" stands for "e", except in "-ing" and before a final "y" ("Energy").
    return re.sub(r"g(?!\b)(?!y\b)|(?<!in)g\b", lambda m: "e", text)


def merge(segments) -> str:
    out = []
    current_fmt = None
    buf = []

    def flush():
        if buf:
            out.append(wrap("".join(buf), current_fmt or ()))

    for text, fmt in segments:
        if not text:
            continue
        if fmt != current_fmt:
            flush()
            buf = []
            current_fmt = fmt
        buf.append(text)
    flush()
    return "".join(out)


def wrap(text: str, fmt: tuple) -> str:
    if not fmt or not text.strip():
        return text
    lead = text[: len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()):]
    core = text.strip()
    for f in fmt:
        core = {
            "b": r"\textbf{%s}",
            "i": r"\emph{%s}",
            "u": r"\underline{%s}",
            "sup": r"\textsuperscript{%s}",
            "sub": r"\textsubscript{%s}",
            "sc": r"\textsc{%s}",
        }.get(f, "%s") % core
    return lead + core + trail


LINK_RE = re.compile(
    r"(\\(?:url|href|nolinkurl|email)\{[^}]*\}(?:\{(?:[^{}]|\{[^{}]*\})*\})?)"
    r"|(https?://[^\s{}\ue000\ue001]+|file:///[^\s{}\ue000\ue001]+|www\.[^\s{}\ue000\ue001]+)"
    r"|((?<![\w.@/\\])(?:[A-Za-z0-9.%+\-]|\\_)+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})")


def linkify(latex: str) -> str:
    """Turn bare URLs and e-mail addresses typed as plain text into links."""

    def repl(m):
        if m.group(1):
            return m.group(1)
        if m.group(3):
            return r"\email{%s}" % m.group(3).replace(r"\_", "_")
        url = m.group(2)
        trail = ""
        while url and url[-1] in ".,;:)":
            if url[-1] == ")" and url.count("(") >= url.count(")"):
                break
            trail = url[-1] + trail
            url = url[:-1]
        raw = url.replace(r"\_", "_").replace(r"\&", "&").replace(r"\%", "%").replace(r"\#", "#")
        raw = raw.replace(r"\textasciitilde{}", "~")
        if raw.startswith("www."):
            return r"\href{https://%s}{\nolinkurl{%s}}%s" % (escape_url(raw), escape_url(raw), trail)
        return r"\url{%s}%s" % (escape_url(raw), trail)

    return LINK_RE.sub(repl, latex)


def image_size(data: bytes):
    """(width, height) of a PNG, JPEG or GIF, or None."""
    try:
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return struct.unpack(">II", data[16:24])
        if data[:6] in (b"GIF87a", b"GIF89a"):
            return struct.unpack("<HH", data[6:10])
        if data[:2] == b"\xff\xd8":
            i = 2
            while i < len(data) - 9:
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                if marker in (0xC0, 0xC1, 0xC2, 0xC3):
                    h, w = struct.unpack(">HH", data[i + 5:i + 9])
                    return w, h
                seg = struct.unpack(">H", data[i + 2:i + 4])[0]
                i += 2 + seg
    except struct.error:
        return None
    return None


def convert_image(path: Path) -> Path | None:
    png = path.with_suffix(".png")
    ext = path.suffix.lower()
    if ext in SIPS_CONVERTIBLE and shutil.which("sips"):
        if subprocess.run(["sips", "-s", "format", "png", str(path), "--out", str(png)],
                          capture_output=True).returncode == 0 and png.exists():
            return png
    if ext in VECTOR_FORMATS:
        for cmd in (["inkscape", str(path), "--export-type=png", f"--export-filename={png}"],
                    ["soffice", "--headless", "--convert-to", "png", "--outdir", str(path.parent), str(path)]):
            if shutil.which(cmd[0]) and subprocess.run(cmd, capture_output=True).returncode == 0 and png.exists():
                return png
        if shutil.which("qlmanage"):
            subprocess.run(["qlmanage", "-t", "-s", "2000", "-o", str(path.parent), str(path)], capture_output=True)
            thumb = path.parent / (path.name + ".png")
            if thumb.exists():
                thumb.rename(png)
                return png
    return None


# ---------------------------------------------------------------------------
# Reading the document body
# ---------------------------------------------------------------------------

def read_blocks(conv: Converter) -> list[Block]:
    doc = conv.pkg.xml("word/document.xml")
    body = doc.find("w:body", NS)
    blocks: list[Block] = []

    sect = body.find("w:sectPr", NS)
    if sect is not None:
        pg = sect.find("w:pgSz", NS)
        mar = sect.find("w:pgMar", NS)
        try:
            width = int(pg.get(W + "w")) - int(mar.get(W + "left")) - int(mar.get(W + "right"))
            if width > 3000:
                conv.text_width_emu = width * 635
        except (AttributeError, TypeError, ValueError):
            pass

    def para(p, in_table=False):
        ppr = p.find("w:pPr", NS)
        sid = None
        num = None
        lvl = None
        align = ""
        page_end = False
        if ppr is not None:
            ps = ppr.find("w:pStyle", NS)
            sid = ps.get(W + "val") if ps is not None else None
            numpr = ppr.find("w:numPr", NS)
            if numpr is not None:
                nid = numpr.find("w:numId", NS)
                ilvl = numpr.find("w:ilvl", NS)
                if nid is not None and nid.get(W + "val") != "0":
                    num = (nid.get(W + "val"), int(ilvl.get(W + "val")) if ilvl is not None else 0)
            lvl = ppr.find("w:outlineLvl", NS)
            jc = ppr.find("w:jc", NS)
            align = jc.get(W + "val") if jc is not None else ""
            if ppr.find("w:sectPr", NS) is not None:
                page_end = True
            if on(ppr.find("w:pageBreakBefore", NS)) and blocks:
                blocks.append(Block("page"))
        if any(br.get(W + "type") == "page" for br in p.iter(W + "br")):
            page_end = True
        style_name = conv.styles.name(sid)
        if style_name.startswith("toc") or style_name == "table of figures":
            if page_end:
                blocks.append(Block("page"))
            return
        latex, plain, images, stats = conv.inline(p, conv.doc_rels, pstyle=sid)
        for find, repl in conv.fixes:
            latex = latex.replace(escape_text(find), escape_text(repl))
        for img, width in images:
            blocks.append(Block("image", image=img, width=width))
        if re.fullmatch(r"\(?\d{1,2}[).]?", clean(plain)) and not TOKEN_RE.search(plain):
            plain = latex = ""  # a stray list number left over from a PDF layout
        text_present = bool(clean(plain)) or TOKEN_RE.search(plain) or "\\footnote" in latex
        if images and text_present and len(clean(plain)) < 300 and conv.styles.heading_level(sid) is None:
            blocks[-1].caption = re.sub(r"^(\\newline\s*)+", "", latex.strip())
            if page_end:
                blocks.append(Block("page"))
            return
        if not text_present:
            if stats.get("drawing") and not images:
                blocks.append(Block("sep"))
            if page_end:
                blocks.append(Block("page"))
            return
        sizes = stats["sizes"]
        size = max(sizes, key=sizes.get) if sizes else conv.styles.size(sid)
        bold = stats["chars"] > 0 and stats["bold"] >= 0.95 * stats["chars"]
        level = conv.styles.heading_level(sid)
        if level is None and lvl is not None and int(lvl.get(W + "val")) < 9:
            level = int(lvl.get(W + "val")) + 1
        if in_table:
            level = None
        if level is not None and clean(plain):
            blocks.append(Block("heading", text=latex, plain=plain, level=level, style=style_name,
                                size=size, all_bold=bold, align=align, numbered=num is not None,
                                source="style"))
        else:
            b = Block("para", text=latex, plain=plain, style=style_name, all_bold=bold, size=size, align=align)
            if num:
                b.list_kind = conv.numbering.kind(*num)
                b.list_level = num[1]
            elif style_name.startswith("list bullet"):
                b.list_kind = "itemize"
            elif style_name.startswith("list number"):
                b.list_kind = "enumerate"
            blocks.append(b)
        if page_end:
            blocks.append(Block("page"))

    def cell_blocks(tc):
        sub: list[Block] = []
        saved = len(blocks)
        for child in tc:
            if child.tag == W + "p":
                para(child, in_table=True)
            elif child.tag == W + "tbl":
                table(child)
        sub = blocks[saved:]
        del blocks[saved:]
        return sub

    def table(tbl):
        rows, plain_rows = [], []
        for tr in tbl.findall("w:tr", NS):
            cells, pcells = [], []
            for tc in tr.findall("w:tc", NS):
                texts, ptexts = [], []
                for b in cell_blocks(tc):
                    if b.kind == "para":
                        t = b.text.strip()
                        if b.list_kind:
                            t = r"\textbullet~" + t
                        texts.append(t)
                        ptexts.append(b.plain)
                    elif b.kind == "image":
                        texts.append(r"\includegraphics[width=\linewidth]{%s}" % b.image)
                    elif b.kind == "table":
                        for r in b.rows:
                            texts.append(" -- ".join(c for c in r if c))
                        ptexts.extend(" ".join(r) for r in b.plain_rows)
                cells.append(r" \newline ".join(t for t in texts if t))
                pcells.append("\n".join(ptexts))
            if any(clean(c) or "includegraphics" in c for c in cells):
                rows.append(cells)
                plain_rows.append(pcells)
        if not rows:
            return
        ncols = max(len(r) for r in rows)
        flat = [clean(c) for r in plain_rows for c in r]
        # One-column tables holding short lines are headings drawn as boxes.
        if ncols == 1 and all(0 < len(c) <= 140 for c in flat) and not any("\\footnote" in r[0] for r in rows):
            for r, pr in zip(rows, plain_rows):
                text = pr[0].replace("\n", " ")
                level = 1 if strip_heading_prefix(clean(text))[1] == 0 else 2
                blocks.append(Block("heading", text=r[0], plain=text, level=level, source="table", all_bold=True))
            return
        # One-column boxes and one-row side-by-side boxes are page layout, not data.
        if ncols == 1 or (len(rows) == 1 and max(len(c) for c in flat) > 150):
            for r, pr in zip(rows, plain_rows):
                for cell, pcell in zip(r, pr):
                    if not clean(pcell) and "includegraphics" not in cell:
                        continue
                    parts: list[list] = []  # [latex, plain, heading?]
                    for t in cell.split(r" \newline "):
                        m = re.match(r"\\includegraphics\[[^]]*\]\{([^}]*)\}", t)
                        if m:
                            blocks.append(Block("image", image=m.group(1)))
                            continue
                        pl = re.sub(r"\\[a-zA-Z]+\{|\}", "", t)
                        head = bool(re.fullmatch(r"\\(?:underline|textbf)\{[^{}]{3,110}\}\s*", t)) and not parts
                        prev = parts[-1] if parts else None
                        # A PDF breaks every line of a box; keep real paragraph ends only.
                        if prev and not prev[2] and clean(prev[1]) and clean(prev[1])[-1] not in ".!?:”\"" \
                                and clean(pl)[:1] and not head:
                            prev[0] += " " + t
                            prev[1] += " " + pl
                        elif clean(pl):
                            parts.append([t, pl, head])
                    for t, pl, head in parts:
                        blocks.append(Block("para", text=t, plain=pl, all_bold=head))
            return
        blocks.append(Block("table", rows=rows, plain_rows=plain_rows))

    def walk(container):
        for child in container:
            if child.tag == W + "p":
                para(child)
            elif child.tag == W + "tbl":
                table(child)
            elif child.tag == W + "sdt":
                gallery = child.find("w:sdtPr/w:docPartObj/w:docPartGallery", NS)
                if gallery is not None and "table of contents" in gallery.get(W + "val", "").lower():
                    continue
                content = child.find("w:sdtContent", NS)
                if content is not None:
                    walk(content)
            elif child.tag in {W + "customXml", W + "ins"}:
                walk(child)

    walk(body)
    return blocks


# ---------------------------------------------------------------------------
# Documents converted from PDF: notes typed at the foot of every page
# ---------------------------------------------------------------------------

def token_numbers(text: str) -> list[int]:
    return [int(n) for m in TOKEN_RE.finditer(text) for n in re.findall(r"\d+", m.group(2))]


def detect_pdf_mode(conv: Converter, blocks: list[Block]) -> bool:
    if conv.word_notes:
        return False
    led = sum(1 for b in blocks if b.kind == "para" and re.match("\\s*\ue000f\\d", b.plain))
    markers = sum(len(token_numbers(b.plain)) for b in blocks if b.kind in {"para", "heading"})
    return led >= 3 and markers >= 6


def note_pieces(plain: str):
    """Split a foot-of-page line into (number or None, text) pieces."""
    pieces = []
    pos = 0
    current = None
    for m in re.finditer("\ue000f(\\d+)[^\ue001]*\ue001", plain):
        before = plain[pos:m.start()]
        if before.strip() or current is not None:
            pieces.append((current, before))
        current = int(m.group(1))
        pos = m.end()
    rest = plain[pos:]
    if pieces or current is not None:
        pieces.append((current, rest))
    else:
        m = re.match(r"\s*(\d{1,3})\s+(\S.*)$", plain, re.S)
        if m:
            pieces.append((int(m.group(1)), m.group(2)))
    return pieces


def join_note(a: str, b: str) -> str:
    a, b = a.rstrip(), b.strip()
    if not a:
        return b
    if a.endswith(("-", "/", "_", "=")) or b.startswith(("-", "/", "_")):
        return a + b
    return a + " " + b


def rebuild_page_notes(blocks: list[Block], body_size: float, conv: Converter):
    """Pull foot-of-page note lines out of the text; return (blocks, notes by number)."""
    notes: dict[int, deque] = defaultdict(deque)
    defined: list[tuple[int, int]] = []  # (number, anchor block index in out)
    out: list[Block] = []
    state = {"zone": False, "pending": False, "cur": None}

    def close():
        cur = state["cur"]
        if cur is not None:
            text = clean(cur[1]).strip()
            if text:
                notes[cur[0]].append(escape_with_urls(text))
                conv.footnote_log.append(text)
                defined.append((cur[0], cur[2]))
        state["cur"] = None

    def anchor():
        for i in range(len(out) - 1, -1, -1):
            if out[i].kind in {"para", "heading", "table"}:
                return i
        return 0

    small = body_size - 0.4
    for b in blocks:
        if b.kind == "sep":
            state["pending"] = True
            continue
        if b.kind == "page":
            close()
            state.update(zone=False, pending=False)
            out.append(b)
            continue
        if b.kind == "para" and not b.list_kind:
            pieces = note_pieces(b.plain)
            starts_note = bool(pieces) and pieces[0][0] is not None
            head = clean(pieces[0][1])[:260] if starts_note else ""
            citation = bool(YEAR_RE.search(head) or URL_RE.search(head) or re.match(r"(?i)ibid|id\.|see ", head))
            if starts_note and (state["zone"] or state["pending"] or b.size <= small
                                or (citation and re.match("\\s*\ue000f", b.plain))):
                close()
                if not state["zone"]:
                    state["align"] = b.align
                state["zone"] = True
                for num, text in pieces:
                    close()
                    state["cur"] = [num, text, anchor()]
                continue
            text = clean(b.plain)
            body_like = (b.size > small and len(text) > 300 and text[:1].isupper()) or (
                len(text) > 80 and b.align != state.get("align", b.align)) or (
                len(text) > 150 and re.search("\\S\ue000f\\d", b.plain) is not None)
            if state["zone"] and state["cur"] is not None and not body_like:
                # Between a foot-of-page note and the page break everything is note text.
                for num, text in (pieces or [(None, b.plain)]):
                    if num is None:
                        state["cur"][1] = join_note(state["cur"][1], text)
                    else:
                        close()
                        state["cur"] = [num, text, anchor()]
                continue
        close()
        if state["zone"]:
            out.append(Block("page"))  # the notes ended a page even without a Word break
        state.update(zone=False, pending=False)
        out.append(b)
    close()

    # A note whose marker got lost in the PDF conversion is attached to the
    # last paragraph before it, so no source disappears.
    used = defaultdict(int)
    for b in out:
        for n in (token_numbers(b.plain) + token_numbers(b.caption)
                  + [n for row in b.plain_rows for c in row for n in token_numbers(c)]):
            used[n] += 1
    seen = defaultdict(int)
    for num, idx in defined:
        seen[num] += 1
        if seen[num] > used.get(num, 0):
            tok = TOK_OPEN + "f" + str(num) + TOK_CLOSE
            target = out[idx]
            if target.kind == "table" and target.rows:
                target.rows[-1][-1] += tok
            else:
                target.text += tok
                target.plain += tok
            conv.warnings.append(f"note {num} has no marker in the text; attached after the paragraph before it.")
    return out, notes


def merge_split_paragraphs(blocks: list[Block], body_size: float) -> list[Block]:
    """Join paragraphs and tables that a PDF page break cut in two."""
    out: list[Block] = []
    broken = False
    for b in blocks:
        if b.kind in {"page", "sep"}:
            broken = True
            continue
        prev = out[-1] if out else None
        if broken and prev is not None:
            if prev.kind == "table" and b.kind == "table" and len(prev.rows[0]) == len(b.rows[0]):
                for r, pr in zip(b.rows, b.plain_rows):
                    if not clean(pr[0]) and prev.rows:
                        prev.rows[-1] = [(a + " " + c).strip() for a, c in zip(prev.rows[-1], r)]
                        prev.plain_rows[-1] = [(a + " " + c).strip() for a, c in zip(prev.plain_rows[-1], pr)]
                    else:
                        prev.rows.append(r)
                        prev.plain_rows.append(pr)
                broken = False
                continue
            if prev.kind == "para" and b.kind == "para" and should_join(prev, b, body_size):
                a = prev.clean
                if a.endswith("-") and b.clean[:1].islower():
                    prev.text = prev.text.rstrip()[:-1] + b.text.lstrip()
                    prev.plain = prev.plain.rstrip()[:-1] + b.plain.lstrip()
                else:
                    prev.text = prev.text.rstrip() + " " + b.text.lstrip()
                    prev.plain = prev.plain.rstrip() + " " + b.plain.lstrip()
                broken = False
                continue
        broken = False
        out.append(b)
    return out


def should_join(a: Block, b: Block, body_size: float) -> bool:
    ta, tb = a.clean, b.clean
    if not ta or not tb or b.list_kind or b.all_bold or b.size > body_size + 1:
        return False
    if BULLET_RE.match(tb) or NUMBERED_RE.match(tb):
        return False
    if ta[-1] in ".!?:;\"”’)»":
        return False
    if tb[0].islower() or ta.endswith((",", "-", "–")):
        return True
    return len(ta) > 120 and not a.all_bold


# ---------------------------------------------------------------------------
# Headings
# ---------------------------------------------------------------------------

def body_font_size(blocks: list[Block]) -> float:
    weights = defaultdict(int)
    for b in blocks:
        if b.kind == "para" and b.size:
            weights[b.size] += len(b.clean)
    if not weights:
        return 11.0
    return max(weights, key=weights.get)


def looks_like_sentence(text: str) -> bool:
    return text.endswith((".", ";", ",", "!", "?")) and not re.search(r"\b(e\.g|etc|vs|U\.S|D\.C)\.$", text)


def find_hard_headings(blocks: list[Block], body_size: float):
    """Promote untagged lines that are clearly headings (large type, known titles),
    and demote whole sentences that were given a heading style by mistake."""
    for b in blocks:
        if b.kind == "heading" and b.source == "style":
            text = b.clean
            if len(text) > 130 or (looks_like_sentence(text) and len(text) > 80):
                b.kind, b.source = "para", ""
                continue
            continue
        if b.kind != "para" or b.list_kind:
            continue
        text = b.clean
        if not (2 <= len(text) <= 110):
            continue
        if "\\footnote" in b.text:
            continue
        stripped, hint = strip_heading_prefix(text)
        n = norm(text)
        big = b.size >= max(14, body_size * 1.25)
        if big and not looks_like_sentence(text) and len(text) <= 100:
            b.kind, b.source = "heading", "size"
            b.level = 0 if b.size >= 20 else 1
        elif (b.all_bold or b.align == "center") and TOP_TITLE_RE.match(n):
            b.kind, b.source, b.force_top = "heading", "title", True
        elif b.all_bold and hint == 0 and len(text) <= 90:
            b.kind, b.source, b.force_top = "heading", "bold", True


def dedupe_headings(blocks: list[Block]) -> list[Block]:
    """Drop a heading repeated right after itself (Word section-break copies, PDF titles)."""
    out: list[Block] = []
    for b in blocks:
        prev = out[-1] if out else None
        if (prev is not None and prev.kind == "heading" and b.kind in {"heading", "para"}
                and norm(prev.plain) == norm(b.plain) and norm(b.plain)):
            if "[" in prev.plain and "[" not in b.plain:
                prev.text, prev.plain = b.text, b.plain
            continue
        out.append(b)
    return out


def choose_top_level(blocks: list[Block], override=None) -> float:
    heads = [b for b in blocks if b.kind == "heading" and (not b.force_top or b.source in {"style", "size", "table"})]
    if override is not None:
        top = float(override)
    else:
        score = defaultdict(int)
        count = defaultdict(int)
        for h in heads:
            _, hint = strip_heading_prefix(h.clean)
            if hint in (1, 2):
                continue
            count[h.level] += 1
            n = norm(h.plain)
            if TOP_TITLE_RE.match(n):
                score[h.level] += 2
            elif TOPISH_RE.search(n):
                score[h.level] += 1
        if score:
            best = max(score.values())
            top = min(l for l, s in score.items() if s == best)
        elif count:
            top = min(count)
        else:
            top = 1.0
    # Numbered headings sharing the top style with unnumbered titles sit one level below.
    at_top = [h for h in heads if h.level == top]
    plain_top = [h for h in at_top if not h.numbered]
    if plain_top and len(plain_top) < len(at_top):
        if sum(1 for h in plain_top if TOPISH_RE.search(norm(h.plain))) >= 2:
            for h in at_top:
                if h.numbered:
                    h.level = top + 0.5
    return top


def assign_top_ranks(blocks: list[Block], top: float):
    for b in blocks:
        if b.kind != "heading":
            continue
        _, hint = strip_heading_prefix(b.clean)
        b.rank_hint = hint
        if b.force_top or hint == 0:
            b.rank = 0
        elif hint in (1, 2):
            b.rank = None  # ranked inside its section
        elif b.level <= top:
            b.rank = 0
        else:
            b.rank = None


def rank_section_headings(blocks: list[Block], body_size: float):
    """Give headings inside one section ranks 1, 2, 3.

    Typed numbering decides first ("1.2" is a subsection), then Word heading
    levels, and lines recognised only by their bold type sit one level below
    the heading before them."""
    soft_headings(blocks, body_size)
    heads = [b for b in blocks if b.kind == "heading"]
    for h in heads:
        if h.rank_hint is None:
            h.rank_hint = strip_heading_prefix(h.clean)[1]
    hard = [h for h in heads if h.source != "soft"]
    plain_levels = sorted({h.level for h in hard if h.rank_hint not in (1, 2)})
    hinted = [h for h in heads if h.rank_hint in (1, 2)]
    hinted_hard_levels = [h.level for h in hinted if h.source != "soft"]
    last = 0
    for h in heads:
        if h.rank_hint in (1, 2):
            h.rank = h.rank_hint
        elif h.source != "soft":
            h.rank = 1 + plain_levels.index(h.level)
            if hinted and not (hinted_hard_levels and h.level <= min(hinted_hard_levels)):
                h.rank = max(h.rank, 2)
        else:
            h.rank = min(last + 1, 3)
        if h.source != "soft" or h.rank_hint in (1, 2):
            last = h.rank


def soft_headings(blocks: list[Block], body_size: float):
    """Bold or short title-like lines in the running text become headings (ranked later)."""
    for i, b in enumerate(blocks):
        if b.kind != "para":
            continue
        text = b.clean
        if not text or len(text) > 100:
            continue
        nxt = next((x for x in blocks[i + 1:] if x.kind != "image"), None)
        if nxt is None or nxt.kind == "heading":
            continue
        if b.list_kind:
            # A bold numbered line ("1. Mandate") on its own, or over a deeper
            # list, is a heading typed as a list item.
            prev = blocks[i - 1] if i else None
            lone = not (prev is not None and prev.kind == "para" and prev.list_kind == b.list_kind
                        and prev.list_level == b.list_level)
            opens = (nxt.kind != "para" or not nxt.list_kind
                     or (nxt.list_level > b.list_level and not nxt.all_bold))
            if lone and opens and b.all_bold and not looks_like_sentence(text) and len(text) <= 80:
                b.kind, b.source, b.list_kind = "heading", "soft", None
            continue
        stripped, hint = strip_heading_prefix(text)
        bold_line = (b.all_bold and not looks_like_sentence(text)
                     and not (text.endswith(":") and len(text) > 60)
                     and not BULLET_RE.match(text) and not NUMBERED_RE.match(text))
        prev = blocks[i - 1] if i else None
        last_word = re.sub(r"\W", "", text.split()[-1].lower()) if text.split() else ""
        label_list = bool(re.match(r"^[\w\s]{2,30}:\s", text)) and "," in text  # "Countries: A, B, C"
        title_like = (not looks_like_sentence(text) and not text.endswith(":") and len(text) <= 70
                      and not label_list
                      and text[0].isupper() and len(text.split()) <= 9
                      and last_word not in SMALL_WORDS | {"include", "includes", "are", "is", "were", "following"}
                      and (nxt.kind == "table" or (nxt.kind == "para" and (len(nxt.clean) > 40 or nxt.list_kind)))
                      and (prev is None or prev.kind != "para" or len(prev.clean) > 100 or prev.list_kind)
                      and capitalised_ratio(text) >= 0.5 and not BULLET_RE.match(text))
        if bold_line or title_like:
            b.kind, b.source, b.rank_hint = "heading", "soft", hint


def capitalised_ratio(text: str) -> float:
    words = [w for w in re.findall(r"[A-Za-zÀ-ÿ][\w’'\-]*", text) if w.lower() not in SMALL_WORDS]
    if not words:
        return 0.0
    if len(words) <= 3:
        return 1.0
    return sum(1 for w in words if w[0].isupper()) / len(words)


def acronyms_from(blocks) -> set[str]:
    words = set()
    for b in blocks:
        if b.kind == "para":
            text = b.clean
            if text.upper() == text:
                continue
            words.update(w for w in re.findall(r"\b[A-Z][A-Z0-9\-/&]{1,}\b", text) if w not in COMMON_CAPS_WORDS)
    return words


def title_case(text: str, keep: set[str]) -> str:
    letters = [c for c in text if c.isalpha()]
    if not letters or text.upper() != text or sum(c.isupper() for c in letters) < 0.9 * len(letters):
        return text
    words = text.split(" ")
    out = []
    for i, w in enumerate(words):
        core = re.sub(r"[^\w\-/&’']", "", w)
        if core in keep or re.fullmatch(r"[IVX]+", core) or (len(core) <= 3 and core in {"UN", "EU", "US", "UK", "AI", "DDR"}):
            out.append(w)
        elif i > 0 and core.lower() in SMALL_WORDS:
            out.append(w.lower())
        else:
            out.append("-".join(p[:1] + p[1:].lower() for p in w.split("-")))
    return " ".join(out)


def heading_title(b: Block, keep: set[str]) -> tuple[str, str]:
    """(LaTeX title with note tokens, short plain title) for a heading block."""
    text = re.sub(r"\s+", " ", b.plain.replace("\n", " ")).strip()
    text, _ = strip_heading_prefix(clean(text)) if not TOKEN_RE.search(text) else strip_heading_prefix(text)
    text = text.replace("[", "").replace("]", "").strip()
    text = re.sub(r"\s*:\s*$", "", text)
    text = title_case(text, keep)
    text = re.sub(r"\b[QW]ARMAS\b", "QARMAs", text, flags=re.I) if re.search(r"\b[QW]ARMAs?\b", text, re.I) else text
    tokens = "".join(m.group(0) for m in TOKEN_RE.finditer(text))
    notes = "".join(r"\footnote{%s}" % f for f in footnote_bodies(b.text))
    plain = clean(text)
    return escape_with_urls(plain) + tokens + notes, escape_text(plain)


# ---------------------------------------------------------------------------
# Emitting LaTeX
# ---------------------------------------------------------------------------

def typed_lists(blocks: list[Block]):
    """Lines typed with "•" or "1." become list items."""
    for i, b in enumerate(blocks):
        if b.kind != "para" or b.list_kind:
            continue
        text = b.clean
        if BULLET_RE.match(text):
            b.list_kind = "itemize"
            b.text = BULLET_RE.sub("", b.text.lstrip(), count=1)
        elif NUMBERED_RE.match(text):
            prev = blocks[i - 1] if i else None
            nxt = blocks[i + 1] if i + 1 < len(blocks) else None
            if any(x is not None and x.kind == "para" and NUMBERED_RE.match(x.clean) for x in (prev, nxt)) or \
                    (prev is not None and prev.list_kind == "enumerate"):
                b.list_kind = "enumerate"
                b.text = re.sub(r"^(\\textbf\{)?\s*\d{1,2}[.)]\s*", r"\1", b.text.lstrip(), count=1)


def clean_caption(latex: str) -> str:
    """The class numbers figures itself: drop a typed "Figure 3:" and stray dashes."""
    cap = latex.strip()
    cap = re.sub(r"^\\(?:textbf|emph)\{([^{}]*)\}", r"\1", cap)
    cap = CAPTION_RE.sub("", cap, count=1)
    return re.sub(r"^[\s\-–—:.]+", "", cap).strip()


def attach_captions(blocks: list[Block]) -> list[Block]:
    """Figure captions and "Source:" lines next to an image become its caption."""
    out: list[Block] = []
    for i, b in enumerate(blocks):
        text = b.clean
        is_cap = b.kind in {"para", "heading"} and len(text) < 300 and (
            b.style == "caption" or CAPTION_RE.match(text) or SOURCE_RE.match(text))
        if is_cap:
            prev_img = next((x for x in reversed(out[-2:]) if x.kind == "image"), None)
            next_img = None
            if prev_img is None:
                for x in blocks[i + 1:i + 3]:
                    if x.kind == "image":
                        next_img = x
                        break
            target = prev_img or next_img
            if target is not None:
                cap = clean_caption(b.text)
                target.caption = (target.caption + ". " + cap if target.caption and not target.caption.endswith(".")
                                  else (target.caption + " " + cap).strip())
                continue
        out.append(b)
    return out


def table_spec(b: Block) -> str:
    """Relative column widths from the amount of text, never narrower than the longest word."""
    ncols = max(len(r) for r in b.rows)
    chars_per_line = 82.0  # \small Montserrat across the text width
    lengths, minimum = [], []
    for c in range(ncols):
        cells = [clean(r[c]) for r in b.plain_rows if c < len(r)]
        vals = [len(x) for x in cells] or [1]
        lengths.append(max(4.0, statistics.mean(vals)) ** 0.5)
        longest = max((len(w) for x in cells for w in x.split()), default=4)
        minimum.append(ncols * (min(longest, 22) + 2.5) / chars_per_line)
    total = sum(lengths)
    factors = [ncols * l / total for l in lengths]
    for _ in range(3):
        short = [i for i, f in enumerate(factors) if f < minimum[i]]
        if not short:
            break
        for i in short:
            factors[i] = minimum[i]
        rest = [i for i in range(ncols) if i not in short]
        spare = ncols - sum(factors[i] for i in short)
        weight = sum(lengths[i] for i in rest) or 1
        for i in rest:
            factors[i] = spare * lengths[i] / weight
    factors = [round(f, 2) for f in factors]
    factors[-1] = round(ncols - sum(factors[:-1]), 2)
    if max(factors) - min(factors) < 0.15:
        return ""
    return "".join("Y{%s}" % f for f in factors)


UNDERLINE_RE = re.compile(r"\\underline\{((?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}")


def tidy_paragraph(text: str, heading: bool = True) -> str:
    """No line break at the edges of a paragraph; a blank line typed as two breaks becomes \\par.
    Underlines are dropped: they cannot break across lines (links are coloured anyway)."""
    text = re.sub(r"^(\s*\\newline\s*)+|(\s*\\newline\s*)+$", "", text.strip())
    text = re.sub(r"(\s*\\newline\s*){2,}", r"\\par ", text).strip()
    m = re.match(r"^(?:\\underline|\\textbf)\{([^{}]{3,110})\}\s*\\newline\s*(?=\S)", text)
    if m and heading:
        text = "\\minorheading{%s}\n" % m.group(1).strip() + text[m.end():]
    while UNDERLINE_RE.search(text):
        text = UNDERLINE_RE.sub(r"\1", text)
    return text


def normalise_list_levels(blocks: list[Block]):
    """Each run of list items starts at level 0 and never skips a level."""
    run: list[Block] = []

    def fix():
        if not run:
            return
        base = min(b.list_level for b in run)
        depth = -1
        for b in run:
            lvl = min(b.list_level - base, depth + 1)
            b.list_level = max(lvl, 0)
            depth = b.list_level
        run.clear()

    for b in blocks:
        if b.kind == "para" and b.list_kind:
            run.append(b)
        else:
            fix()
    fix()


def emit_blocks(blocks: list[Block], lead: bool = False) -> list[str]:
    lines: list[str] = []
    stack: list[str] = []
    for b in blocks:
        if b.kind == "para":
            b.text = tidy_paragraph(b.text, heading=not b.list_kind)
    blocks = [b for b in blocks if not (b.kind == "para" and not b.text)]
    normalise_list_levels(blocks)

    def close_to(level):
        while len(stack) > level:
            lines.append("  " * (len(stack) - 1) + r"\end{%s}" % stack.pop())
            if not stack:
                lines.append("")

    first_para = True
    for b in blocks:
        if b.kind == "para" and b.list_kind:
            target = b.list_level + 1
            close_to(target)
            while len(stack) < target:
                lines.append("  " * len(stack) + r"\begin{%s}" % b.list_kind)
                stack.append(b.list_kind)
            lines.append("  " * len(stack) + r"\item " + b.text.strip())
            first_para = False
            continue
        close_to(0)
        if b.kind == "para":
            text = b.text.strip()
            if lead and first_para and not b.all_bold and not text.startswith("\\minorheading"):
                unbold = lambda t: re.sub(r"\\textbf\{([^{}]*)\}", r"\1", t)
                if 100 <= len(b.clean) <= 380:
                    text = r"\lead{%s}" % unbold(text)
                else:
                    head, tail = split_first_sentence(text)
                    if tail and 90 <= len(clean(re.sub(r"\\footnote\{.*", "", head))) <= 320:
                        lines.append(r"\lead{%s}" % unbold(head))
                        lines.append("")
                        text = tail
            lines.append(text)
            lines.append("")
            first_para = False
        elif b.kind == "raw":
            lines.append("")
            lines.append(b.text)
            lines.append("")
            first_para = False
        elif b.kind == "image":
            cap = clean_caption(b.caption)
            ctoks = ""
            if cap:
                cap = TOKEN_RE.sub(lambda m: TOK_OPEN + "c" + m.group(2) + TOK_CLOSE, cap)
                ctoks = TOK_FLUSH if TOKEN_RE.search(cap) or "\\footnote" in cap else ""
                cap = cap.replace("\\footnote", "\\protect\\footnote")
            width = "" if b.width >= 0.99 else "[%s]" % b.width
            lines.append(r"\guidefig%s{%s}%s%s" % ("[%s]" % cap if cap else "", b.image, width, ctoks))
            lines.append("")
            first_para = False
        elif b.kind == "table":
            ncols = max(len(r) for r in b.rows)
            spec = table_spec(b)
            header = (len(b.rows) > 2 and all(len(clean(c)) <= 40 for c in b.plain_rows[0])
                      and any(len(clean(c)) > 40 for r in b.plain_rows[1:] for c in r))
            lines.append(r"\begin{guidetable}%s{%d}" % ("[%s]" % spec if spec else "", ncols))
            for i, row in enumerate(b.rows):
                row = [tidy_paragraph(c, heading=False) for c in row] + [""] * (ncols - len(row))
                if i == 0 and header:
                    row = [r"\textbf{%s}" % c if c and not c.startswith(r"\textbf") else c for c in row]
                lines.append("  " + " & ".join(c.replace("\n", " ") for c in row) + r" \\")
                if i == 0 and header:
                    lines.append(r"  \midrule")
                elif i < len(b.rows) - 1 and not header:
                    lines.append(r"  \midrule")
            lines.append(r"\end{guidetable}")
            lines.append("")
            first_para = False
    close_to(0)
    return lines


def split_first_sentence(latex: str) -> tuple[str, str]:
    """Split LaTeX after its first sentence (and any note right after it)."""
    depth = 0
    i = 0
    n = len(latex)
    while i < n:
        c = latex[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif c in ".!?" and depth == 0 and i > 40:
            j = i + 1
            while True:
                m = re.match(r"(\\footnote\{|\ue000[fc][^\ue001]*\ue001)", latex[j:])
                if not m:
                    break
                if m.group(0).startswith("\ue000"):
                    j += m.end()
                    continue
                k, d = j + m.end(), 1
                while k < n and d:
                    if latex[k] == "\\":
                        k += 2
                        continue
                    d += {"{": 1, "}": -1}.get(latex[k], 0)
                    k += 1
                j = k
            prev = latex[max(0, i - 3):i]
            if re.match(r" [A-Z][a-z]?\.?$", " " + prev[-2:]) or re.search(r"\b[A-Z]$", prev):
                i += 1
                continue
            rest = latex[j:]
            if re.match(r"\s+[A-Z“\"(]", rest):
                return latex[:j].strip(), rest.strip()
        i += 1
    return latex, ""


def footnote_bodies(tex: str) -> list[str]:
    bodies = []
    for m in re.finditer(r"\\footnote(?:text)?\{", tex):
        k, d = m.end(), 1
        while k < len(tex) and d:
            if tex[k] == "\\":
                k += 2
                continue
            d += {"{": 1, "}": -1}.get(tex[k], 0)
            k += 1
        bodies.append(tex[m.end():k - 1])
    return bodies


def text_key(text: str) -> str:
    text = re.sub(r"\\(url|nolinkurl|email)\{([^}]*)\}", r" \2 ", text)
    text = re.sub(r"\\href\{[^}]*\}", " ", text)
    text = re.sub(r"\\[a-zA-Z]+\*?", " ", text)
    text = text.replace("\\", "")
    return re.sub(r"[^0-9a-zà-ÿ]+", "", text.lower())


def heading_line(b: Block, keep: set[str]) -> str:
    title, short = heading_title(b, keep)
    rank = b.rank or 1
    if rank >= 3:
        return r"\minorheading{%s}" % title
    cmd = {1: "subsection", 2: "subsubsection"}[rank]
    if TOKEN_RE.search(title) or "\\footnote" in title:
        return "\\%s[%s]{%s}" % (cmd, short, title)
    return "\\%s{%s}" % (cmd, title)


# -- abbreviations -----------------------------------------------------------

ABBR_SPLIT_RES = [
    re.compile(r"(?<=\S) +(?=[A-Z][A-Za-z0-9&/\-]{1,11}\t)"),
    re.compile(r"(?<=\S)\s+(?=[A-Z][A-Za-z0-9&/\-]{0,11}[A-Z0-9][a-z]?s?\s*[:=]\s)"),
    re.compile(r"(?<=[a-z\)])\s+(?=[A-Z][A-Z0-9&/\-]{1,11}s?(?:\s\([^)]{1,40}\))?\s[–—\-.]\s)"),
    re.compile(r"(?<=[a-z\)])\s+(?=[A-Z]{2,}[A-Z][a-z])"),
    re.compile(r"(?<=[a-z\)])(?=[A-Z][A-Z0-9]{1,10}\s[–—\-]\s)"),
]
ABBR_PARSE_RES = [
    re.compile(r"^([^\s:=]+)\t+(.+)$", re.S),
    re.compile(r"^(\S[^:=]{0,40}?)\s*[:=]\s+(.+)$", re.S),
    re.compile(r"^(\S.{0,40}?)\s+[–—\-.]\s+(.+)$", re.S),
    re.compile(r"^([A-Z][A-Za-z0-9\-–/&.]*[A-Z0-9][A-Za-z0-9\-–/&.]*)\s+(.+)$", re.S),
    re.compile(r"^([A-Z][A-Z0-9]+?)([A-Z][a-z].+)$", re.S),
]


def split_abbreviations(line: str) -> list[str]:
    parts = [line]
    for rx in ABBR_SPLIT_RES:
        nxt = []
        for p in parts:
            nxt.extend(x for x in rx.split(p) if x.strip())
        parts = nxt
    return parts


def parse_abbreviation(entry: str):
    entry = entry.strip()
    for rx in ABBR_PARSE_RES:
        m = rx.match(entry)
        if m:
            key, value = m.group(1).strip(), m.group(2).strip()
            has_caps = sum(c.isupper() for c in key) >= 1 or (len(key) <= 5 and key.isalpha())
            if 1 <= len(key) <= 30 and value and has_caps and len(key.split()) <= 4:
                return key, value
    return None


def abbreviation_lines(blocks: list[Block]) -> list[str]:
    entries: list[tuple[str, str]] = []
    before: list[Block] = []
    after: list[Block] = []
    for b in blocks:
        if b.kind == "table":
            for row in b.plain_rows:
                cells = [clean(c) for c in row if clean(c)]
                if len(cells) >= 2:
                    entries.append((cells[0], " ".join(cells[1:])))
            continue
        if b.kind not in {"para"}:
            (after if entries else before).append(b)
            continue
        found = []
        leftovers = []
        for line in re.split(r"\n+", TOKEN_RE.sub("", b.plain)):
            line = re.sub(r"[ \t]{2,}", "\t", line.strip())
            if not line:
                continue
            for entry in split_abbreviations(line):
                parsed = parse_abbreviation(entry)
                if parsed and len(line) < 400:
                    found.append(parsed)
                else:
                    leftovers.append(entry)
        if found and not leftovers:
            entries.extend(found)
        else:
            (after if entries else before).append(b)
    seen = set()
    lines = emit_blocks(before)
    lines.append(r"\begin{abbreviations}")
    for key, value in entries:
        k = (key.lower(), value.lower())
        if k in seen:
            continue
        seen.add(k)
        value = value.rstrip(" ;,")
        lines.append(r"  \abbr{%s}{%s}" % (escape_text(key), escape_with_urls(value)))
    lines.append(r"\end{abbreviations}")
    lines.append("")
    lines.extend(emit_blocks(after))
    return lines


# -- references --------------------------------------------------------------

def reference_entries(blocks: list[Block], pdf_mode: bool) -> list[str]:
    """One entry per work: a line holding only a URL, or a fragment cut off by a PDF
    page, joins the entry before it; entries a PDF run together are split again."""
    paras = [b for b in blocks if b.kind == "para" and b.clean]
    entries: list[list] = []  # [latex, plain, from_list]
    for b in paras:
        text = b.clean
        latex = escape_with_urls(text) if pdf_mode else tidy_paragraph(b.text, heading=False)
        if entries and not b.list_kind and not entries[-1][2]:
            prev = entries[-1][1]
            url_only = bool(re.match(r"(https?://|www\.)\S+$", text))
            short_tail = (not YEAR_RE.search(text[:220]) and len(text) < 110
                          and YEAR_RE.search(prev) and not URL_RE.search(prev))
            if url_only or (pdf_mode and not YEAR_RE.search(text[:220])) or short_tail:
                entries[-1][0] = entries[-1][0].rstrip() + " " + latex
                entries[-1][1] = join_note(prev, text)
                continue
            if pdf_mode:
                m = re.match(r"^([A-Za-z][\w&,.\s]{0,40}?\.)\s+(?=[A-Z].{0,160}" + YEAR_RE.pattern + ")", text)
                if m and not prev.rstrip().endswith((".", "/")) and not YEAR_RE.search(m.group(1)):
                    entries[-1][1] = join_note(prev, m.group(1))
                    entries[-1][0] = escape_with_urls(entries[-1][1])
                    text = text[m.end():]
                    latex = escape_with_urls(text)
        entries.append([latex, text, bool(b.list_kind)])
    if not pdf_mode:
        return [e[0] for e in entries]
    return [escape_with_urls(x) for e in entries for x in split_after_urls(e[1])]


def split_after_urls(line: str) -> list[str]:
    parts = []
    pos = 0
    for m in re.finditer(r"(https?://\S+)\s+(?=[A-Z][^()]{1,150}" + YEAR_RE.pattern + ")", line):
        parts.append(line[pos:m.end(1)])
        pos = m.end()
    parts.append(line[pos:])
    return [p.strip() for p in parts if p.strip()]


def reference_lines(blocks: list[Block], pdf_mode: bool) -> list[str]:
    lines = []
    intro = []
    for b in blocks:
        if b.kind == "para" and b.clean and not YEAR_RE.search(b.clean) and not URL_RE.search(b.clean) \
                and len(b.clean) > 60 and not lines and not intro:
            intro.append(b)
        else:
            break
    rest = blocks[len(intro):]
    out = emit_blocks(intro)
    entries = reference_entries(rest, pdf_mode)
    if entries:
        out.append(r"\begin{referencelist}")
        for e in entries:
            out.append(r"  \refitem " + e)
        out.append(r"\end{referencelist}")
    other = [b for b in rest if b.kind in {"image", "table"}]
    out.extend(emit_blocks(other))
    return out


# -- letters -----------------------------------------------------------------

def is_closing(text: str) -> bool:
    return len(text) <= 90 and bool(CLOSING_RE.match(text.strip()))


def is_name_line(b: Block | None) -> bool:
    if b is None or b.kind != "para" or b.list_kind:
        return False
    text = b.clean.rstrip(".")
    if not text or len(text) > 120 or looks_like_sentence(b.clean.rstrip(".") + ""):
        return False
    words = re.findall(r"[\wÀ-ÿ’'\-]+", text)
    if not words or len(words) > 16:
        return False
    caps = sum(1 for w in words if w[0].isupper() or w.lower() in {"and", "y", "the", "&", "de", "da", "dos"})
    return caps >= 0.7 * len(words)


def is_role_line(b: Block | None) -> bool:
    return (b is not None and b.kind == "para" and len(b.clean) <= 110 and bool(ROLE_WORDS_RE.search(b.clean))
            and not looks_like_sentence(b.clean))


def split_name_role(name: str) -> tuple[str, str]:
    """ "Ana Pérez, Chair of UNSC" -> ("Ana Pérez", "Chair of UNSC"); "The DISEC Chairs" stays whole."""
    m = re.match(r"^(.*?)(?:,\s*|\s+)((?:Head |Co-|Vice-)?(?:Chairs?|Presidentes?|Directors?)\s+(?:of|del?|,)\b.*"
                 r"|(?:Head |Co-)?Chairs?\s*(?:&|and)\s*(?:Head |Co-)?Chairs?\b.*)$", name)
    if m and m.group(1).strip() and not re.match(r"(?i)^(the|your|los|las)\b", m.group(1).strip()):
        return m.group(1).strip(" ,"), m.group(2).strip()
    return name, ""


def introduced_names(text: str, people: list[str]) -> list[str]:
    """Names the chairs introduce themselves with ("My name is Nia", "Nosotras somos A y B")."""
    names = []
    for m in re.finditer(r"(?:[Mm]y name is|I am|I’m|I'm|[Mm]e llamo|[Ss]oy|[Ss]omos|our names are|[Ww]e are)\s+"
                         r"((?:[A-ZÁÉÍÓÚÑ][\wÀ-ÿ’'\-]+(?:\s+|,\s*|\s+(?:y|and|&)\s+)?){1,8})", text):
        for part in re.split(r",\s*|\s+(?:y|and|&)\s+", m.group(1)):
            part = part.strip()
            words = part.split()
            if not words or words[0] in {"I", "IE", "A", "The", "From", "In"}:
                continue
            first = words[0]
            known = [p for p in people if p.split()[0].lower() == first.lower()]
            if known:
                names.append(known[0])
            elif any(first.lower() == p.lower() for p in people):
                names.append(first)
    out = []
    for n in names:
        if not any(n == o or o.startswith(n) for o in out):
            out = [o for o in out if not n.startswith(o)] + [n]
    return out


def full_name(first: str, text: str, people: list[str]) -> str:
    first = first.strip()
    parts = re.split(r"(,\s*(?:and\s+|y\s+)?|\s+&\s+|\s+and\s+|\s+y\s+)", first)
    if len(parts) > 1:
        # "Nils & Julius" -> "Nils Bischof & Julius Masrouki" when the config knows them
        names = [full_name(p, text, people) if i % 2 == 0 else p for i, p in enumerate(parts)]
        return "".join(names)
    if len(first.split()) > 1:
        return first
    for p in people:
        if p.split()[0].lower() == first.lower():
            return p
    m = re.search(r"\b(%s(?:\s+(?:[A-ZÁÉÍÓÚÑ][\wÀ-ÿ’'\-]+|de|da|dos|del)){1,3})" % re.escape(first), text)
    if m:
        name = re.sub(r"\s+(?:de|da|dos|del)$", "", m.group(1))
        if not re.search(r"\b(I|I’m|And|The|From|In|At)\b", name.split(" ", 1)[1] if " " in name else ""):
            return name
    return first


def people_from(meta: dict) -> list[str]:
    names = []
    for key in ("authors", "editor", "chairs"):
        for part in re.split(r",|&|\band\b|\by\b", meta.get(key, "") or ""):
            part = re.sub(r"\(.*?\)", "", part).strip()
            if part and part[0].isupper():
                names.append(part)
    return sorted(names, key=lambda n: -len(n.split()))


def welcome_lines(blocks: list[Block], meta: dict, fallback: str) -> list[str]:
    people = people_from(meta)
    items = [b for b in blocks]
    letters = []  # (body blocks, closing, name, role)
    cur: list[Block] = []
    i = 0
    while i < len(items):
        b = items[i]
        text = b.clean if b.kind == "para" else ""
        nxt = items[i + 1] if i + 1 < len(items) else None
        if b.kind == "para" and is_closing(text) and is_name_line(nxt):
            name, role = split_name_role(nxt.clean)
            step = 2
            after = items[i + 2] if i + 2 < len(items) else None
            if not role and is_role_line(after) and not is_closing(after.clean):
                role = after.clean
                step = 3
            letters.append((cur, text, name.rstrip("."), role))
            cur = []
            i += step
            continue
        if b.kind == "para" and nxt is not None and is_name_line(nxt) and not is_closing(text):
            m = re.search(r"(?:^|(?<=[.!?]\s))((?:[^.!?]*?\b)?(?:yours sincerely|sincerely|best regards|"
                          r"kind regards|warm regards|regards|your chairs?|best|cheers),?)\s*$", text, re.I)
            if m and len(m.group(1)) <= 40 and (i + 2 >= len(items) or items[i + 2].kind != "para"
                                                 or is_role_line(items[i + 2]) or len(items[i + 2].clean) > 40):
                body_text = text[:m.start(1)].strip()
                if body_text:
                    cur.append(Block("para", text=escape_with_urls(body_text), plain=body_text))
                name, role = split_name_role(nxt.clean)
                step = 2
                after = items[i + 2] if i + 2 < len(items) else None
                if not role and is_role_line(after):
                    role = after.clean
                    step = 3
                letters.append((cur, m.group(1).strip(), name.rstrip("."), role))
                cur = []
                i += step
                continue
        cur.append(b)
        i += 1
    trailing = cur
    if not letters:
        last = next((b for b in reversed(trailing) if b.kind == "para"), None)
        if last is not None and is_name_line(last) and ("," in last.clean or " and " in last.clean
                                                       or len(last.clean.split()) <= 4):
            idx = trailing.index(last)
            name, role = split_name_role(last.clean)
            letters.append((trailing[:idx], "", name.rstrip("."), role))
            trailing = trailing[idx + 1:]
        else:
            letters.append((trailing, "", "", ""))
            trailing = []

    out = []
    for body, closing, name, role in letters:
        text_all = " ".join(b.clean for b in body)
        if name:
            heading = full_name(name, text_all, people)
        else:
            found = introduced_names(text_all, people)
            heading = (", ".join(found[:-1]) + " & " + found[-1] if len(found) > 1 else found[0]) if found else fallback
        signame = name
        out.append(r"\begin{chairletter}%s{%s}" % ("[%s]" % escape_text(role) if role else "", escape_text(heading)))
        out.extend(letter_body(body, people))
        if signame:
            out.append(r"\signoff%s{%s}" % ("[%s]" % escape_text(closing) if closing else "", escape_text(signame)))
        out.append(r"\end{chairletter}")
        out.append("")
    out.extend(emit_blocks(trailing))
    return out


def letter_body(blocks: list[Block], people: list[str] | None = None) -> list[str]:
    body = []
    for b in blocks:
        if b.kind == "heading" or (b.kind == "para" and b.all_bold and len(b.clean) <= 60
                                   and not looks_like_sentence(b.clean)):
            label = clean(b.plain).rstrip(":").strip()
            if people and len(label.split()) == 1:
                label = next((p for p in people if p.split()[0].lower() == label.lower()), label)
            body.append(Block("raw", text=r"\minorheading{%s}" % escape_text(label)))
        else:
            body.append(b)
    return [l for l in emit_blocks(body)]


STAFF_RE = re.compile(r"^(.{2,40}?)\s+[-–—:]\s+(.{3,60})$")


def staff_lines(blocks: list[Block]) -> list[str]:
    out = []
    groups: list[tuple[str, str, list[Block]]] = []
    pre: list[Block] = []
    for b in blocks:
        text = b.clean
        m = STAFF_RE.match(text) if (b.kind == "heading" or b.all_bold) and b.kind != "image" else None
        if m and ROLE_WORDS_RE.search(m.group(1)):
            groups.append((m.group(1).strip(), m.group(2).strip(), []))
        elif groups:
            groups[-1][2].append(b)
        else:
            pre.append(b)
    out.extend(emit_blocks(pre))
    for role, name, body in groups:
        out.append(r"\begin{chairletter}[%s]{%s}" % (escape_text(role), escape_text(name)))
        out.extend(letter_body(body, []))
        out.append(r"\end{chairletter}")
        out.append("")
    return out


# -- sections ----------------------------------------------------------------

@dataclass
class Section:
    heading: Block
    blocks: list[Block] = field(default_factory=list)

    @property
    def plain(self) -> str:
        return self.heading.clean


def split_sections(blocks: list[Block]):
    front: list[Block] = []
    sections: list[Section] = []
    tops = [i for i, b in enumerate(blocks) if b.kind == "heading" and b.rank == 0]
    start = None
    for i in tops:
        n = norm(blocks[i].plain)
        if TOPISH_RE.search(n) or CONTENTS_RE.match(n):
            start = i
            break
    if start is None and tops:
        start = tops[0]
    if start is None:
        return blocks, []
    front = blocks[:start]
    current = None
    for b in blocks[start:]:
        if b.kind == "heading" and b.rank == 0:
            current = Section(b)
            sections.append(current)
        else:
            current.blocks.append(b)
    return front, sections


def section_kind(sec: Section) -> str:
    n = norm(sec.heading.plain)
    for kind, rx in SECTION_KINDS:
        if rx.search(n):
            return kind
    return "normal"


def section_tex(sec: Section, kind: str, keep: set[str], meta: dict, opts: dict) -> str:
    title, short = heading_title(sec.heading, keep)
    out = []
    if kind == "references":
        out.append(r"\unnumberedsection{%s}" % short)
    elif TOKEN_RE.search(title) or "\\footnote" in title:
        out.append("\\section[%s]{%s}" % (short, title))
    else:
        out.append(r"\section{%s}" % title)
    out.append("")
    blocks = attach_captions(sec.blocks)
    typed_lists(blocks)
    if kind == "welcome":
        out.extend(welcome_lines(blocks, meta, opts.get("letter_fallback", "The Chairs")))
    elif kind == "staff":
        out.extend(staff_lines(blocks))
    elif kind == "abbreviations":
        out.extend(abbreviation_lines(blocks))
    elif kind == "references":
        out.extend(reference_lines(blocks, opts.get("pdf_mode", False)))
    else:
        rank_section_headings(blocks, opts.get("body_size", 11))
        chunk: list[Block] = []
        first = True

        def flush():
            nonlocal first
            if chunk:
                out.extend(emit_blocks(chunk, lead=first and opts.get("auto_lead", True)))
                first = False
                chunk.clear()

        for b in blocks:
            if b.kind == "heading":
                flush()
                first = False
                out.append("")
                out.append(heading_line(b, keep))
                out.append("")
            else:
                chunk.append(b)
        flush()
    text = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


class NoteResolver:
    """Replace note tokens by \\footnote{...} (rebuilt notes) or superscripts."""

    def __init__(self, notes, pdf_mode: bool):
        self.notes = notes
        self.pdf_mode = pdf_mode
        self.pending: list[str] = []
        self.unresolved: list[str] = []

    def __call__(self, tex: str) -> str:
        def repl(m):
            kind, digits = m.group(1), m.group(2)
            if not self.pdf_mode:
                return r"\textsuperscript{%s}" % escape_text(digits.strip())
            out = []
            for n in re.findall(r"\d+", digits):
                q = self.notes.get(int(n))
                if q:
                    note = q.popleft()
                    if kind == "c":
                        out.append(r"\protect\footnotemark")
                        self.pending.append(note)
                    else:
                        out.append(r"\footnote{%s}" % note)
                else:
                    out.append(r"\textsuperscript{%s}" % n)
                    self.unresolved.append(n)
            return "".join(out)

        tex = TOKEN_RE.sub(repl, tex)

        def flush(_m):
            texts = "".join(r"\footnotetext{%s}" % t for t in self.pending)
            self.pending = []
            return texts

        return re.sub(TOK_FLUSH, flush, tex)


def guess_metadata(front: list[Block]) -> dict[str, str]:
    lines = []
    for b in front:
        if b.kind in {"para", "heading"}:
            for line in b.clean.split("\n"):
                if line.strip():
                    lines.append(line.strip())
    meta = {"committee": "", "longname": "", "topic": "", "authors": "", "editor": ""}
    rest = []
    chairs = []
    skip = re.compile(r"^(title page|table of contents?|contents|index|study guide|onglet \d+|mockup|"
                      r"ieumun( 20\d\d)?|crisis study guide|.* study guide|ie tower.*)$", re.I)
    for line in lines:
        m = re.match(r"(?i)^(written|prepared|authored)\s+by[:\s]+(.+)", line)
        e = re.match(r"(?i)^edited\s+by[:\s]+(.+)", line)
        t = re.match(r"(?i)^(topic|tema)\s*:\s*(.+)", line)
        c = re.match(r"(?i)^((?:head\s+|co-?\s*)?chair(?:person)?)\s*:\s*(.+)", line)
        if m:
            meta["authors"] = m.group(2).strip()
        elif e:
            meta["editor"] = e.group(1).strip()
        elif t:
            meta["topic"] = t.group(2).strip().strip("“”\"")
        elif c:
            chairs.append(c.group(2).strip())
        elif not re.fullmatch(r"\d+", line) and not skip.match(line):
            rest.append(line.strip("“”\""))
    if chairs and not meta["authors"]:
        meta["authors"] = " & ".join(chairs)
    if rest:
        meta["committee"] = rest[0]
    if len(rest) > 1:
        meta["longname"] = rest[1]
    if len(rest) > 2 and not meta["topic"]:
        meta["topic"] = max(rest[2:], key=len)
    return meta


def write_main(out_dir: Path, meta: dict, inputs: list[str], category: str, cover: str | None,
               opts: dict):
    def m(key, fallback):
        value = meta.get(key)
        if value is None or value == "":
            value = fallback
        return value if meta.get("_latex_" + key) else escape_text(value)

    lines = [
        r"\documentclass{ieumun-guide}",
        "",
        "% Generated by scripts/docx2guide.py -- edit SG_config/<slug>.json instead.",
    ]
    if opts.get("language") and opts["language"] != "english":
        lines.append(r"\guidelanguage{%s}" % opts["language"])
    lines += [
        r"\guidecommittee{%s}" % m("committee", "COMMITTEE"),
        r"\guidelongname{%s}" % m("longname", ""),
        r"\guidetopic{%s}" % m("topic", ""),
        r"\guideauthors{%s}" % m("authors", ""),
        r"\guideeditor{%s}" % m("editor", ""),
    ]
    if meta.get("authors_label"):
        lines.append(r"\guideauthorslabel{%s}" % escape_text(meta["authors_label"]))
    if meta.get("editor_label"):
        lines.append(r"\guideeditorlabel{%s}" % escape_text(meta["editor_label"]))
    lines.append(r"\guidecover{%s}" % (cover or "assets/cover.jpg"))
    lines.append(r"\guidecategory{%s}" % category)
    lines += opts.get("preamble", [])
    lines += [
        "",
        r"\begin{document}",
        "",
        r"\makecover",
        r"\tableofcontents",
        "",
        *[r"\input{content/%s}" % name for name in inputs],
        "",
        r"\end{document}",
        "",
    ]
    (out_dir / "main.tex").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def convert(docx: Path, out: Path, cfg: dict, category: str, cover: Path | None, force: bool) -> dict:
    content = out / "content"
    if content.exists() and any(content.iterdir()) and not force:
        sys.exit(f"{content} already has files; pass --force to overwrite.")
    content.mkdir(parents=True, exist_ok=True)
    for old in content.glob("*.tex"):
        old.unlink()
    (out / "assets").mkdir(exist_ok=True)

    conv_cfg = cfg.get("convert", {})
    fixes = [tuple(x) for x in conv_cfg.get("text_fixes", [])]
    conv = Converter(Package(docx), out, fixes)
    blocks = read_blocks(conv)

    for rule in conv_cfg.get("drop", []):
        rx_from = re.compile(rule["from"])
        rx_to = re.compile(rule["until"]) if rule.get("until") else None
        kept, dropping = [], False
        for b in blocks:
            text = b.clean
            if not dropping and text and rx_from.search(text):
                if rx_to is None:
                    continue  # drop just this block
                dropping = True
            elif dropping and text and rx_to.search(text):
                dropping = False
            if not dropping:
                kept.append(b)
        blocks = kept

    body_size = body_font_size(blocks)
    pdf_mode = conv_cfg.get("pdf_mode", detect_pdf_mode(conv, blocks))
    notes: dict = {}
    if pdf_mode:
        blocks, notes = rebuild_page_notes(blocks, body_size, conv)
        blocks = merge_split_paragraphs(blocks, body_size)
    else:
        blocks = [b for b in blocks if b.kind not in {"page", "sep"}]

    for rule in conv_cfg.get("headings", []):
        rx = re.compile(rule["match"])
        for b in blocks:
            if b.list_kind and not rule.get("lists", False):
                continue  # typed tables of contents are lists
            if b.kind in {"para", "heading"} and rx.search(b.clean):
                if rule.get("level") is None:
                    b.kind = "para"
                    b.list_kind = None
                else:
                    if b.kind != "heading":
                        b.kind, b.source = "heading", "config"
                    b.list_kind = None
                    if rule["level"] == "top":
                        b.force_top = True
                    else:
                        b.level = float(rule["level"])

    find_hard_headings(blocks, body_size)
    blocks = dedupe_headings(blocks)
    top = choose_top_level(blocks, conv_cfg.get("top_level"))
    assign_top_ranks(blocks, top)
    keep = acronyms_from(blocks)
    front, sections = split_sections(blocks)

    meta = guess_metadata(front)
    guessed = dict(meta)
    for key, value in cfg.get("meta", {}).items():
        meta[key] = value

    resolver = NoteResolver(notes, pdf_mode)
    opts = {"pdf_mode": pdf_mode, "body_size": body_size, "auto_lead": conv_cfg.get("auto_lead", True),
            "letter_fallback": conv_cfg.get("letter_fallback", "The Chairs")}
    inputs, skipped, report_sections = [], [], []
    for sec in sections:
        kind = section_kind(sec)
        if kind in {"contents", "drop"}:
            skipped.append(sec.plain)
            continue
        if not any(b.kind in {"para", "table", "image", "heading"} for b in sec.blocks):
            conv.warnings.append(f"section '{sec.plain}' is empty and was left out.")
            skipped.append(sec.plain)
            continue
        name = f"{len(inputs):02d}-{slugify(norm(sec.heading.plain))}"
        tex = resolver(section_tex(sec, kind, keep, meta, opts))
        (content / f"{name}.tex").write_text(tex, encoding="utf-8")
        inputs.append(name)
        report_sections.append({"file": name, "title": sec.plain, "kind": kind})

    leftover = sum(len(q) for q in notes.values())
    if leftover:
        conv.warnings.append(f"{leftover} rebuilt notes were not placed (front matter?).")

    # Every source note must be somewhere in the generated text. Notes that only
    # sat in the cover page or in a skipped duplicate are reported by name.
    written = "".join(p.read_text(encoding="utf-8") for p in sorted(content.glob("*.tex")))
    written_key = text_key(written)
    local = re.findall(r"file:///[^}\s]+", written)
    if local:
        conv.warnings.append(f"{len(local)} sources link to a file on the author's computer, e.g. {local[0][:70]}")
    missing_notes = [t for t in conv.footnote_log if text_key(escape_text(t))[:70] not in written_key]
    for t in missing_notes[:10]:
        conv.warnings.append("source note not in the guide: " + t[:120])
    if len(missing_notes) > 10:
        conv.warnings.append(f"... and {len(missing_notes) - 10} more source notes not in the guide")
    if resolver.unresolved:
        conv.warnings.append(f"{len(resolver.unresolved)} superscript numbers have no matching note: "
                             + ", ".join(resolver.unresolved[:20]))

    if front:
        front_lines = ["% Text found before the first section (usually the Word cover page).",
                       "% It is not \\input anywhere; metadata in main.tex comes from it or from the config.", ""]
        front_lines += ["% " + clean(b.plain) for b in front if b.kind in {"para", "heading"} and b.clean]
        (out / "front-matter.txt").write_text("\n".join(front_lines) + "\n", encoding="utf-8")

    cover_rel = None
    if cover:
        ext = cover.suffix.lower()
        dest = out / "assets" / f"cover{ext if ext in LATEX_READY_IMAGES else '.png'}"
        if ext in LATEX_READY_IMAGES:
            shutil.copyfile(cover, dest)
        else:
            subprocess.run(["sips", "-s", "format", "png", str(cover), "--out", str(dest)], capture_output=True)
        cover_rel = f"assets/{dest.name}"
    write_main(out, meta, inputs, category, cover_rel,
               {"language": cfg.get("language", "english"), "preamble": cfg.get("preamble", [])})
    shutil.copyfile(TEMPLATE_DIR / "latexmkrc", out / "latexmkrc")

    log = ["# Footnotes extracted from the Word document", ""]
    log += [f"{i}. {text}" for i, text in enumerate(conv.footnote_log, 1)]
    (out / "sources-extracted.md").write_text("\n".join(log) + "\n", encoding="utf-8")

    report = {
        "sections": report_sections,
        "skipped": skipped,
        "images": len(conv.images),
        "word_footnotes": conv.word_notes,
        "rebuilt_footnotes": len(conv.footnote_log) - conv.word_notes,
        "source_notes": len(conv.footnote_log),
        "notes_outside_guide": sum(len(footnote_bodies(b.text)) for b in front)
        + sum(len(footnote_bodies(b.text)) for s in sections if section_kind(s) in {"contents", "drop"}
              for b in s.blocks),
        "source_notes_missing": missing_notes,
        "footnotes_written": len(footnote_bodies(written)),
        "expected_footnotes": len(footnote_bodies(written)),
        "pdf_mode": pdf_mode,
        "guessed_meta": guessed,
        "warnings": conv.warnings,
    }
    (out / "convert-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                             encoding="utf-8")
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("docx", type=Path)
    ap.add_argument("out", type=Path, help="guide folder to create, e.g. guides/unsc")
    ap.add_argument("--config", type=Path, help="per-guide JSON config (metadata and conversion rules)")
    ap.add_argument("--committee", help="override the committee short name")
    ap.add_argument("--category", default="black", choices=["black", "red", "blue"])
    ap.add_argument("--cover", type=Path, help="full-page A4 cover artwork (jpg/png)")
    ap.add_argument("--force", action="store_true", help="overwrite existing content/ files")
    args = ap.parse_args(argv)

    cfg = json.loads(args.config.read_text(encoding="utf-8")) if args.config else {}
    if args.committee:
        cfg.setdefault("meta", {})["committee"] = args.committee
    report = convert(args.docx, args.out, cfg, cfg.get("category", args.category), args.cover, args.force)

    print(f"Sections:   {len(report['sections'])} -> {args.out / 'content'}")
    if report["skipped"]:
        print(f"Skipped:    {', '.join(report['skipped'])}")
    print(f"Images:     {report['images']}")
    print(f"Footnotes:  {report['expected_footnotes']} ({report['word_footnotes']} Word notes, "
          f"{report['rebuilt_footnotes']} rebuilt from page feet)")
    for w in report["warnings"]:
        print("WARNING:", w)


if __name__ == "__main__":
    main()
