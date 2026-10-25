#!/usr/bin/env python3
"""
FolioPress - Portfolio Builder
Drag files from your hard drive, arrange on a canvas, export rich HTML.

Dependencies: PyQt5
Install: pip install PyQt5
"""

import sys, os, re, json, math, shutil, uuid, random, base64, hashlib, html, threading
import urllib.request, urllib.parse
from html.parser import HTMLParser
from pathlib import Path

try:
    import pymupdf as fitz          # PyMuPDF — PDF metadata, text, cover image
except ImportError:
    try:
        import fitz                 # PyMuPDF < 1.24.3
    except ImportError:
        fitz = None
pypdf = None                        # fallback (metadata + text, no cover); imported on demand


def _load_pypdf():
    global pypdf
    if pypdf is None:
        try:
            import pypdf as _pypdf
            pypdf = _pypdf
        except ImportError:
            pass
    return pypdf


np = None                           # numpy — only the drawing fill tool needs it; imported on demand


def _load_numpy():
    global np
    if np is None:
        try:
            import numpy as _np
            np = _np
        except ImportError:
            pass
    return np


from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QGraphicsScene, QGraphicsView, QGraphicsItem,
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton, QComboBox, QSpinBox,
    QDoubleSpinBox, QFontComboBox,
    QTreeView, QFileSystemModel, QFileDialog, QDialog, QDialogButtonBox,
    QTableWidget, QTableWidgetItem, QFrame, QMessageBox, QAction,
    QToolBar, QSplitter, QCheckBox, QStatusBar, QTabWidget, QScrollArea,
    QGroupBox, QSlider, QColorDialog, QMenu, QSizePolicy, QAbstractItemView,
    QHeaderView, QPlainTextEdit, QInputDialog, QToolButton, QButtonGroup, QGridLayout
)
from PyQt5.QtCore import (
    Qt, QPointF, QRectF, QSizeF, pyqtSignal, QMimeData, QUrl,
    QFileInfo, QDir, QModelIndex, QTimer
)
from PyQt5.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QFontMetrics, QFontMetricsF, QPixmap,
    QDrag, QCursor, QPainterPath, QLinearGradient, QRadialGradient,
    QTransform, QPalette, QIcon, QTextLayout, QTextOption, QImage, QImageReader,
    qRgb, QKeySequence, QDesktopServices
)
from PyQt5.QtCore import QBuffer, QByteArray, QIODevice, QThread, QObject

# ─── Constants ─────────────────────────────────────────────────────────────────

GRID = 20
CANVAS_W = 3000
CANVAS_H = 4000
IMAGE_EXTS  = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif", ".svg"}
DOC_EXTS    = {".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".odt"}
ALL_EXTS    = IMAGE_EXTS | DOC_EXTS

APP_VERSION = "0.9.0"
APP_YEAR    = "2026"

DEV_NAME    = "Mitali Aayat Mahnoor Sharma"
APP_ID      = "com.zeffiroh.foliopress"
# frozen builds (PyInstaller) unpack bundled data next to the executable's internals
BUNDLE_DIR   = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
BRANDING_DIR = BUNDLE_DIR / "branding"


def _load_links() -> dict:
    """Developer & support links from links.json — the one place to edit them; blank = hidden."""
    try:
        data = json.loads((BUNDLE_DIR / "links.json").read_text("utf-8"))
    except (OSError, ValueError):
        data = {}
    return {k: str(data.get(k) or "").strip() for k in ("email", "github", "website", "support")}


_LINKS      = _load_links()
DEV_EMAIL   = _LINKS["email"]
DEV_GITHUB  = _LINKS["github"]
DEV_WEBSITE = _LINKS["website"]
SUPPORT_URL = _LINKS["support"]          # Razorpay Payment Page


def app_icon() -> QIcon:
    """The FolioPress icon at every size we ship (empty if branding/ is missing)."""
    icon = QIcon()
    for png in sorted((BRANDING_DIR / "icons").glob("*.png")):
        icon.addFile(str(png))
    return icon

NEWSPAPER_FONTS = [
    "Georgia",
    "Times New Roman",
    "Playfair Display",
    "Garamond",
    "Baskerville Old Face",
    "Bodoni MT",
    "Palatino Linotype",
    "Book Antiqua",
    "Impact",
    "Arial",
    "Helvetica Neue",
    "Trebuchet MS",
    "Verdana",
    "Courier New",
    "Consolas",
]

BOX_STYLES = {
    "broadsheet": {
        "label": "Broadsheet Classic",
        "bg": "#fdfdf8", "ink": "#111111", "accent": "#8b0000",
        "muted": "#666666", "rule": "#bdb8ad",
        "top_bar": 5, "double_border": False, "left_bar": 0, "banner_head": False, "corner_ticks": False,
    },
    "double_rule": {
        "label": "Double-Rule Frame",
        "bg": "#faf6eb", "ink": "#141414", "accent": "#7a1818",
        "muted": "#686256", "rule": "#9e9585",
        "top_bar": 0, "double_border": True, "left_bar": 0, "banner_head": False, "corner_ticks": False,
    },
    "tabloid_splash": {
        "label": "Tabloid Splash",
        "bg": "#ffffff", "ink": "#050505", "accent": "#cc0000",
        "muted": "#555555", "rule": "#222222",
        "top_bar": 8, "double_border": False, "left_bar": 0, "banner_head": True, "corner_ticks": False,
    },
    "boxed_editorial": {
        "label": "Boxed Editorial",
        "bg": "#f3ede0", "ink": "#1a1712", "accent": "#5c3317",
        "muted": "#6b6152", "rule": "#a39681",
        "top_bar": 4, "double_border": False, "left_bar": 0, "banner_head": False, "corner_ticks": True,
    },
    "sidebar_callout": {
        "label": "Sidebar Callout",
        "bg": "#f5f3ec", "ink": "#181818", "accent": "#1565c0",
        "muted": "#666666", "rule": "#c5c0b5",
        "top_bar": 0, "double_border": False, "left_bar": 6, "banner_head": False, "corner_ticks": False,
    },
    "minimal_column": {
        "label": "Minimal Column",
        "bg": "#ffffff", "ink": "#222222", "accent": "#444444",
        "muted": "#777777", "rule": "#dddddd",
        "top_bar": 1, "double_border": False, "left_bar": 0, "banner_head": False, "corner_ticks": False,
    },
    "dark_dispatch": {
        "label": "Dark Dispatch",
        "bg": "#0d1117", "ink": "#e6edf3", "accent": "#58a6ff",
        "muted": "#8b949e", "rule": "#30363d",
        "top_bar": 0, "double_border": False, "left_bar": 5, "banner_head": False, "corner_ticks": False,
    },
}

# ─── Data Model ────────────────────────────────────────────────────────────────

class PortfolioItem:
    """One card on the canvas."""
    KINDS = ("image", "article", "strapline", "headline", "abstract", "text", "url", "linktree",
             "quote", "donate")

    def __init__(self, kind="image"):
        self.id              = uuid.uuid4().hex[:10]
        self.kind            = kind
        self.x               = 60.0
        self.y               = 60.0
        self.w               = 320.0
        self.h               = 240.0
        self.title           = ""
        self.strapline       = ""
        self.abstract        = ""
        self.notes           = ""
        self.url             = ""
        self.file_path       = ""
        self.cover_path      = ""
        self.embedded_image  = ""           # base64 PNG (drawn / cropped / PDF cover); wins over paths
        self.links           = []           # attached links: [{label, url}]
        self.mailto          = ""           # per-card contact (blank → portfolio email)
        self.pdf_access      = ""           # per-document access (blank → portfolio setting)
        self.tags            = []
        # Typography & formatting
        self.font_family     = "Georgia"
        self.font_size       = 10
        self.title_font_size = 16
        self.bold            = False
        self.italic          = False
        self.underline       = False
        self.align           = "left"       # left | center | right | justify
        self.columns         = 2 if kind in ("text", "article") else 1
        self.drop_cap        = (kind == "article")
        self.box_style       = "dark_dispatch" if kind == "url" else "broadsheet"
        self.text_color      = ""
        self.bg_color        = ""
        # Rotation & grouping
        self.rotation        = 0.0          # degrees
        self.group_id        = ""
        self.group_locked    = True

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, d):
        item = cls(d.get("kind", "image"))
        item.__dict__.update(d)
        return item


class Project:
    def __init__(self):
        self.title   = "My Portfolio"
        self.author  = ""
        self.email   = ""
        self.tagline = ""
        self.intro   = ""
        self.items   = []       # list[PortfolioItem]
        self.links   = []       # list[{label, url, desc, preview, icon, page_title, page_desc, image, embed}]
        self.theme   = "broadsheet"
        self.path    = None
        # Exported documents: "preview" (pages as images, full file not published),
        # "password" (+ AES-256 encrypted download) or "open" (+ plain download)
        self.pdf_access    = "preview"
        self.request_email = ""   # mailto for "Request the full document" (blank → email)
        self.file_password = ""   # kept in memory only, never saved
        self.donate_url    = ""   # Ko-fi / PayPal / Buy Me a Coffee … (blank → no button)
        self.donate_label  = "Donate"
        self.texture       = "none"   # page background: see TEXTURES
        self.texture_path  = ""       # image for texture == "custom"

    SAVED_FIELDS = ("title", "author", "email", "tagline", "intro", "links", "theme",
                    "pdf_access", "request_email", "donate_url", "donate_label",
                    "texture", "texture_path")

    def to_data(self):
        data = {k: getattr(self, k) for k in self.SAVED_FIELDS}
        data["items"] = [i.to_dict() for i in self.items]
        return data

    def snapshot(self) -> str:
        """Fingerprint of everything that gets saved — used to skip the save prompt."""
        return hashlib.sha1(json.dumps(self.to_data(), sort_keys=True, default=str).encode("utf-8")).hexdigest()

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_data(), f, indent=2)
        self.path = path

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        p = cls()
        for k in cls.SAVED_FIELDS:
            setattr(p, k, data.get(k, getattr(p, k)))
        p.items = [PortfolioItem.from_dict(d) for d in data.get("items", [])]
        p.path  = path
        return p


# ─── Image & Document Import Helpers ───────────────────────────────────────────

def image_to_b64(img: QImage) -> str:
    """Encode a QImage as base64 PNG for storing inside the project."""
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    return base64.b64encode(bytes(ba)).decode("ascii")


def b64_to_image(s: str) -> QImage:
    img = QImage()
    if s:
        try:
            img.loadFromData(base64.b64decode(s))
        except Exception:
            pass
    return img


def parse_links_text(text: str):
    """'Label | url' (or a bare url) per line → [{label, url}]."""
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        label, _, url = line.rpartition("|") if "|" in line else ("", "", line)
        url = url.strip()
        if url and not re.match(r"[a-z][a-z0-9+.-]*:", url, re.I) and "." in url:
            url = "https://" + url
        if url:
            out.append({"label": label.strip(), "url": url})
    return out


def format_links_text(links) -> str:
    return "\n".join((f'{l["label"]} | {l["url"]}' if l.get("label") else l["url"]) for l in links or [])


def read_image(path: str, max_side: int = 1600) -> QImage:
    """Decode an image file already downscaled to `max_side` (much faster than full-size
    camera photos); export still copies the original file."""
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    size = reader.size()
    if max_side and size.isValid() and max(size.width(), size.height()) > max_side:
        reader.setScaledSize(size.scaled(max_side, max_side, Qt.KeepAspectRatio))
    return reader.read()


def item_image(item: PortfolioItem, max_side: int = 1600) -> QImage:
    """The picture shown on a card: embedded image > cover path > image file."""
    if getattr(item, "embedded_image", ""):
        img = b64_to_image(item.embedded_image)
        if not img.isNull():
            return img
    if item.cover_path and os.path.isfile(item.cover_path):
        img = read_image(item.cover_path, max_side)
        if not img.isNull():
            return img
    if item.kind == "image" and item.file_path and os.path.isfile(item.file_path):
        return read_image(item.file_path, max_side)
    return QImage()


# Page background textures (tile generated on the theme's background colour)
TEXTURES = {"none": "None", "paper": "Paper", "newsprint": "Newsprint", "linen": "Linen",
            "canvas": "Canvas", "grid": "Graph Paper", "dots": "Dots", "custom": "Image…"}


def make_texture(kind: str, base: str, custom_path: str = "") -> QImage:
    """A seamless background tile; null image for "none" (or a missing custom file)."""
    if kind == "custom":
        return read_image(custom_path, 1200) if custom_path and os.path.isfile(custom_path) else QImage()
    if kind not in TEXTURES or kind == "none":
        return QImage()
    size = {"grid": 96, "dots": 24}.get(kind, 192)
    img = QImage(size, size, QImage.Format_RGB32)
    base_c = QColor(base)
    img.fill(base_c)
    dark = 0.5 if base_c.lightness() > 128 else -0.5   # ink darker than light paper, lighter than dark
    ink = QColor(0, 0, 0) if dark > 0 else QColor(255, 255, 255)
    rng = random.Random(7)
    if kind in ("paper", "newsprint", "canvas"):
        amp = {"paper": 7, "newsprint": 11, "canvas": 6}[kind]
        r0, g0, b0 = base_c.red(), base_c.green(), base_c.blue()
        for y in range(size):
            for x in range(size):
                d = rng.randint(-amp, amp)
                img.setPixel(x, y, qRgb(max(0, min(255, r0 + d)), max(0, min(255, g0 + d)), max(0, min(255, b0 + d))))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)

    def pen(alpha, width=1.0):
        c = QColor(ink); c.setAlpha(alpha)
        p.setPen(QPen(c, width))

    if kind == "paper":                                  # faint fibres
        for _ in range(28):
            x, y = rng.uniform(0, size), rng.uniform(0, size)
            a = rng.uniform(0, math.pi)
            ln = rng.uniform(6, 22)
            pen(rng.randint(6, 16), 0.6)
            for ox in (-size, 0, size):                  # draw wrapped copies so the tile is seamless
                for oy in (-size, 0, size):
                    p.drawLine(QPointF(x + ox, y + oy), QPointF(x + ox + ln * math.cos(a), y + oy + ln * math.sin(a)))
    elif kind == "newsprint":                            # halftone screen
        p.setPen(Qt.NoPen)
        c = QColor(ink); c.setAlpha(16); p.setBrush(c)
        for y in range(0, size, 6):
            for x in range(0, size, 6):
                p.drawEllipse(QPointF(x + (3 if (y // 6) % 2 else 0), y), 1.1, 1.1)
    elif kind in ("linen", "canvas"):                    # woven threads
        step = 3 if kind == "linen" else 4
        for i in range(0, size, step):
            pen(rng.randint(8, 26), 1.0)
            p.drawLine(0, i, size, i)
            pen(rng.randint(8, 26), 1.0)
            p.drawLine(i, 0, i, size)
    elif kind == "grid":
        for i in range(0, size, 12):
            pen(40 if i % 48 == 0 else 18, 1.0)
            p.drawLine(QPointF(i + 0.5, 0), QPointF(i + 0.5, size))
            p.drawLine(QPointF(0, i + 0.5), QPointF(size, i + 0.5))
    elif kind == "dots":
        p.setPen(Qt.NoPen)
        c = QColor(ink); c.setAlpha(45); p.setBrush(c)
        p.drawEllipse(QPointF(size / 2.0, size / 2.0), 1.3, 1.3)
    p.end()
    return img


_RTF_SKIP_DESTS = {
    "fonttbl", "colortbl", "stylesheet", "info", "pict", "object", "header", "footer",
    "headerl", "headerr", "headerf", "footerl", "footerr", "footerf", "fldinst",
    "generator", "listtable", "listoverridetable", "rsidtbl", "themedata",
    "colorschememapping", "datastore", "latentstyles", "xmlnstbl", "filetbl",
}


def rtf_to_text(rtf: str) -> str:
    """Minimal RTF → plain text: keeps paragraphs, decodes escapes, drops control groups."""
    out = []
    stack = []
    skip = False
    uc = 1
    pending = 0           # fallback chars to swallow after \uN
    i, n = 0, len(rtf)
    word_re = re.compile(r"([a-zA-Z]+)(-?\d+)? ?")

    def emit(s):
        nonlocal pending
        if pending > 0:
            pending -= 1
            return
        if not skip:
            out.append(s)

    while i < n:
        c = rtf[i]
        if c == "{":
            stack.append((skip, uc))
            i += 1
        elif c == "}":
            skip, uc = stack.pop() if stack else (False, 1)
            i += 1
        elif c == "\\":
            i += 1
            if i >= n:
                break
            c2 = rtf[i]
            if c2 in "\\{}":
                emit(c2); i += 1
            elif c2 == "'":
                try:
                    emit(bytes([int(rtf[i + 1:i + 3], 16)]).decode("cp1252", errors="replace"))
                except ValueError:
                    pass
                i += 3
            elif c2 == "*":
                skip = True; i += 1
            elif c2 in "\r\n":
                emit("\n"); i += 1
            elif not c2.isalpha():
                emit({"~": " ", "_": "-", "-": ""}.get(c2, "")); i += 1
            else:
                m = word_re.match(rtf, i)
                word, num = m.group(1), m.group(2)
                i = m.end()
                if word in _RTF_SKIP_DESTS:
                    skip = True
                elif skip:
                    continue
                elif word in ("par", "line", "sect", "page"):
                    out.append("\n")
                elif word == "tab":
                    out.append("\t")
                elif word in ("emdash", "endash"):
                    out.append("—" if word == "emdash" else "–")
                elif word in ("lquote", "rquote"):
                    out.append("’" if word == "rquote" else "‘")
                elif word in ("ldblquote", "rdblquote"):
                    out.append("”" if word == "rdblquote" else "“")
                elif word == "bullet":
                    out.append("•")
                elif word == "uc" and num:
                    uc = int(num)
                elif word == "u" and num:
                    code = int(num)
                    out.append(chr(code + 65536 if code < 0 else code))
                    pending = uc
        elif c in "\r\n":
            i += 1
        else:
            emit(c); i += 1
    return "".join(out)


def reflow_paragraphs(text: str):
    """Split text into paragraphs (blank-line separated), joining hard-wrapped lines."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\x0c", "\n\n")
    paras = []
    for block in re.split(r"\n\s*\n", text):
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue
        joined = ""
        for ln in lines:
            if joined.endswith("-") and not joined.endswith(" -"):
                joined = joined[:-1] + ln          # de-hyphenate PDF line wraps
            else:
                joined = (joined + " " + ln) if joined else ln
        paras.append(re.sub(r"[ \t]+", " ", joined))
    return paras


def _pdf_cover_image(doc) -> QImage:
    """Largest real picture on the first pages (no page renders). Sizes come from the
    image list, so only the chosen picture is decoded."""
    best_xref, best_area = 0, 0
    for page in list(doc)[:2]:
        for info in page.get_images(full=True):
            xref, w, h = info[0], info[2], info[3]
            if min(w, h) >= 160 and w * h > best_area:
                best_xref, best_area = xref, w * h
    if best_xref:
        try:
            raw = doc.extract_image(best_xref).get("image")
        except Exception:
            raw = None
        img = QImage()
        if raw and img.loadFromData(raw) and not img.isNull():
            return img
    return QImage()


def _pdf_text(doc, max_pages=None) -> str:
    # text blocks ≈ paragraphs; type 0 = text (1 = image)
    pages = list(doc) if max_pages is None else list(doc)[:max_pages]
    return "\n\n".join(b[4] for page in pages
                       for b in page.get_text("blocks", sort=True) if b[6] == 0)


def _pdf_largest_type(doc) -> str:
    """Text set in the largest font on page 1 — usually the real title."""
    if not len(doc):
        return ""
    spans = []
    page = doc[0]
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            txt = "".join(s.get("text", "") for s in line.get("spans", [])).strip()
            if txt and line.get("spans"):
                spans.append((max(s.get("size", 0) for s in line["spans"]), line["bbox"][1], txt))
    if not spans:
        return ""
    top = max(s[0] for s in spans)
    lines = [t for size, y, t in sorted(spans, key=lambda s: s[1]) if size >= top - 0.6]
    title = re.sub(r"\s+", " ", " ".join(lines)).strip()
    return title if 3 <= len(title) <= 200 else ""


def extract_pdf(path: str, max_pages: int = 3) -> dict:
    """Return {title, big_title, author, subject, keywords, text, cover(QImage)} for a PDF.
    Only the first `max_pages` pages of text are read — enough for headline + abstract."""
    info = {"title": "", "big_title": "", "author": "", "subject": "", "keywords": "",
            "text": "", "cover": QImage()}
    if fitz is not None:
        with fitz.open(path) as doc:
            meta = doc.metadata or {}
            for k in ("title", "author", "subject", "keywords"):
                info[k] = (meta.get(k) or "").strip()
            info["text"] = _pdf_text(doc, max_pages)
            info["big_title"] = _pdf_largest_type(doc)
            info["cover"] = _pdf_cover_image(doc)
    elif _load_pypdf() is not None:
        reader = pypdf.PdfReader(path)
        meta = reader.metadata or {}
        info["title"]    = str(meta.get("/Title") or "").strip()
        info["author"]   = str(meta.get("/Author") or "").strip()
        info["subject"]  = str(meta.get("/Subject") or "").strip()
        info["keywords"] = str(meta.get("/Keywords") or "").strip()
        info["text"] = "\n\n".join((p.extract_text() or "") for p in reader.pages[:max_pages])
    return info


_DOC_TEXT_CACHE = {}


def document_paragraphs(path: str):
    """Full text of a PDF / RTF / TXT / MD file as paragraphs (cached per file version)."""
    try:
        key = (path, os.path.getmtime(path))
    except OSError:
        return []
    if key in _DOC_TEXT_CACHE:
        return _DOC_TEXT_CACHE[key]
    ext = Path(path).suffix.lower()
    text = ""
    if ext == ".pdf":
        if fitz is not None:
            with fitz.open(path) as doc:
                text = _pdf_text(doc)
        elif _load_pypdf() is not None:
            text = "\n\n".join((p.extract_text() or "") for p in pypdf.PdfReader(path).pages)
    elif ext in (".txt", ".md", ".rtf"):
        raw = Path(path).read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("cp1252", errors="replace")
        if ext == ".rtf":
            # every \par is a real paragraph in RTF (no hard-wrapped lines to join)
            text = re.sub(r"\n", "\n\n", rtf_to_text(text))
    paras = reflow_paragraphs(text)
    _DOC_TEXT_CACHE.clear()
    _DOC_TEXT_CACHE[key] = paras
    return paras


def _trim_sentences(s: str, limit: int = 600) -> str:
    s = s.strip()
    if len(s) <= limit:
        return s
    cut = s[:limit]
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    return (cut[:end + 1] if end > limit * 0.4 else cut.rsplit(" ", 1)[0] + "…").strip()


def find_abstract(paras, skip_text=""):
    """An 'Abstract' / 'Summary' paragraph if there is one, else the first real paragraph."""
    for i, p in enumerate(paras[:80]):
        m = re.match(r"^\s*(abstract|summary|executive summary)\b[\s.:—–-]*", p, re.I)
        if m:
            rest = p[m.end():].strip()
            if len(rest) < 40 and i + 1 < len(paras):
                rest = paras[i + 1]
            return _trim_sentences(rest)
    skip = skip_text.strip().lower()
    for p in paras[:30]:
        if len(p) >= 80 and p.strip().lower() != skip:
            return _trim_sentences(p)
    return ""


_BAD_META_TITLE = re.compile(r"(untitled.*|microsoft (word|powerpoint).*|.*\.(docx?|pdf|indd|tex)|document\d*)", re.I)


def fill_article_from_document(data: PortfolioItem, path: str):
    """Fetch headline, kicker, abstract and cover from a file. The body is left empty —
    use Extract Text to pick passages from the document."""
    ext = Path(path).suffix.lower()
    stem_title = Path(path).stem.replace("_", " ").replace("-", " ").strip().title()
    data.file_path = path
    data.title, data.strapline, data.abstract, data.notes = stem_title, "", "", ""
    data.embedded_image = ""

    if ext == ".pdf":
        info = extract_pdf(path)
        paras = reflow_paragraphs(info["text"])
        meta_title = info["title"]
        if meta_title and not _BAD_META_TITLE.fullmatch(meta_title):
            data.title = meta_title
        elif info["big_title"]:
            data.title = info["big_title"]
        elif paras and len(paras[0]) < 110:
            data.title = paras[0]
        data.strapline = (info["keywords"].split(",")[0].strip() if info["keywords"] else "") or ("BY " + info["author"] if info["author"] else "")
        data.abstract = find_abstract(paras, data.title) or _trim_sentences(info["subject"])
        if not info["cover"].isNull():
            cover = info["cover"]
            if max(cover.width(), cover.height()) > 1400:
                cover = cover.scaled(1400, 1400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            data.embedded_image = image_to_b64(cover)
        return

    if ext in (".txt", ".md", ".rtf"):
        paras = document_paragraphs(path)
        if paras:
            first = paras[0].lstrip("# ").strip()
            if len(first) < 90 and len(paras) > 1:
                data.title = first
        data.abstract = find_abstract(paras, data.title)


# ─── Newspaper Box & Typography Helpers ────────────────────────────────────────

def get_style_palette(data: PortfolioItem, default_style="broadsheet"):
    st = BOX_STYLES.get(getattr(data, "box_style", "") or default_style, BOX_STYLES[default_style]).copy()
    if getattr(data, "bg_color", ""):
        st["bg"] = data.bg_color
    if getattr(data, "text_color", ""):
        st["ink"] = data.text_color
    return st


def paint_newspaper_frame(painter: QPainter, r: QRectF, data: PortfolioItem, default_style="broadsheet"):
    """Draw specialized newspaper-themed card background, rules, borders, and ornaments."""
    st = get_style_palette(data, default_style)
    w, h = r.width(), r.height()
    bg     = QColor(st["bg"])
    ink    = QColor(st["ink"])
    accent = QColor(st["accent"])
    rule   = QColor(st["rule"])

    painter.fillRect(r, bg)

    if st.get("double_border"):
        painter.setPen(QPen(ink, 2.2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(QRectF(1.5, 1.5, w - 3.0, h - 3.0))
        painter.setPen(QPen(rule, 0.9))
        painter.drawRect(QRectF(5.5, 5.5, w - 11.0, h - 11.0))
    else:
        border_w = 2.0 if data.box_style == "tabloid_splash" else 1.0
        painter.setPen(QPen(rule, border_w))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0))

    top_bar = st.get("top_bar", 0)
    if top_bar > 0:
        bar_col = accent if data.box_style == "tabloid_splash" else ink
        painter.fillRect(QRectF(0, 0, w, top_bar), bar_col)
        if data.box_style == "boxed_editorial":
            painter.fillRect(QRectF(0, h - top_bar, w, top_bar), bar_col)

    left_bar = st.get("left_bar", 0)
    if left_bar > 0:
        painter.fillRect(QRectF(0, 0, left_bar, h), accent)

    if st.get("corner_ticks"):
        tk = 10.0
        painter.setPen(QPen(accent, 1.5))
        for cx, cy, sx, sy in [(6, 8, 1, 1), (w - 6, 8, -1, 1), (6, h - 8, 1, -1), (w - 6, h - 8, -1, -1)]:
            painter.drawLine(QPointF(cx, cy), QPointF(cx + sx * tk, cy))
            painter.drawLine(QPointF(cx, cy), QPointF(cx, cy + sy * tk))

    return st


def qt_align_flag(align_str: str):
    return {
        "left":    Qt.AlignLeft,
        "center":  Qt.AlignHCenter,
        "right":   Qt.AlignRight,
        "justify": Qt.AlignJustify,
    }.get((align_str or "left").lower(), Qt.AlignLeft)


def make_card_font(data: PortfolioItem, pt_size: float, bold_override=None, italic_override=None, underline_override=None) -> QFont:
    fam = getattr(data, "font_family", "Georgia") or "Georgia"
    f = QFont(fam, max(5, int(round(pt_size))))
    b = data.bold if bold_override is None else bold_override
    it = data.italic if italic_override is None else italic_override
    ul = data.underline if underline_override is None else underline_override
    f.setBold(bool(b))
    f.setItalic(bool(it))
    f.setUnderline(bool(ul))
    return f


_LAYOUT_CACHE = {}


def _layout_paragraphs_into_lines(text: str, font: QFont, col_w: float, drop_cap: bool = False,
                                  max_h: float = None):
    """
    Break paragraphs into wrapped lines (text_str, x_offset, width_avail, is_para_end)
    so we can verify whether the text fits inside `columns` of height `col_h` without clipping.
    Stops once the stacked height passes `max_h` (nothing beyond it is ever drawn) and
    returns (lines, line_h, drop_info, overflowed). Results are cached.
    """
    key = (text, font.key(), round(col_w, 1), drop_cap, None if max_h is None else round(max_h, 1))
    hit = _LAYOUT_CACHE.get(key)
    if hit is not None:
        return hit
    fm = QFontMetricsF(font)
    line_h = max(10.0, fm.lineSpacing() * 1.08)
    paras = [p.strip() for p in (text or "").split("\n") if p.strip()]
    if not paras:
        return [], line_h, None, False

    drop_info = None
    lines = []
    used_h = 0.0
    overflow = False

    def push(entry):
        nonlocal used_h, overflow
        lines.append(entry)
        used_h += line_h + (line_h * 0.25 if entry[3] else 0.0)
        if max_h is not None and used_h > max_h:
            overflow = True

    for p_idx, para in enumerate(paras):
        if overflow:
            break
        use_dc = (drop_cap and p_idx == 0 and len(para) >= 2 and col_w >= 90)
        if use_dc:
            dc_char = para[0].upper()
            para_rest = para[1:].lstrip()
            dc_font = QFont(font.family(), max(12, int(round(font.pointSize() * 2.3))), QFont.Bold)
            dc_fm = QFontMetricsF(dc_font)
            dc_w = min(col_w * 0.4, dc_fm.horizontalAdvance(dc_char) + 6.0)
            dc_lines = 2
            drop_info = (dc_char, dc_font, dc_w, dc_lines * line_h)
        else:
            para_rest = para
            dc_w = 0.0
            dc_lines = 0

        words = para_rest.split()
        if not words:
            continue
        cur_line = []
        line_idx_in_para = 0
        for word in words:
            indent_x = dc_w if (use_dc and line_idx_in_para < dc_lines) else 0.0
            avail_w = max(24.0, col_w - indent_x)
            candidate = (" ".join(cur_line + [word])) if cur_line else word
            if fm.horizontalAdvance(candidate) <= avail_w or not cur_line:
                cur_line.append(word)
            else:
                push((" ".join(cur_line), indent_x, avail_w, False))
                line_idx_in_para += 1
                cur_line = [word]
                if overflow:
                    cur_line = []
                    break
        if cur_line:
            indent_x = dc_w if (use_dc and line_idx_in_para < dc_lines) else 0.0
            avail_w = max(24.0, col_w - indent_x)
            push((" ".join(cur_line), indent_x, avail_w, True))

    result = (lines, line_h, drop_info, overflow)
    if len(_LAYOUT_CACHE) > 600:
        _LAYOUT_CACHE.clear()
    _LAYOUT_CACHE[key] = result
    return result


def draw_newspaper_columns(painter: QPainter, rect: QRectF, text: str, data: PortfolioItem,
                           base_pt: float, ink_color: QColor, rule_color: QColor,
                           accent_color: QColor = None, max_cols: int = None):
    """
    Render multi-column formatted newspaper prose inside `rect`, automatically fitting font size
    so no text is ever clipped/cropped, drawing column divider rules and optional drop-cap.
    """
    if not text or rect.width() < 24 or rect.height() < 14:
        return
    cols = max(1, min(4, int(max_cols if max_cols is not None else getattr(data, "columns", 1))))
    if rect.width() / cols < 85 and cols > 1:
        cols = max(1, int(rect.width() // 85))

    col_gap = 14.0 if cols > 1 else 0.0
    col_w = (rect.width() - col_gap * (cols - 1)) / float(cols)

    # Draw vertical newspaper column rules
    if cols > 1:
        painter.save()
        painter.setPen(QPen(rule_color, 0.9, Qt.DashLine if data.box_style == "broadsheet" else Qt.SolidLine))
        for c_i in range(1, cols):
            rx = rect.left() + c_i * col_w + (c_i - 0.5) * col_gap
            painter.drawLine(QPointF(rx, rect.top() + 2), QPointF(rx, rect.bottom() - 2))
        painter.restore()

    use_drop_cap = bool(getattr(data, "drop_cap", False))
    align_flag = qt_align_flag(getattr(data, "align", "left"))

    # Largest font size <= base_pt (0.5pt steps) that fits across `cols` without clipping —
    # binary search; wrapping stops once the box is full, so long documents stay cheap
    capacity = rect.height() * cols * 0.98
    top_pt = max(5.0, float(base_pt))
    sizes = [top_pt - i * 0.5 for i in range(int((top_pt - 5.0) * 2) + 1)]   # descending

    def fits(pt):
        res = _layout_paragraphs_into_lines(text, make_card_font(data, pt), col_w, use_drop_cap, capacity)
        return not res[3]

    lo, hi = 0, len(sizes) - 1
    best = hi
    while lo <= hi:
        mid = (lo + hi) // 2
        if fits(sizes[mid]):
            best, hi = mid, mid - 1
        else:
            lo = mid + 1
    font = make_card_font(data, sizes[best])
    lines, line_h, drop_info, _ = _layout_paragraphs_into_lines(text, font, col_w, use_drop_cap, capacity)

    painter.save()
    painter.setFont(font)
    painter.setPen(ink_color)

    # Draw drop cap in first column if active
    if drop_info:
        dc_char, dc_font, dc_w, dc_h = drop_info
        painter.save()
        painter.setFont(dc_font)
        painter.setPen(accent_color or ink_color)
        painter.drawText(
            QRectF(rect.left(), rect.top() - 2, dc_w - 3, dc_h + 4),
            Qt.AlignLeft | Qt.AlignTop,
            dc_char
        )
        painter.restore()

    col_idx = 0
    y_cursor = rect.top()
    for line_text, indent_x, avail_w, is_para_end in lines:
        if y_cursor + line_h > rect.bottom() + 2:
            col_idx += 1
            if col_idx >= cols:
                break
            y_cursor = rect.top()
            indent_x = 0.0
            avail_w = col_w

        col_x = rect.left() + col_idx * (col_w + col_gap) + (indent_x if col_idx == 0 else 0.0)
        w_line = avail_w if col_idx == 0 else col_w
        painter.drawText(
            QRectF(col_x, y_cursor, w_line, line_h + 2),
            align_flag | Qt.AlignVCenter,
            line_text
        )
        y_cursor += line_h + (line_h * 0.22 if is_para_end else 0.0)

    painter.restore()


# ─── Canvas Graphics Items ─────────────────────────────────────────────────────

HANDLE = 14   # resize handle px
ROT_HANDLE = 16

class BaseCard(QGraphicsItem):
    """Draggable, resizable, rotatable card on the canvas with optional group link."""

    def __init__(self, data: PortfolioItem):
        super().__init__()
        self.data = data
        self.setPos(data.x, data.y)
        self.setFlags(
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        self._resizing = False
        self._rotating = False
        self._scaled_cache = (None, None, None)   # (source pixmap key, size, scaled)
        self._res_start = QPointF()
        self._orig_w = data.w
        self._orig_h = data.h
        self._sync_transform()

    def _scaled(self, pix: QPixmap, w: int, h: int) -> QPixmap:
        """Smooth-scaled copy of `pix` fitted into w×h, cached until the size or source changes."""
        key, size, scaled = self._scaled_cache
        if key != pix.cacheKey() or size != (w, h):
            scaled = pix.scaled(max(1, w), max(1, h), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._scaled_cache = (pix.cacheKey(), (w, h), scaled)
        return scaled

    def _sync_transform(self):
        self.setTransformOriginPoint(self.data.w / 2.0, self.data.h / 2.0)
        self.setRotation(float(getattr(self.data, "rotation", 0.0)))

    # ── geometry ──────────────────────────────────────────────────────────────

    def boundingRect(self):
        return QRectF(0, 0, self.data.w, self.data.h)

    def _handle_rect(self):
        w, h = self.data.w, self.data.h
        return QRectF(w - HANDLE, h - HANDLE, HANDLE, HANDLE)

    def _rot_handle_rect(self):
        w = self.data.w
        return QRectF(w / 2.0 - ROT_HANDLE / 2.0, 2.0, ROT_HANDLE, ROT_HANDLE)

    # ── snapping & group movement ─────────────────────────────────────────────

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            sc = self.scene()
            if getattr(sc, "snap_to_grid", False) and not getattr(sc, "_in_bsp_layout", False) and not getattr(sc, "_in_group_move", False):
                value = QPointF(
                    round(value.x() / GRID) * GRID,
                    round(value.y() / GRID) * GRID,
                )
            old_pos = self.pos()
            dx = value.x() - old_pos.x()
            dy = value.y() - old_pos.y()
            self.data.x = value.x()
            self.data.y = value.y()

            # Move linked group members together when group_locked is True
            gid = getattr(self.data, "group_id", "")
            if (gid and getattr(self.data, "group_locked", True)
                    and not getattr(sc, "_in_bsp_layout", False)
                    and not getattr(sc, "_in_group_move", False)
                    and (abs(dx) > 1e-4 or abs(dy) > 1e-4)):
                mods = QApplication.keyboardModifiers()
                if not (mods & Qt.AltModifier):
                    sc._in_group_move = True
                    try:
                        for other in sc.items():
                            if (isinstance(other, BaseCard) and other is not self
                                    and getattr(other.data, "group_id", "") == gid
                                    and not other.isSelected()):
                                np = QPointF(other.pos().x() + dx, other.pos().y() + dy)
                                other.setPos(np)
                                other.data.x = np.x()
                                other.data.y = np.y()
                    finally:
                        sc._in_group_move = False
        return super().itemChange(change, value)

    # ── resize & rotate mouse events ──────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.isSelected() and self._rot_handle_rect().contains(event.pos()):
            self._rotating = True
            event.accept()
            return
        if event.button() == Qt.LeftButton and self._handle_rect().contains(event.pos()):
            self._resizing = True
            self._res_start = event.pos()
            self._orig_w = self.data.w
            self._orig_h = self.data.h
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._rotating:
            center_scene = self.mapToScene(QPointF(self.data.w / 2.0, self.data.h / 2.0))
            cur_scene = event.scenePos()
            angle_rad = math.atan2(cur_scene.x() - center_scene.x(), -(cur_scene.y() - center_scene.y()))
            deg = math.degrees(angle_rad)
            if event.modifiers() & Qt.ShiftModifier:
                deg = round(deg / 15.0) * 15.0
            else:
                # Snap lightly near cardinal 0, 90, -90, 180
                for card_deg in (-180.0, -90.0, 0.0, 90.0, 180.0):
                    if abs(deg - card_deg) < 4.0:
                        deg = card_deg
                        break
            self.data.rotation = float(round(deg, 1))
            self._sync_transform()
            self.update()
            if self.scene():
                self.scene().item_selected.emit(self.data)
            return
        if self._resizing:
            dx = event.pos().x() - self._res_start.x()
            dy = event.pos().y() - self._res_start.y()
            nw = max(80.0, self._orig_w + dx)
            nh = max(36.0, self._orig_h + dy)
            if self.scene() and getattr(self.scene(), "snap_to_grid", False):
                nw = max(80.0, round(nw / GRID) * GRID)
                nh = max(40.0, round(nh / GRID) * GRID)
            self.prepareGeometryChange()
            self.data.w = nw
            self.data.h = nh
            self._sync_transform()
            self.update()
            if self.scene():
                self.scene().item_selected.emit(self.data)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._resizing = False
        self._rotating = False
        super().mouseReleaseEvent(event)

    # ── selection / handle / group paint helpers ──────────────────────────────

    def _paint_selection(self, painter):
        w, h = self.data.w, self.data.h
        gid = getattr(self.data, "group_id", "")

        # attached-links badge (top-right)
        n_links = len(getattr(self.data, "links", []) or [])
        if n_links and w > 60:
            br = QRectF(w - 40, 4, 36, 15)
            painter.save()
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(21, 101, 192, 220))
            painter.drawRoundedRect(br, 7, 7)
            painter.setFont(QFont("Segoe UI Symbol", 7, QFont.Bold))
            painter.setPen(QColor("white"))
            painter.drawText(br, Qt.AlignCenter, f"🔗 {n_links}")
            painter.restore()

        # Highlight group siblings when any member of the group is selected
        if gid and self.scene() and not self.isSelected():
            for sel in self.scene().selectedItems():
                if isinstance(sel, BaseCard) and getattr(sel.data, "group_id", "") == gid:
                    painter.save()
                    painter.setPen(QPen(QColor("#FF8F00"), 1.5, Qt.DotLine))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawRect(QRectF(1.5, 1.5, w - 3, h - 3))
                    painter.restore()
                    break

        if self.isSelected():
            pen = QPen(QColor("#2979FF"), 2, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(QRectF(1, 1, w - 2, h - 2))

            # Resize grip (bottom-right)
            r = self._handle_rect()
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#2979FF"))
            painter.drawRect(r)

            # Rotate grip (top-center)
            rr = self._rot_handle_rect()
            painter.setBrush(QColor("#00897B"))
            painter.setPen(QPen(QColor("white"), 1))
            painter.drawEllipse(rr)
            painter.setFont(QFont("Segoe UI Symbol", 7, QFont.Bold))
            painter.setPen(QColor("white"))
            painter.drawText(rr, Qt.AlignCenter, "↻")

            # Group badge (top-left) if grouped
            if gid:
                badge_r = QRectF(4, 4, 54, 15)
                locked = getattr(self.data, "group_locked", True)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor("#FF8F00" if locked else "#546E7A"))
                painter.drawRoundedRect(badge_r, 3, 3)
                painter.setFont(QFont("Arial", 6, QFont.Bold))
                painter.setPen(QColor("white"))
                painter.drawText(badge_r, Qt.AlignCenter, "🔗 GROUP" if locked else "🔓 FREE")

    # ── context menu & double click ──────────────────────────────────────────

    def contextMenuEvent(self, event):
        if self.scene() and self.scene().views():
            mw = self.scene().views()[0].main_window
            mw.show_item_context(self, event.screenPos())

    def mouseDoubleClickEvent(self, event):
        if self.scene() and self.scene().views():
            mw = self.scene().views()[0].main_window
            mw.props.load(self.data)
            mw.props.title_e.setFocus()


# ── IMAGE CARD ─────────────────────────────────────────────────────────────────

class ImageCard(BaseCard):
    def __init__(self, data):
        super().__init__(data)
        self._pix = None
        self._reload()

    def _reload(self):
        img = item_image(self.data)
        self._pix = QPixmap.fromImage(img) if not img.isNull() else None

    def paint(self, painter, option, widget):
        r = self.boundingRect()
        bg = QColor(self.data.bg_color) if getattr(self.data, "bg_color", "") else QColor("#111111")
        painter.fillRect(r, bg)

        if self._pix and not self._pix.isNull():
            # Fit without cropping or skewing
            scaled = self._scaled(self._pix, int(round(r.width())), int(round(r.height())))
            dx = (r.width()  - scaled.width())  / 2.0
            dy = (r.height() - scaled.height()) / 2.0
            painter.drawPixmap(int(round(dx)), int(round(dy)), scaled)
        else:
            painter.setPen(QColor("#444"))
            painter.setFont(QFont("Arial", 28))
            painter.drawText(r, Qt.AlignCenter, "📷")

        # gradient footer
        if self.data.title or self.data.url or self.data.notes:
            gh = min(r.height() * 0.4, 54.0)
            grad = QLinearGradient(0, r.height() - gh, 0, r.height())
            grad.setColorAt(0, QColor(0, 0, 0, 0))
            grad.setColorAt(1, QColor(0, 0, 0, 210))
            painter.fillRect(QRectF(0, r.height() - gh, r.width(), gh), QBrush(grad))
            painter.setPen(QColor(self.data.text_color or "white"))
            f = make_card_font(self.data, max(8, self.data.font_size), bold_override=True)
            painter.setFont(f)
            painter.drawText(
                QRectF(8, r.height() - gh + 6, r.width() - 16, gh - 10),
                Qt.AlignVCenter | qt_align_flag(self.data.align),
                self.data.title or self.data.notes
            )

        self._paint_selection(painter)


# ── STRAPLINE CARD (Separable Article Kicker / Overline) ───────────────────────

class StraplineCard(BaseCard):
    """Newspaper kicker / strapline box (separable, rotatable, packable in BSP)."""

    def paint(self, painter, option, widget):
        r = self.boundingRect()
        w, h = r.width(), r.height()
        st = paint_newspaper_frame(painter, r, self.data, "broadsheet")
        ink    = QColor(st["ink"])
        accent = QColor(st["accent"])
        rule   = QColor(st["rule"])

        text = (self.data.strapline or self.data.title or "KICKER").upper()

        if self.data.box_style == "tabloid_splash":
            painter.fillRect(QRectF(2, 2, w - 4, h - 4), accent)
            pen_col = QColor("white")
        else:
            # Classic newspaper double overline/underline kicker rules
            painter.setPen(QPen(accent, 1.8))
            painter.drawLine(QPointF(8, 5), QPointF(w - 8, 5))
            painter.setPen(QPen(rule, 0.9))
            painter.drawLine(QPointF(8, h - 5), QPointF(w - 8, h - 5))
            pen_col = QColor(self.data.text_color) if self.data.text_color else accent

        scale = min(w / 260.0, h / 38.0)
        pt = max(7.0, min(28.0, float(self.data.font_size or 10) * max(0.75, min(1.8, scale))))
        f = make_card_font(self.data, pt, bold_override=True)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 1.5)
        painter.setFont(f)
        painter.setPen(pen_col)
        painter.drawText(
            QRectF(10, 4, w - 20, h - 8),
            Qt.AlignVCenter | qt_align_flag(self.data.align or "left") | Qt.TextWordWrap,
            text
        )
        self._paint_selection(painter)


# ── HEADLINE CARD (Separable Article Banner Title) ─────────────────────────────

class HeadlineCard(BaseCard):
    """Separable newspaper headline/title box."""

    def paint(self, painter, option, widget):
        r = self.boundingRect()
        w, h = r.width(), r.height()
        st = paint_newspaper_frame(painter, r, self.data, "broadsheet")
        ink    = QColor(st["ink"])
        accent = QColor(st["accent"])

        text = self.data.title or "Headline"
        pad_x = 14.0 if st.get("left_bar") else 10.0
        avail_w = max(20.0, w - pad_x - 10.0)
        avail_h = max(16.0, h - 14.0)

        if self.data.box_style == "tabloid_splash":
            painter.fillRect(QRectF(2, 2, w - 4, h - 4), QColor("#111111"))
            ink = QColor("#ffffff")

        # Auto-fit headline font size so it fills the box cleanly without clipping
        scale = math.sqrt((w * h) / (380.0 * 90.0))
        target_pt = max(9.0, float(self.data.title_font_size or 18) * max(0.7, min(2.4, scale)))
        for pt in [target_pt - i for i in range(int(target_pt - 7) + 1)]:
            f = make_card_font(self.data, pt, bold_override=(True if not self.data.bold else self.data.bold))
            fm = QFontMetricsF(f)
            br = fm.boundingRect(QRectF(0, 0, avail_w, 2000),
                                 qt_align_flag(self.data.align) | Qt.TextWordWrap, text)
            if br.height() <= avail_h or pt <= 8:
                break

        painter.setFont(f)
        painter.setPen(ink)
        painter.drawText(
            QRectF(pad_x, 7, avail_w, avail_h),
            Qt.AlignVCenter | qt_align_flag(self.data.align) | Qt.TextWordWrap,
            text
        )
        self._paint_selection(painter)


# ── ABSTRACT CARD (Separable Article Standfirst / Deck) ────────────────────────

class AbstractCard(BaseCard):
    """Separable newspaper abstract / standfirst / summary deck box."""

    def paint(self, painter, option, widget):
        r = self.boundingRect()
        w, h = r.width(), r.height()
        st = paint_newspaper_frame(painter, r, self.data, "broadsheet")
        ink    = QColor(st["ink"])
        accent = QColor(st["accent"])
        rule   = QColor(st["rule"])

        pad_x = 14.0 if st.get("left_bar") else 12.0
        # Top and bottom standfirst rules
        painter.setPen(QPen(rule, 1.0))
        painter.drawLine(QPointF(pad_x, 8), QPointF(w - 12, 8))
        painter.drawLine(QPointF(pad_x, h - 8), QPointF(w - 12, h - 8))

        text = self.data.abstract or self.data.notes or self.data.title or "Standfirst"
        scale = math.sqrt((w * h) / (380.0 * 95.0))
        base_pt = max(7.0, float(self.data.font_size or 10) * max(0.8, min(1.8, scale)))

        # Default italic editorial deck feel unless overridden
        orig_italic = self.data.italic
        if not self.data.bold and not self.data.underline:
            self.data.italic = True
        try:
            draw_newspaper_columns(
                painter,
                QRectF(pad_x, 12, w - pad_x - 12, h - 24),
                text, self.data, base_pt, ink, rule, accent,
                max_cols=max(1, min(2, self.data.columns))
            )
        finally:
            self.data.italic = orig_italic

        self._paint_selection(painter)


# ── ARTICLE CARD ───────────────────────────────────────────────────────────────

class ArticleCard(BaseCard):
    def __init__(self, data):
        super().__init__(data)
        self._thumb = None
        self._reload()

    def _reload(self):
        img = item_image(self.data)
        self._thumb = QPixmap.fromImage(img) if not img.isNull() else None

    def paint(self, painter, option, widget):
        r  = self.boundingRect()
        w, h = r.width(), r.height()
        st = paint_newspaper_frame(painter, r, self.data, "broadsheet")
        ink    = QColor(st["ink"])
        accent = QColor(st["accent"])
        muted  = QColor(st["muted"])
        rule   = QColor(st["rule"])

        pad_l = 14.0 if st.get("left_bar") else 12.0
        pad_r = 12.0
        avail_w = max(30.0, w - pad_l - pad_r)
        scale = max(0.75, min(1.75, math.sqrt((w * h) / (380.0 * 300.0))))
        y = float(max(10, st.get("top_bar", 0) + 7))

        # 1. Optional Strapline (if present on unified article card)
        if self.data.strapline and y < h - 40:
            sf = make_card_font(self.data, max(7, 8 * scale), bold_override=True)
            sf.setLetterSpacing(QFont.AbsoluteSpacing, 1.2)
            painter.setFont(sf)
            painter.setPen(accent)
            sh = max(14.0, 16.0 * scale)
            painter.drawText(QRectF(pad_l, y, avail_w, sh),
                             qt_align_flag(self.data.align) | Qt.AlignVCenter,
                             self.data.strapline.upper())
            y += sh + 3.0

        # 2. Optional Headline / Title (skipped if empty on body-only split card)
        show_title = self.data.title if self.data.title else ("" if self.data.group_id else "Headline")
        if show_title and y < h - 36:
            head_pt = max(9.0, float(self.data.title_font_size or 15) * scale)
            hf = make_card_font(self.data, head_pt, bold_override=True)
            hfm = QFontMetricsF(hf)
            max_head_h = max(22.0, min(h * 0.28, 72.0 * scale))
            if st.get("banner_head"):
                br = hfm.boundingRect(QRectF(0, 0, avail_w - 12, max_head_h),
                                      qt_align_flag(self.data.align) | Qt.TextWordWrap, show_title)
                bh = min(max_head_h, br.height() + 10)
                painter.fillRect(QRectF(pad_l, y, avail_w, bh), accent)
                painter.setFont(hf)
                painter.setPen(QColor("white"))
                painter.drawText(QRectF(pad_l + 6, y + 4, avail_w - 12, bh - 6),
                                 qt_align_flag(self.data.align) | Qt.AlignVCenter | Qt.TextWordWrap,
                                 show_title)
                y += bh + 6.0
            else:
                br = hfm.boundingRect(QRectF(0, 0, avail_w, max_head_h),
                                      qt_align_flag(self.data.align) | Qt.TextWordWrap, show_title)
                bh = min(max_head_h, max(20.0, br.height() + 4))
                painter.setFont(hf)
                painter.setPen(ink)
                painter.drawText(QRectF(pad_l, y, avail_w, bh),
                                 qt_align_flag(self.data.align) | Qt.AlignTop | Qt.TextWordWrap,
                                 show_title)
                y += bh + 5.0
                painter.setPen(QPen(rule, 0.9))
                painter.drawLine(QPointF(pad_l, y), QPointF(w - pad_r, y))
                y += 6.0

        # 3. Optional Abstract / Standfirst (if present on unified article card)
        if self.data.abstract and y < h - 45:
            af = make_card_font(self.data, max(7, (self.data.font_size or 9) * 0.95 * scale), italic_override=True)
            afm = QFontMetricsF(af)
            max_abs_h = max(18.0, min(h * 0.22, 54.0 * scale))
            abr = afm.boundingRect(QRectF(0, 0, avail_w, max_abs_h),
                                   qt_align_flag(self.data.align) | Qt.TextWordWrap, self.data.abstract)
            ah = min(max_abs_h, max(16.0, abr.height() + 4))
            painter.setFont(af)
            painter.setPen(muted)
            painter.drawText(QRectF(pad_l, y, avail_w, ah),
                             qt_align_flag(self.data.align) | Qt.AlignTop | Qt.TextWordWrap,
                             self.data.abstract)
            y += ah + 5.0
            painter.setPen(QPen(rule, 0.7, Qt.DotLine))
            painter.drawLine(QPointF(pad_l, y), QPointF(w - pad_r, y))
            y += 6.0

        # 4. Thumbnail left + multi-column body prose right
        ref = (self.data.url or os.path.basename(self.data.file_path) or "")[:60]
        foot_h = 18.0 if ref else 6.0
        body_h = max(10.0, h - y - foot_h - 4.0)

        thumb_w = 0
        if self._thumb and not self._thumb.isNull() and self._thumb.width() > 0 and body_h > 30:
            max_tw = min(int(avail_w * 0.35), int(130 * scale))
            max_th = int(body_h)
            if max_tw >= 36:
                scaled = self._scaled(self._thumb, max_tw, max_th)
                thumb_w = scaled.width()
                painter.drawPixmap(int(pad_l), int(y), scaled)

        notes_x = pad_l + thumb_w + (10.0 if thumb_w else 0.0)
        notes_w = w - notes_x - pad_r
        body_text = self.data.notes
        if body_text and notes_w > 36 and body_h > 16:
            body_pt = max(6.5, float(self.data.font_size or 9) * scale)
            draw_newspaper_columns(
                painter,
                QRectF(notes_x, y, notes_w, body_h),
                body_text, self.data, body_pt, ink, rule, accent,
                max_cols=self.data.columns
            )

        # 5. Footer with file/url reference
        if ref and h > 60:
            painter.setFont(QFont("Courier New", max(6, int(6.5 * scale))))
            painter.setPen(muted)
            painter.drawText(QRectF(pad_l, h - foot_h - 2, avail_w, foot_h),
                             Qt.AlignVCenter | Qt.AlignLeft, ref)

        self._paint_selection(painter)


# ── TEXT BLOCK ─────────────────────────────────────────────────────────────────

class TextBlock(BaseCard):
    def paint(self, painter, option, widget):
        r  = self.boundingRect()
        w, h = r.width(), r.height()
        st = paint_newspaper_frame(painter, r, self.data, "broadsheet")
        ink    = QColor(st["ink"])
        accent = QColor(st["accent"])
        rule   = QColor(st["rule"])

        pad_l = 14.0 if st.get("left_bar") else 10.0
        pad_r = 10.0
        avail_w = max(24.0, w - pad_l - pad_r)
        scale = max(0.75, min(1.8, math.sqrt((w * h) / (420.0 * 280.0))))
        y_off = float(max(8, st.get("top_bar", 0) + 6))

        if self.data.strapline and y_off < h - 36:
            sf = make_card_font(self.data, max(7, 8 * scale), bold_override=True)
            sf.setLetterSpacing(QFont.AbsoluteSpacing, 1.2)
            painter.setFont(sf)
            painter.setPen(accent)
            painter.drawText(QRectF(pad_l, y_off, avail_w, 16 * scale),
                             qt_align_flag(self.data.align) | Qt.AlignVCenter,
                             self.data.strapline.upper())
            y_off += 18 * scale

        if self.data.title and y_off < h - 30:
            tf = make_card_font(self.data, max(8.5, float(self.data.title_font_size or 13) * scale), bold_override=True)
            tfm = QFontMetricsF(tf)
            br = tfm.boundingRect(QRectF(0, 0, avail_w, h * 0.3),
                                  qt_align_flag(self.data.align) | Qt.TextWordWrap, self.data.title)
            th = min(h * 0.3, max(20.0, br.height() + 4))
            painter.setFont(tf)
            painter.setPen(ink)
            painter.drawText(QRectF(pad_l, y_off, avail_w, th),
                             Qt.AlignTop | qt_align_flag(self.data.align) | Qt.TextWordWrap,
                             self.data.title)
            y_off += th + 4
            painter.setPen(QPen(rule, 0.9))
            painter.drawLine(QPointF(pad_l, y_off), QPointF(w - pad_r, y_off))
            y_off += 6

        body_rect = QRectF(pad_l, y_off, avail_w, max(12.0, h - y_off - 8.0))
        body_pt = max(6.5, float(self.data.font_size or 9) * scale)
        draw_newspaper_columns(
            painter, body_rect,
            self.data.notes or "Body",
            self.data, body_pt, ink, rule, accent,
            max_cols=self.data.columns
        )

        self._paint_selection(painter)

    def mouseDoubleClickEvent(self, event):
        if self.scene() and self.scene().views():
            mw = self.scene().views()[0].main_window
            mw.props.load(self.data)
            mw.props.notes_e.setFocus()


# ── URL CARD ───────────────────────────────────────────────────────────────────

class URLCard(BaseCard):
    def __init__(self, data):
        super().__init__(data)
        self.data.w = max(self.data.w, 180)
        self.data.h = max(self.data.h, 70)

    def paint(self, painter, option, widget):
        r  = self.boundingRect()
        w, h = r.width(), r.height()
        st = paint_newspaper_frame(painter, r, self.data, "dark_dispatch")
        ink    = QColor(st["ink"])
        accent = QColor(st["accent"])
        muted  = QColor(st["muted"])
        rule   = QColor(st["rule"])

        pad_l = 14.0 if st.get("left_bar") else 12.0
        avail_w = max(24.0, w - pad_l - 28.0)
        scale = max(0.75, min(1.75, math.sqrt((w * h) / (300.0 * 120.0))))
        y = float(max(8, st.get("top_bar", 0) + 6))

        if self.data.strapline and y < h - 30:
            sf = make_card_font(self.data, max(6.5, 7.5 * scale), bold_override=True)
            painter.setFont(sf)
            painter.setPen(accent)
            painter.drawText(QRectF(pad_l, y, avail_w, 14 * scale),
                             qt_align_flag(self.data.align) | Qt.AlignVCenter,
                             self.data.strapline.upper())
            y += 15 * scale

        tf = make_card_font(self.data, max(8.5, float(self.data.title_font_size or 12) * scale), bold_override=True)
        painter.setFont(tf)
        painter.setPen(accent if self.data.box_style == "dark_dispatch" else ink)
        th = max(18.0, 22.0 * scale)
        painter.drawText(QRectF(pad_l, y, avail_w, th),
                         Qt.AlignVCenter | qt_align_flag(self.data.align),
                         self.data.title or "Link")
        y += th + 2.0

        uf = QFont("Courier New", max(6, int(round(7.5 * scale))))
        painter.setFont(uf)
        painter.setPen(muted)
        uh = max(14.0, 16.0 * scale)
        painter.drawText(QRectF(pad_l, y, avail_w, uh),
                         Qt.AlignVCenter | qt_align_flag(self.data.align),
                         (self.data.url or "https://...")[:75])
        y += uh + 4.0

        if self.data.notes and y < h - 10:
            body_pt = max(6.5, float(self.data.font_size or 8.5) * scale)
            draw_newspaper_columns(
                painter,
                QRectF(pad_l, y, avail_w, h - y - 8),
                self.data.notes, self.data, body_pt, ink, rule, accent,
                max_cols=max(1, min(2, self.data.columns))
            )

        # arrow
        painter.setFont(QFont("Arial", max(10, int(round(13 * scale))), QFont.Bold))
        painter.setPen(accent)
        painter.drawText(QRectF(w - 28, h - 28, 24, 24),
                         Qt.AlignCenter, "↗")

        self._paint_selection(painter)


# ── LINK TREE CARD ─────────────────────────────────────────────────────────────

_ICON_CACHE = {}


def _icon_pixmap(uri: str):
    """Decoded favicon (raster data URIs only), cached; None if absent."""
    if not uri or not uri.startswith("data:image/") or "svg" in uri[:30]:
        return None
    if uri not in _ICON_CACHE:
        img = QImage()
        img.loadFromData(base64.b64decode(uri.split(",", 1)[1]))
        _ICON_CACHE[uri] = QPixmap.fromImage(img) if not img.isNull() else None
    return _ICON_CACHE[uri]


class LinkTreeCard(BaseCard):
    """The project's link tree as a box in the layout (exported with a links.html link)."""

    def _links(self):
        if self.scene() and self.scene().views():
            return self.scene().views()[0].main_window.project.links
        return getattr(self, "_export_links", [])

    def paint(self, painter, option, widget):
        r  = self.boundingRect()
        w, h = r.width(), r.height()
        st = paint_newspaper_frame(painter, r, self.data, "broadsheet")
        ink    = QColor(st["ink"])
        accent = QColor(st["accent"])
        muted  = QColor(st["muted"])
        rule   = QColor(st["rule"])

        pad_l = 14.0 if st.get("left_bar") else 12.0
        avail_w = max(24.0, w - pad_l - 12.0)
        scale = max(0.75, min(1.6, math.sqrt((w * h) / (300.0 * 260.0))))
        y = float(max(8, st.get("top_bar", 0) + 6))

        hf = make_card_font(self.data, max(9.0, float(self.data.title_font_size or 13) * scale), bold_override=True)
        painter.setFont(hf)
        painter.setPen(ink)
        th = max(20.0, QFontMetricsF(hf).height() + 4.0)
        painter.drawText(QRectF(pad_l, y, avail_w, th),
                         Qt.AlignVCenter | qt_align_flag(self.data.align),
                         self.data.title or "Links")
        y += th + 2.0
        painter.setPen(QPen(rule, 0.9))
        painter.drawLine(QPointF(pad_l, y), QPointF(w - 12, y))
        y += 6.0

        links = [l for l in self._links() if l.get("url") or l.get("label")]
        if not links:
            painter.setFont(make_card_font(self.data, max(7.0, 8.5 * scale), italic_override=True))
            painter.setPen(muted)
            painter.drawText(QRectF(pad_l, y, avail_w, h - y - 8),
                             Qt.AlignTop | Qt.AlignLeft | Qt.TextWordWrap,
                             "No links")
        else:
            lf = make_card_font(self.data, max(7.5, float(self.data.font_size or 10) * scale), bold_override=True)
            uf = QFont("Courier New", max(6, int(round(7 * scale))))
            row_h = max(30.0, 34.0 * scale)
            for lnk in links:
                if y + row_h > h - 6:
                    painter.setFont(uf); painter.setPen(muted)
                    painter.drawText(QRectF(pad_l, y, avail_w, 14), Qt.AlignLeft, "…")
                    break
                painter.fillRect(QRectF(pad_l, y + 3, 3, row_h - 8), accent)
                tx = pad_l + 9
                icon = _icon_pixmap(lnk.get("icon", ""))
                if icon is not None:
                    isz = int(row_h * 0.55)
                    painter.drawPixmap(QRectF(tx, y + (row_h - isz) / 2.0, isz, isz).toRect(),
                                       icon.scaled(isz, isz, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    tx += isz + 6
                painter.setFont(lf); painter.setPen(ink)
                painter.drawText(QRectF(tx, y + 2, w - tx - 12, row_h * 0.55),
                                 Qt.AlignVCenter | Qt.AlignLeft,
                                 lnk.get("label") or lnk.get("page_title") or lnk.get("url", ""))
                painter.setFont(uf); painter.setPen(muted)
                painter.drawText(QRectF(tx, y + row_h * 0.52, w - tx - 12, row_h * 0.42),
                                 Qt.AlignVCenter | Qt.AlignLeft,
                                 link_domain(lnk.get("url") or "") + ("  ▶" if lnk.get("embed") and lnk.get("preview", True) else ""))
                y += row_h

        self._paint_selection(painter)

    def mouseDoubleClickEvent(self, event):
        if self.scene() and self.scene().views():
            self.scene().views()[0].main_window._edit_links()


# ── PULL QUOTE CARD ────────────────────────────────────────────────────────────

def quote_font_pt(text: str, box_w: float, box_h: float) -> float:
    """Type size that roughly fills the box with the quote (canvas shrinks further to fit)."""
    n = max(8, len(text or ""))
    px = math.sqrt(max(1.0, box_w * box_h) / (n * 0.55 * 1.35))
    return max(9.0, min(60.0, px * 0.75))


class QuoteCard(BaseCard):
    """Pull quote: big quotation mark, the quote, and an attribution line."""

    def paint(self, painter, option, widget):
        r = self.boundingRect()
        w, h = r.width(), r.height()
        st = paint_newspaper_frame(painter, r, self.data, "broadsheet")
        ink    = QColor(self.data.text_color) if self.data.text_color else QColor(st["ink"])
        accent = QColor(st["accent"])

        mark_pt = max(24.0, min(90.0, h * 0.42))
        painter.setFont(QFont("Georgia", int(mark_pt), QFont.Bold))
        painter.setPen(accent)
        painter.drawText(QRectF(10, -mark_pt * 0.18, mark_pt, mark_pt * 1.2), Qt.AlignLeft | Qt.AlignTop, "“")

        quote = self.data.notes or "Quote"
        attrib = self.data.title
        pad_l = 14.0 + mark_pt * 0.55
        bw = max(20.0, w - pad_l - 14)
        target = quote_font_pt(quote, bw, h - 40)

        def attr_font(pt):
            fa = make_card_font(self.data, max(7.0, min(14.0, pt * 0.55)), bold_override=True, italic_override=False)
            fa.setLetterSpacing(QFont.AbsoluteSpacing, 1.2)
            return fa

        for pt in [target - i for i in range(int(target - 7) + 1)]:   # shrink until quote + attribution fit
            f = make_card_font(self.data, pt, italic_override=True)
            attr_h = QFontMetricsF(attr_font(pt)).height() + 6 if attrib else 0.0
            box = QRectF(pad_l, 10, bw, max(16.0, h - 18 - attr_h))
            if QFontMetricsF(f).boundingRect(QRectF(0, 0, bw, 4000), Qt.TextWordWrap, quote).height() <= box.height():
                break
        painter.setFont(f)
        painter.setPen(ink)
        painter.drawText(box, Qt.AlignVCenter | qt_align_flag(self.data.align) | Qt.TextWordWrap, quote)
        if attrib:
            painter.setFont(attr_font(f.pointSizeF()))
            painter.setPen(accent)
            painter.drawText(QRectF(pad_l, h - attr_h - 6, bw, attr_h),
                             Qt.AlignVCenter | Qt.AlignRight, "— " + attrib.upper())
        self._paint_selection(painter)


# ── HEART / DONATE CARD ────────────────────────────────────────────────────────

class DonateCard(BaseCard):
    """The ♥ donate button as a box in the layout."""

    def paint(self, painter, option, widget):
        r = self.boundingRect()
        w, h = r.width(), r.height()
        st = paint_newspaper_frame(painter, r, self.data, "broadsheet")
        accent = QColor(self.data.text_color) if self.data.text_color else QColor(st["accent"])
        ink = QColor(st["ink"])
        msg = self.data.notes
        label = self.data.title or "Donate"

        heart = min(h * (0.38 if msg else 0.48), w * 0.3)
        painter.setRenderHint(QPainter.Antialiasing)
        pill_h = max(18.0, min(heart * 0.34, h * 0.2))
        msg_h =(QFontMetricsF(make_card_font(self.data, max(7.0, float(self.data.font_size or 10)))).height() * 2 + 4
                 if msg else 0.0)
        cx, top = w / 2.0, max(6.0, (h - (heart + 6 + pill_h + msg_h)) / 2.0)   # centre the group
        path = QPainterPath()                        # heart from two arcs and a point
        s = heart
        path.moveTo(cx, top + s * 0.3)
        path.cubicTo(cx, top, cx - s * 0.5, top, cx - s * 0.5, top + s * 0.3)
        path.cubicTo(cx - s * 0.5, top + s * 0.6, cx, top + s * 0.8, cx, top + s)
        path.cubicTo(cx, top + s * 0.8, cx + s * 0.5, top + s * 0.6, cx + s * 0.5, top + s * 0.3)
        path.cubicTo(cx + s * 0.5, top, cx, top, cx, top + s * 0.3)
        painter.fillPath(path, accent)

        y = top + s + 6
        fb =make_card_font(self.data, max(7.0, pill_h * 0.42), bold_override=True)
        pill_w = min(w - 16, QFontMetricsF(fb).horizontalAdvance(label) + pill_h * 1.4)
        pill = QRectF(cx - pill_w / 2.0, y, pill_w, pill_h)
        painter.setPen(Qt.NoPen)
        painter.setBrush(accent)
        painter.drawRoundedRect(pill, pill_h / 2.0, pill_h / 2.0)
        painter.setFont(fb)
        painter.setPen(QColor("white"))
        painter.drawText(pill, Qt.AlignCenter, label)
        if msg:
            painter.setFont(make_card_font(self.data, max(7.0, float(self.data.font_size or 10)), italic_override=True))
            painter.setPen(ink)
            painter.drawText(QRectF(8, pill.bottom() + 4, w - 16, max(10.0, h - pill.bottom() - 8)),
                             Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, msg)
        self._paint_selection(painter)


# ─── Canvas Scene ──────────────────────────────────────────────────────────────

def make_card(data: PortfolioItem) -> BaseCard:
    return {
        "image":     ImageCard,
        "article":   ArticleCard,
        "strapline": StraplineCard,
        "headline":  HeadlineCard,
        "abstract":  AbstractCard,
        "text":      TextBlock,
        "url":       URLCard,
        "linktree":  LinkTreeCard,
        "quote":     QuoteCard,
        "donate":    DonateCard,
    }.get(data.kind, ImageCard)(data)


class FolioScene(QGraphicsScene):
    item_selected = pyqtSignal(object)   # PortfolioItem | None

    def __init__(self):
        super().__init__(0, 0, CANVAS_W, CANVAS_H)
        self.snap_to_grid = True
        self.setBackgroundBrush(QBrush(QColor("#dbd6ce")))
        self.selectionChanged.connect(self._on_selection_changed)

    def set_texture(self, tile: QImage = None, base: str = "#dbd6ce"):
        """Canvas background: the portfolio texture tile, or a plain colour."""
        if tile is not None and not tile.isNull():
            self.setBackgroundBrush(QBrush(QPixmap.fromImage(tile)))
        else:
            self.setBackgroundBrush(QBrush(QColor(base)))

    # ── grid ──────────────────────────────────────────────────────────────────

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        if not self.snap_to_grid:
            return
        pen = QPen(QColor("#cac5bd"), 0.5)
        painter.setPen(pen)
        l = int(rect.left())  - int(rect.left())  % GRID
        t = int(rect.top())   - int(rect.top())   % GRID
        x = l
        while x < rect.right():
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
            x += GRID
        y = t
        while y < rect.bottom():
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)
            y += GRID

    # ── selection ────────────────────────────────────────────────────────────

    def _on_selection_changed(self):
        sel = [c for c in self.selectedItems() if isinstance(c, BaseCard)]
        self.item_selected.emit(sel[0].data if sel else None)

    # ── add ───────────────────────────────────────────────────────────────────

    def add_card(self, data: PortfolioItem) -> BaseCard:
        card = make_card(data)
        self.addItem(card)
        return card

    # ── BSP auto-layout ───────────────────────────────────────────────────────

    def bsp_autolayout(self, cards=None):
        """
        Aspect-ratio-preserving Binary Space Partitioning (slicing floorplan)
        that packs all component rectangles (images, text boxes, link boxes,
        articles, and grouped/rotated strapline/headline/abstract components)
        into a tight, seamless rectangular tiling without cropping or skewing.
        """
        if cards is None:
            sel = [c for c in self.selectedItems() if isinstance(c, BaseCard)]
            cards = sel if len(sel) >= 2 else list(self.items())
        cards = [c for c in cards if isinstance(c, BaseCard)]
        if not cards:
            return

        margin = float(GRID * 2)
        gap    = float(GRID)
        target_w = float(CANVAS_W) - margin * 2.0
        target_h = float(CANVAS_H) * 0.5 - margin
        target_ar = target_w / max(1.0, target_h)

        # Group cards that share a locked group_id into cohesive layout units
        units = self._build_bsp_units(cards)
        if len(units) > 1:
            random.shuffle(units)

        tree = self._bsp_build_tree_from_units(units, gap, target_ar)

        # Ensure root width is large enough so no leaf violates its minimum size
        root_w = max(target_w, tree["min_w"])
        root_h = tree["m"] * root_w + tree["c"]

        # Expand scene height if needed to fit the uncropped packed layout
        req_scene_w = max(float(CANVAS_W), root_w + margin * 2.0)
        req_scene_h = max(float(CANVAS_H), root_h + margin * 2.0)
        self.setSceneRect(0, 0, req_scene_w, req_scene_h)

        self._in_bsp_layout = True
        try:
            self._bsp_apply_tree(tree, margin, margin, root_w, gap)
        finally:
            self._in_bsp_layout = False

        self.update()
        sel = self.selectedItems()
        if sel:
            self.item_selected.emit(sel[0].data)

    def _build_bsp_units(self, cards):
        """Partition cards into single-card units and group units. A group is always one
        unit — its pieces never scatter across the outer layout (lock only affects dragging)."""
        groups = {}
        ungrouped = []
        for c in cards:
            gid = getattr(c.data, "group_id", "")
            if gid:
                groups.setdefault(gid, []).append(c)
            else:
                ungrouped.append([c])
        units = list(ungrouped)
        for gid, gcards in groups.items():
            units.append(gcards)
        return units

    # (aspect clamp lo, hi, min width base, min width per unit of aspect)
    _LEAF_LIMITS = {
        "image":     (0.15, 6.0, 160.0, 120.0),
        "strapline": (0.2, 14.0, 140.0, 32.0),
        "headline":  (0.2, 10.0, 180.0, 54.0),
        "abstract":  (0.25, 8.0, 200.0, 68.0),
        "url":       (0.25, 8.0, 200.0, 80.0),
        "quote":     (0.6, 5.0, 220.0, 70.0),
        "donate":    (0.6, 3.0, 150.0, 50.0),
    }

    def _card_intrinsic_metrics(self, card: BaseCard, local_ar: float = None):
        """
        Return (scene_aspect_ratio, min_scene_width, local_aspect_ratio)
        accounting for both the component's natural uncropped aspect ratio
        and its current rotation angle. `local_ar` overrides the card's own shape
        (used when a group arrangement wants e.g. a tall standfirst column).
        """
        lo, hi, mw_base, mw_k = self._LEAF_LIMITS.get(card.data.kind, (0.2, 6.0, 220.0, 140.0))
        if local_ar is None:
            local_ar = float(card.data.w) / max(1.0, float(card.data.h))
            if isinstance(card, ImageCard):
                if card._pix is None or card._pix.isNull():
                    card._reload()
                if card._pix and not card._pix.isNull() and card._pix.height() > 0:
                    local_ar = float(card._pix.width()) / float(card._pix.height())
        local_ar = max(lo, min(hi, local_ar))
        min_w_local = max(mw_base, mw_k * local_ar)

        theta = math.radians(float(getattr(card.data, "rotation", 0.0)))
        ct = abs(math.cos(theta))
        st = abs(math.sin(theta))
        w_factor = local_ar * ct + st
        h_factor = local_ar * st + ct
        scene_ar = w_factor / max(1e-6, h_factor)
        min_h_local = min_w_local / local_ar
        min_w_scene = min_h_local * w_factor
        return scene_ar, min_w_scene, local_ar

    def _make_leaf_node(self, c: BaseCard, local_ar: float = None):
        scene_ar, min_w_scene, local_ar = self._card_intrinsic_metrics(c, local_ar)
        return {
            "kind": "leaf",
            "card": c,
            "ar": scene_ar,
            "local_ar": local_ar,
            "m": 1.0 / scene_ar,
            "c": 0.0,
            "min_w": min_w_scene,
        }

    def _join_nodes_H(self, L, R, gap: float):
        mL, cL, mwL = L["m"], L["c"], L["min_w"]
        mR, cR, mwR = R["m"], R["c"], R["min_w"]
        denom = mL + mR
        mH = (mL * mR) / denom
        cH = (mL * cR + mR * cL - mL * mR * gap) / denom
        mwH_from_L = gap + (denom * mwL - (cR - cL)) / mR
        mwH_from_R = gap + (denom * mwR - (cL - cR)) / mL
        mwH = max(mwL + mwR + gap, mwH_from_L, mwH_from_R)
        return {"kind": "H", "left": L, "right": R, "m": mH, "c": cH, "min_w": mwH, "gap": gap}

    def _join_nodes_V(self, L, R, gap: float):
        mL, cL, mwL = L["m"], L["c"], L["min_w"]
        mR, cR, mwR = R["m"], R["c"], R["min_w"]
        return {"kind": "V", "left": L, "right": R, "m": mL + mR, "c": cL + cR + gap,
                "min_w": max(mwL, mwR), "gap": gap}

    def _stack_V(self, nodes, gap):
        node = nodes[0]
        for nd in nodes[1:]:
            node = self._join_nodes_V(node, nd, gap)
        return node

    GROUP_ORDER = {"strapline": 0, "headline": 1, "abstract": 2, "article": 3, "text": 4, "image": 5, "url": 6}

    def _build_group_subtree(self, group_cards, gap: float):
        """
        One block for a group (kicker / headline / standfirst / body / …). Inside it the
        BSP picks an arrangement each run — plain stack, kicker turned into a vertical
        sidebar, standfirst as a column beside the body, or image beside the text —
        always in reading order. Pieces sit closer than the outer gap so the group reads
        as one unit. A kicker the user angled themselves is never re-rotated.
        """
        g = max(3.0, gap * 0.3)
        cards = sorted(group_cards, key=lambda c: self.GROUP_ORDER.get(c.data.kind, 9))
        first = lambda kind: next((c for c in cards if c.data.kind == kind), None)
        kicker, head, stand = first("strapline"), first("headline"), first("abstract")
        header = [c for c in (kicker, head, stand) if c]
        rest = [c for c in cards if c not in header]
        images = [c for c in rest if c.data.kind == "image"]
        texts = [c for c in rest if c.data.kind != "image"]

        def auto_turnable(c):
            rot = round(float(getattr(c.data, "rotation", 0.0)))
            return rot == 0 or (abs(rot) == 90 and getattr(c.data, "bsp_turned", False))

        user_side_kicker = kicker is not None and not auto_turnable(kicker) and \
            abs(round(float(kicker.data.rotation))) == 90

        variants = ["stack"]
        if kicker and (head or stand or rest) and auto_turnable(kicker):
            variants.append("side_kicker")
        if stand and rest:
            variants.append("stand_column")
        if images and texts:
            variants.append("image_beside")
        choice = "side_kicker" if user_side_kicker else random.choice(variants)

        if kicker and auto_turnable(kicker):
            turn = choice == "side_kicker"
            kicker.data.rotation = -90.0 if turn else 0.0
            kicker.data.bsp_turned = turn

        leaf = self._make_leaf_node
        stack_ar = lambda c: max(2.5, float(c.data.w) / max(1.0, float(c.data.h)))  # undo an earlier column shape
        if stand:
            stand_leaf = leaf(stand, stack_ar(stand))

        if choice == "side_kicker":
            body = [leaf(c) for c in [head] if c] + ([stand_leaf] if stand else []) + [leaf(c) for c in rest]
            return self._join_nodes_H(leaf(kicker), self._stack_V(body, g), g)

        top = [leaf(c) for c in (kicker, head) if c]
        if choice == "stand_column":
            col = leaf(stand, 0.55)
            body = self._join_nodes_H(col, self._stack_V([leaf(c) for c in rest], g), g)
            return self._stack_V(top + [body], g)
        if stand:
            top.append(stand_leaf)
        if choice == "image_beside":
            pic = self._stack_V([leaf(c) for c in images], g)
            txt = self._stack_V([leaf(c) for c in texts], g)
            pair = (pic, txt) if random.random() < 0.5 else (txt, pic)
            body = self._join_nodes_H(pair[0], pair[1], g)
            return self._stack_V(top + [body], g) if top else body
        return self._stack_V(top + [leaf(c) for c in rest], g)

    def _bsp_build_tree_from_units(self, units, gap: float, target_ar: float):
        """
        Build a bottom-up slicing tree over `units` where each node's height H
        is an exact affine function of its width W:  H(W) = m * W + c.
        """
        if len(units) == 1:
            u = units[0]
            if len(u) == 1:
                return self._make_leaf_node(u[0])
            return self._build_group_subtree(u, gap)

        n = len(units)
        if n == 2:
            split_idx = 1
        else:
            lo = max(1, int(n * 0.35))
            hi = min(n - 1, int(math.ceil(n * 0.65)))
            split_idx = random.randint(lo, hi)

        r_left  = split_idx / float(n)
        r_right = (n - split_idx) / float(n)

        if target_ar >= 1.1:
            left_target  = max(0.35, target_ar * r_left)
            right_target = max(0.35, target_ar * r_right)
        else:
            left_target  = min(3.5, target_ar / max(0.2, r_left))
            right_target = min(3.5, target_ar / max(0.2, r_right))

        L = self._bsp_build_tree_from_units(units[:split_idx], gap, left_target)
        R = self._bsp_build_tree_from_units(units[split_idx:], gap, right_target)

        nodeH = self._join_nodes_H(L, R, gap)
        nodeV = self._join_nodes_V(L, R, gap)

        arH = 1.0 / max(1e-6, nodeH["m"])
        arV = 1.0 / max(1e-6, nodeV["m"])
        target_ar = max(0.2, min(5.0, target_ar))

        errH = abs(math.log(arH / target_ar)) + random.uniform(-0.18, 0.18)
        errV = abs(math.log(arV / target_ar)) + random.uniform(-0.18, 0.18)

        max_canvas_w = float(CANVAS_W) - float(GRID * 4)
        if nodeH["min_w"] > max_canvas_w and nodeV["min_w"] <= max_canvas_w:
            return nodeV
        return nodeH if errH <= errV else nodeV

    def _bsp_apply_tree(self, node, x: float, y: float, w: float, gap: float):
        if node["kind"] == "leaf":
            c = node["card"]
            h_scene = node["m"] * w
            local_ar = node.get("local_ar", float(c.data.w) / max(1.0, float(c.data.h)))
            theta = math.radians(float(getattr(c.data, "rotation", 0.0)))
            ct = abs(math.cos(theta))
            st = abs(math.sin(theta))
            w_factor = local_ar * ct + st

            h_local = w / max(1e-6, w_factor)
            w_local = local_ar * h_local

            cx = x + w / 2.0
            cy = y + h_scene / 2.0
            pos_x = cx - w_local / 2.0
            pos_y = cy - h_local / 2.0

            c.prepareGeometryChange()
            c.data.w = float(w_local)
            c.data.h = float(h_local)
            c._sync_transform()
            c.setPos(float(pos_x), float(pos_y))
            c.data.x, c.data.y = float(pos_x), float(pos_y)
            c.update()
            return

        L, R = node["left"], node["right"]
        gap = node.get("gap", gap)          # groups use a tighter inner gap
        if node["kind"] == "H":
            mL, cL = L["m"], L["c"]
            mR, cR = R["m"], R["c"]
            wL = (mR * (w - gap) + cR - cL) / (mL + mR)
            wR = w - gap - wL
            self._bsp_apply_tree(L, x,            y, wL, gap)
            self._bsp_apply_tree(R, x + wL + gap, y, wR, gap)
        else:
            hL = L["m"] * w + L["c"]
            self._bsp_apply_tree(L, x, y,            w, gap)
            self._bsp_apply_tree(R, x, y + hL + gap, w, gap)


# ─── Canvas View ───────────────────────────────────────────────────────────────

class FolioView(QGraphicsView):
    def __init__(self, scene, main_window):
        super().__init__(scene)
        self.main_window = main_window
        self.setRenderHints(
            QPainter.Antialiasing |
            QPainter.SmoothPixmapTransform |
            QPainter.TextAntialiasing
        )
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setAcceptDrops(True)
        self._panning   = False
        self._pan_start = None

    # ── zoom / pan ────────────────────────────────────────────────────────────

    def wheelEvent(self, e):
        f = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
        self.scale(f, f)

    def mousePressEvent(self, e):
        if e.button() == Qt.MiddleButton:
            self._panning   = True
            self._pan_start = e.pos()
            self.setCursor(Qt.ClosedHandCursor)
        else:
            super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._panning:
            d = e.pos() - self._pan_start
            self._pan_start = e.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - d.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - d.y())
        else:
            super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MiddleButton:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
        else:
            super().mouseReleaseEvent(e)

    # ── file drag-and-drop from outside ──────────────────────────────────────

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        e.acceptProposedAction()

    def dropEvent(self, e):
        pos = self.mapToScene(e.pos())
        offset = QPointF(0, 0)
        for url in e.mimeData().urls():
            path = url.toLocalFile()
            gi = self.main_window.add_file_at(path, pos.x() + offset.x(),
                                                     pos.y() + offset.y())
            if gi:
                offset += QPointF(GRID * 2, GRID * 2)


# ─── File Browser ──────────────────────────────────────────────────────────────

class FileBrowser(QWidget):
    files_requested = pyqtSignal(list)   # [str paths]

    def __init__(self):
        super().__init__()
        self._root = ""
        v = QVBoxLayout(self)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(4)

        # header
        btn_row = QHBoxLayout()
        self.open_btn = QPushButton("📂 Open Folder")
        self.open_btn.clicked.connect(self.choose_folder)
        btn_row.addWidget(self.open_btn)
        v.addLayout(btn_row)

        self.path_lbl = QLabel("No folder opened")
        self.path_lbl.setStyleSheet("color:#888;font-size:9px;")
        self.path_lbl.setWordWrap(True)
        v.addWidget(self.path_lbl)

        # filter bar
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("🔍 filter files…")
        v.addWidget(self.filter)

        # file tree
        self.model = QFileSystemModel()
        self.model.setNameFilters([f"*{e}" for e in ALL_EXTS])
        self.model.setNameFilterDisables(False)

        # The model is attached in choose_folder(): attaching it before a root path is set
        # makes Windows enumerate every drive (OneDrive, network) — seconds at startup.
        self.tree = QTreeView()
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.doubleClicked.connect(self._on_double)
        v.addWidget(self.tree)

        # add buttons
        add_sel = QPushButton("➕ Add Selected → Canvas")
        add_sel.setStyleSheet("background:#1565C0;color:white;padding:6px;border-radius:3px;font-weight:bold;")
        add_sel.clicked.connect(self._emit_selected)
        v.addWidget(add_sel)

        add_all = QPushButton("📋 Add All Files → Canvas")
        add_all.setStyleSheet("background:#37474F;color:white;padding:5px;border-radius:3px;")
        add_all.clicked.connect(self._emit_all)
        v.addWidget(add_all)

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Open Folder")
        if path:
            self._root = path
            self.model.setRootPath(path)
            if self.tree.model() is None:
                self.tree.setModel(self.model)
                for col in (1, 2, 3):
                    self.tree.hideColumn(col)
            self.tree.setRootIndex(self.model.index(path))
            self.path_lbl.setText(path)

    def _on_double(self, idx):
        path = self.model.filePath(idx)
        if os.path.isfile(path):
            self.files_requested.emit([path])

    def _get_selected_paths(self):
        seen, paths = set(), []
        for idx in self.tree.selectedIndexes():
            if idx.column() != 0:
                continue
            p = self.model.filePath(idx)
            if p not in seen and os.path.isfile(p):
                ext = Path(p).suffix.lower()
                if ext in ALL_EXTS:
                    paths.append(p)
                    seen.add(p)
        return paths

    def _get_all_paths(self):
        if not self._root:
            return []
        paths = []
        for root, _, files in os.walk(self._root):
            for f in sorted(files):
                ext = Path(f).suffix.lower()
                if ext in ALL_EXTS:
                    paths.append(os.path.join(root, f))
        return paths

    def _emit_selected(self):
        paths = self._get_selected_paths()
        if paths:
            self.files_requested.emit(paths)

    def _emit_all(self):
        paths = self._get_all_paths()
        if paths:
            self.files_requested.emit(paths)


# ─── Properties Panel ──────────────────────────────────────────────────────────

class DockTitleBar(QWidget):
    """Title bar for the properties dock: collapse to the bar, float / re-dock, close."""

    def __init__(self, dock: QDockWidget):
        super().__init__(dock)
        self.dock = dock
        h = QHBoxLayout(self)
        h.setContentsMargins(8, 3, 4, 3)
        h.setSpacing(2)
        self.fold = QToolButton(); self.fold.setArrowType(Qt.DownArrow); self.fold.setAutoRaise(True)
        self.fold.setToolTip("Collapse / expand")
        self.fold.clicked.connect(self.toggle_collapsed)
        title = QLabel(dock.windowTitle())
        title.setStyleSheet("color:#bbb;font-weight:bold;letter-spacing:0.5px;")
        h.addWidget(self.fold); h.addWidget(title, 1)
        self._extras = [title]
        for text, tip, fn in (("⧉", "Float / dock", lambda: dock.setFloating(not dock.isFloating())),
                              ("✕", "Close", dock.close)):
            b = QToolButton(); b.setText(text); b.setToolTip(tip); b.setAutoRaise(True)
            b.setStyleSheet("QToolButton{color:#bbb;border:none;padding:0 4px}QToolButton:hover{color:white}")
            b.clicked.connect(fn); h.addWidget(b)
            self._extras.append(b)
        self.setStyleSheet("background:#333;")
        self._collapsed = False
        self._saved_w = None
        self._min_w = dock.minimumWidth() or 265
        dock.topLevelChanged.connect(lambda _: self._apply())

    def toggle_collapsed(self):
        if not self._collapsed and not self.dock.isFloating():
            self._saved_w = self.dock.width()
        self._collapsed = not self._collapsed
        self._apply()

    def _apply(self):
        """Collapsed + floating → just the title bar; collapsed + docked → a thin strip."""
        c = self._collapsed
        self.dock.widget().setVisible(not c)
        strip = c and not self.dock.isFloating()
        for w in self._extras:
            w.setVisible(not strip)
        if strip:
            self.fold.setArrowType(Qt.LeftArrow)
            self.dock.setMinimumWidth(0)
            self.dock.setFixedWidth(34)
        else:
            self.fold.setArrowType(Qt.RightArrow if c else Qt.DownArrow)
            self.dock.setMinimumWidth(self._min_w)
            self.dock.setMaximumWidth(16777215)
            mw = self.dock.parent()
            if not c and not self.dock.isFloating() and self._saved_w and isinstance(mw, QMainWindow):
                mw.resizeDocks([self.dock], [self._saved_w], Qt.Horizontal)
        if self.dock.isFloating():
            self.dock.adjustSize()

    def mouseDoubleClickEvent(self, e):
        self.dock.setFloating(not self.dock.isFloating())


class CollapsibleSection(QWidget):
    """A header that folds its contents away."""

    def __init__(self, title, expanded=True, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 2, 0, 2)
        v.setSpacing(4)
        self.toggle = QToolButton()
        self.toggle.setText(title.upper())
        self.toggle.setCheckable(True)
        self.toggle.setChecked(expanded)
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.toggle.setStyleSheet("QToolButton{border:none;border-top:1px solid #444;color:#999;font-weight:bold;"
                                  "font-size:9px;letter-spacing:1px;padding:6px 0 2px 0;text-align:left}")
        self.toggle.toggled.connect(self._on_toggle)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self.toggle)
        v.addWidget(self.body)
        self._on_toggle(expanded)

    def _on_toggle(self, on):
        self.toggle.setArrowType(Qt.DownArrow if on else Qt.RightArrow)
        self.body.setVisible(on)


class PropertiesPanel(QWidget):
    changed        = pyqtSignal()
    split_article  = pyqtSignal(object)   # PortfolioItem
    merge_group    = pyqtSignal(str)      # group_id
    detach_group   = pyqtSignal(object)   # PortfolioItem
    replace_source = pyqtSignal(object)   # PortfolioItem
    edit_image     = pyqtSignal(object)   # PortfolioItem
    extract_text   = pyqtSignal(object)   # PortfolioItem
    fetch_url      = pyqtSignal(object)   # PortfolioItem
    edit_linktree  = pyqtSignal()

    # which content rows / actions each card type shows
    KIND_ROWS = {
        "image":     ("title", "url", "mailto", "links", "notes"),
        "article":   ("strap", "title", "abstract", "url", "mailto", "access", "links", "notes"),
        "strapline": ("strap", "url", "mailto", "links"),
        "headline":  ("title", "url", "mailto", "links"),
        "abstract":  ("abstract", "url", "mailto", "links"),
        "text":      ("strap", "title", "url", "mailto", "links", "notes"),
        "url":       ("strap", "title", "url", "mailto", "links", "notes"),
        "linktree":  ("title",),
        "quote":     ("notes", "title", "url", "mailto", "links"),
        "donate":    ("title", "notes", "url"),
    }
    KIND_LABELS = {   # kind → {row: label}
        "quote":   {"notes": "Quote:", "title": "Attribution:", "url": "Source:"},
        "donate":  {"title": "Button:", "notes": "Message:", "url": "Donate link:"},
        "image":   {"title": "Title:", "url": "Opens:", "notes": "Caption:"},
        "article": {"title": "Headline:", "url": "Link:", "notes": "Body:"},
        "text":    {"title": "Title:", "notes": "Text:"},
        "url":     {"title": "Name:", "url": "Address:", "notes": "Description:"},
        "linktree": {"title": "Title:"},
    }
    KIND_ACTIONS = {
        "image":    ("replace", "edit_img"),
        "article":  ("replace", "extract", "cover", "edit_img", "split"),
        "text":     ("replace",),
        "url":      ("fetch",),
        "linktree": ("links_dlg",),
    }

    def __init__(self):
        super().__init__()
        self._data = None
        self._loading = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        root = QVBoxLayout(container)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # --- header label
        self.kind_lbl = QLabel("CARD PROPERTIES")
        self.kind_lbl.setStyleSheet("font-weight:bold;color:#58a6ff;font-size:10px;letter-spacing:1px;")
        root.addWidget(self.kind_lbl)

        # --- Content fields (rows shown per card type, see KIND_ROWS)
        self.strap_e    = QLineEdit(); self.strap_e.setPlaceholderText("Kicker")
        self.title_e    = QLineEdit(); self.title_e.setPlaceholderText("Headline")
        self.abstract_e = QLineEdit(); self.abstract_e.setPlaceholderText("Standfirst")
        self.url_e      = QLineEdit(); self.url_e.setPlaceholderText("https://")
        self.mailto_e   = QLineEdit(); self.mailto_e.setPlaceholderText("portfolio email")
        self.mailto_e.setToolTip("Contact for this card: an ✉ button on it, and where document requests go")
        self.access_c   = QComboBox()
        for key, label in (("", "Portfolio setting"), ("preview", "Preview only"),
                           ("password", "Preview + password download"), ("open", "Preview + open download")):
            self.access_c.addItem(label, key)
        self.links_e = QPlainTextEdit()
        self.links_e.setPlaceholderText("Label | https://…  (one per line)")
        self.links_e.setFixedHeight(58)
        self.notes_e = QTextEdit()
        self.notes_e.setPlaceholderText("Body")
        self.notes_e.setMinimumHeight(90)
        self.notes_e.setMaximumHeight(150)
        self._rows = {"strap": self.strap_e, "title": self.title_e, "abstract": self.abstract_e,
                      "url": self.url_e, "mailto": self.mailto_e, "access": self.access_c,
                      "links": self.links_e, "notes": self.notes_e}
        self._default_labels = {"strap": "Kicker:", "title": "Headline:", "abstract": "Standfirst:",
                                "url": "URL:", "mailto": "Email:", "access": "Document:",
                                "links": "Links:", "notes": "Body:"}
        # one container per row, so a hidden row leaves no gap (QFormLayout keeps its spacing)
        self._row_boxes, self._row_labels = {}, {}
        for key, wdg in self._rows.items():
            box = QWidget()
            hl = QHBoxLayout(box)
            hl.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(self._default_labels[key])
            lbl.setFixedWidth(88)
            multi = key in ("links", "notes")
            lbl.setAlignment(Qt.AlignRight | (Qt.AlignTop if multi else Qt.AlignVCenter))
            if multi:
                lbl.setContentsMargins(0, 6, 0, 0)
            hl.addWidget(lbl, 0, Qt.AlignTop if multi else Qt.Alignment())
            hl.addWidget(wdg, 1)
            box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)   # extra height goes to the stretch
            root.addWidget(box)
            self._row_boxes[key], self._row_labels[key] = box, lbl
        self._rows_layout = root
        self._rows_at = root.indexOf(self._row_boxes["strap"])

        # --- Type-specific actions (see KIND_ACTIONS)
        self.replace_btn = QPushButton("⇄ Replace…")
        self.replace_btn.clicked.connect(lambda: self._data and self.replace_source.emit(self._data))
        self.edit_img_btn = QPushButton("✎ Edit Image…")
        self.edit_img_btn.clicked.connect(lambda: self._data and self.edit_image.emit(self._data))
        self.extract_btn = QPushButton("📑 Extract Text…")
        self.extract_btn.clicked.connect(lambda: self._data and self.extract_text.emit(self._data))
        self.cover_btn = QPushButton("🖼  Set Cover…")
        self.cover_btn.clicked.connect(self._pick_cover)
        self.fetch_btn = QPushButton("⟳ Fetch Title && Description")
        self.fetch_btn.clicked.connect(lambda: self._data and (self.apply(), self.fetch_url.emit(self._data)))
        self.links_dlg_btn = QPushButton("🌳 Edit Link Tree…")
        self.links_dlg_btn.clicked.connect(self.edit_linktree.emit)
        self.split_btn = QPushButton("✂ Split into Group")
        self.split_btn.setToolTip("Kicker / Headline / Standfirst / Body")
        self.split_btn.setStyleSheet("background:#6a1b9a;color:white;font-weight:bold;padding:4px 6px;")
        self.split_btn.clicked.connect(self._on_split_clicked)
        self._actions = {"replace": self.replace_btn, "edit_img": self.edit_img_btn,
                         "extract": self.extract_btn, "cover": self.cover_btn, "fetch": self.fetch_btn,
                         "links_dlg": self.links_dlg_btn, "split": self.split_btn}
        act_grid = QHBoxLayout(); act_grid2 = QHBoxLayout(); act_grid3 = QHBoxLayout()
        act_grid.addWidget(self.replace_btn); act_grid.addWidget(self.edit_img_btn)
        act_grid2.addWidget(self.extract_btn); act_grid2.addWidget(self.cover_btn)
        act_grid3.addWidget(self.fetch_btn); act_grid3.addWidget(self.links_dlg_btn); act_grid3.addWidget(self.split_btn)
        for row in (act_grid, act_grid2, act_grid3):
            root.addLayout(row)

        # --- Article group (only for grouped pieces)
        self.group_box = QWidget()
        grp_row2 = QHBoxLayout(self.group_box)
        grp_row2.setContentsMargins(0, 0, 0, 0)
        self.group_lock_cb = QCheckBox("🔗 Lock Group")
        self.group_lock_cb.toggled.connect(self._on_group_lock_toggled)
        self.merge_btn = QPushButton("⊕ Merge")
        self.merge_btn.clicked.connect(self._on_merge_clicked)
        self.detach_btn = QPushButton("🔓 Detach")
        self.detach_btn.clicked.connect(self._on_detach_clicked)
        grp_row2.addWidget(self.group_lock_cb)
        grp_row2.addWidget(self.merge_btn)
        grp_row2.addWidget(self.detach_btn)
        root.addWidget(self.group_box)

        root.addWidget(self._sep())

        apply_btn = QPushButton("✓  Apply")
        apply_btn.setStyleSheet("background:#2e7d32;color:white;padding:6px;border-radius:3px;font-weight:bold;")
        apply_btn.clicked.connect(self.apply)
        root.addWidget(apply_btn)

        # --- Newspaper Box & Typography Formatting (hidden for pictures)
        self.typo_box = CollapsibleSection("Style & Typography", expanded=True)
        typo_v = self.typo_box.body_layout
        root.addWidget(self.typo_box)
        tf = QFormLayout()
        tf.setLabelAlignment(Qt.AlignRight)
        tf.setHorizontalSpacing(8)

        self.style_combo = QComboBox()
        for k, v in BOX_STYLES.items():
            self.style_combo.addItem(v["label"], k)
        self.style_combo.currentIndexChanged.connect(self._live_style_apply)
        tf.addRow("Box Theme:", self.style_combo)

        self.font_combo = QFontComboBox()
        self.font_combo.currentFontChanged.connect(self._live_style_apply)
        tf.addRow("Font:", self.font_combo)

        sz_row = QHBoxLayout()
        self.title_sz_spin = QSpinBox(); self.title_sz_spin.setRange(7, 72); self.title_sz_spin.setSuffix(" pt")
        self.title_sz_spin.setToolTip("Headline / Title font size")
        self.body_sz_spin  = QSpinBox(); self.body_sz_spin.setRange(6, 48);  self.body_sz_spin.setSuffix(" pt")
        self.body_sz_spin.setToolTip("Body / Notes font size")
        self.title_sz_spin.valueChanged.connect(self._live_style_apply)
        self.body_sz_spin.valueChanged.connect(self._live_style_apply)
        sz_row.addWidget(QLabel("Title:"))
        sz_row.addWidget(self.title_sz_spin)
        sz_row.addWidget(QLabel("Body:"))
        sz_row.addWidget(self.body_sz_spin)
        tf.addRow("Font Size:", sz_row)

        fmt_row = QHBoxLayout()
        self.bold_btn = QPushButton("B"); self.bold_btn.setCheckable(True); self.bold_btn.setFixedWidth(30)
        self.bold_btn.setStyleSheet("font-weight:bold;")
        self.ital_btn = QPushButton("I"); self.ital_btn.setCheckable(True); self.ital_btn.setFixedWidth(30)
        self.ital_btn.setStyleSheet("font-style:italic;")
        self.und_btn  = QPushButton("U"); self.und_btn.setCheckable(True);  self.und_btn.setFixedWidth(30)
        self.und_btn.setStyleSheet("text-decoration:underline;")
        self.dc_cb    = QCheckBox("Drop Cap")
        for w_btn in (self.bold_btn, self.ital_btn, self.und_btn, self.dc_cb):
            w_btn.toggled.connect(self._live_style_apply)
        fmt_row.addWidget(self.bold_btn)
        fmt_row.addWidget(self.ital_btn)
        fmt_row.addWidget(self.und_btn)
        fmt_row.addWidget(self.dc_cb)
        fmt_row.addStretch()
        tf.addRow("Format:", fmt_row)

        lay_row = QHBoxLayout()
        self.align_combo = QComboBox()
        self.align_combo.addItems(["left", "center", "right", "justify"])
        self.align_combo.currentTextChanged.connect(self._live_style_apply)
        self.cols_spin = QSpinBox(); self.cols_spin.setRange(1, 4); self.cols_spin.setSuffix(" col")
        self.cols_spin.valueChanged.connect(self._live_style_apply)
        lay_row.addWidget(self.align_combo)
        lay_row.addWidget(self.cols_spin)
        tf.addRow("Align / Cols:", lay_row)

        col_row = QHBoxLayout()
        self.fg_btn = QPushButton("🎨 Ink")
        self.fg_btn.clicked.connect(self._pick_fg)
        self.bg_btn = QPushButton("🎨 Paper")
        self.bg_btn.clicked.connect(self._pick_bg)
        self.clr_reset_btn = QPushButton("↺ Reset")
        self.clr_reset_btn.clicked.connect(self._reset_colors)
        col_row.addWidget(self.fg_btn)
        col_row.addWidget(self.bg_btn)
        col_row.addWidget(self.clr_reset_btn)
        tf.addRow("Colors:", col_row)

        typo_v.addLayout(tf)

        # --- Rotation controls
        rot_sec = CollapsibleSection("Rotation", expanded=False)
        self.typo_box.toggle.setText("STYLE && TYPOGRAPHY")
        root.addWidget(rot_sec)
        rot_row1 = QHBoxLayout()
        self.rot_spin = QDoubleSpinBox()
        self.rot_spin.setRange(-180.0, 180.0)
        self.rot_spin.setSingleStep(5.0)
        self.rot_spin.setSuffix("°")
        self.rot_spin.valueChanged.connect(self._on_rot_spin)
        self.rot_slider = QSlider(Qt.Horizontal)
        self.rot_slider.setRange(-180, 180)
        self.rot_slider.valueChanged.connect(self._on_rot_slider)
        rot_row1.addWidget(self.rot_spin)
        rot_row1.addWidget(self.rot_slider)
        rot_sec.body_layout.addLayout(rot_row1)

        rot_row2 = QHBoxLayout()
        for lbl_txt, deg in [("0°", 0.0), ("↺ -90°", -90.0), ("↻ +90°", 90.0), ("180°", 180.0)]:
            b = QPushButton(lbl_txt)
            b.clicked.connect(lambda _=False, d=deg: self._set_rotation(d))
            rot_row2.addWidget(b)
        rot_sec.body_layout.addLayout(rot_row2)

        # --- Size & position
        geo_sec = CollapsibleSection("Size && Position", expanded=False)
        root.addWidget(geo_sec)
        sf = QFormLayout()
        self.w_spin = QSpinBox(); self.w_spin.setRange(60, 3000); self.w_spin.setSuffix(" px")
        self.h_spin = QSpinBox(); self.h_spin.setRange(30, 3000); self.h_spin.setSuffix(" px")
        self.x_spin = QSpinBox(); self.x_spin.setRange(-1000, CANVAS_W * 2); self.x_spin.setSuffix(" px")
        self.y_spin = QSpinBox(); self.y_spin.setRange(-1000, CANVAS_H * 2); self.y_spin.setSuffix(" px")
        sf.addRow("Width:", self.w_spin)
        sf.addRow("Height:", self.h_spin)
        sf.addRow("X:", self.x_spin)
        sf.addRow("Y:", self.y_spin)
        geo_sec.body_layout.addLayout(sf)
        geo_row = QHBoxLayout()
        sz_btn = QPushButton("Apply Size")
        sz_btn.clicked.connect(self._apply_size)
        pos_btn = QPushButton("Apply Position")
        pos_btn.clicked.connect(self._apply_pos)
        geo_row.addWidget(sz_btn); geo_row.addWidget(pos_btn)
        geo_sec.body_layout.addLayout(geo_row)

        root.addStretch()
        self.setEnabled(False)

    def _lbl(self, text):
        l = QLabel(text); l.setStyleSheet("color:#aaa;font-size:10px;"); return l

    def _header(self, text):
        l = QLabel(text); l.setStyleSheet("font-weight:bold;color:#888;font-size:9px;letter-spacing:1px;"); return l

    def _sep(self):
        f = QFrame(); f.setFrameShape(QFrame.HLine); f.setStyleSheet("color:#444;"); return f

    def load(self, data: PortfolioItem):
        self._loading = True
        try:
            self._data = data
            gid_txt = f"  [Group {data.group_id[:5]}]" if getattr(data, "group_id", "") else ""
            self.kind_lbl.setText(f"{data.kind.upper()} CARD{gid_txt}")

            self.strap_e.setText(getattr(data, "strapline", ""))
            self.title_e.setText(data.title)
            self.abstract_e.setText(getattr(data, "abstract", ""))
            self.url_e.setText(data.url)
            self.mailto_e.setText(getattr(data, "mailto", ""))
            self.access_c.setCurrentIndex(max(0, self.access_c.findData(getattr(data, "pdf_access", ""))))
            self.links_e.setPlainText(format_links_text(getattr(data, "links", [])))
            self.notes_e.setPlainText(data.notes)
            self._show_for_kind(data)

            idx = self.style_combo.findData(getattr(data, "box_style", "broadsheet"))
            self.style_combo.setCurrentIndex(max(0, idx))
            self.font_combo.setCurrentFont(QFont(getattr(data, "font_family", "Georgia")))
            self.title_sz_spin.setValue(int(getattr(data, "title_font_size", 16)))
            self.body_sz_spin.setValue(int(getattr(data, "font_size", 10)))

            self.bold_btn.setChecked(bool(getattr(data, "bold", False)))
            self.ital_btn.setChecked(bool(getattr(data, "italic", False)))
            self.und_btn.setChecked(bool(getattr(data, "underline", False)))
            self.dc_cb.setChecked(bool(getattr(data, "drop_cap", False)))

            self.align_combo.setCurrentText(getattr(data, "align", "left"))
            self.cols_spin.setValue(int(getattr(data, "columns", 1)))

            rot = float(getattr(data, "rotation", 0.0))
            self.rot_spin.setValue(rot)
            self.rot_slider.setValue(int(round(rot)))

            self.group_lock_cb.setChecked(bool(getattr(data, "group_locked", True)))

            self.w_spin.setValue(int(round(data.w)))
            self.h_spin.setValue(int(round(data.h)))
            self.x_spin.setValue(int(round(data.x)))
            self.y_spin.setValue(int(round(data.y)))
            self.setEnabled(True)
        finally:
            self._loading = False

    def _show_for_kind(self, data):
        """Show only the fields and actions this card type uses."""
        kind = data.kind
        has_group = bool(getattr(data, "group_id", ""))
        has_doc = Path(data.file_path or "").suffix.lower() in DOC_EXTS
        rows = set(self.KIND_ROWS.get(kind, ()))
        if kind == "article" and not has_doc:
            rows.discard("access")
        labels = self.KIND_LABELS.get(kind, {})
        order = [k for k in self.KIND_ROWS.get(kind, ()) if k in rows] + [k for k in self._rows if k not in rows]
        for i, key in enumerate(order):                # rows in this type's own order
            box = self._row_boxes[key]
            self._rows_layout.removeWidget(box)
            self._rows_layout.insertWidget(self._rows_at + i, box)
            box.setVisible(key in rows)
            self._row_labels[key].setText(labels.get(key, self._default_labels[key]))
        self.notes_e.setPlaceholderText(labels.get("notes", "Body:").rstrip(":"))
        self.title_e.setPlaceholderText(labels.get("title", "Headline:").rstrip(":"))

        acts = set(self.KIND_ACTIONS.get(kind, ()))
        if kind == "article":
            if not has_doc:
                acts.discard("extract")
            if has_group:
                acts.discard("split")
        for key, b in self._actions.items():
            b.setVisible(key in acts)
        self.replace_btn.setText({"image": "⇄ Replace Image…",
                                  "article": "⇄ Replace Document…" if has_doc else "📎 Attach Document…",
                                  "text": "⇄ Text from File…"}.get(kind, "⇄ Replace…"))
        self.edit_img_btn.setText("✎ Edit Image…" if kind == "image" else "✎ Edit Cover…")

        self.group_box.setVisible(has_group)
        self.typo_box.setVisible(kind != "image")
        self.url_e.setPlaceholderText("portfolio donate link" if kind == "donate" else "https://")
        self.dc_cb.setVisible(kind in ("article", "text"))
        self.cols_spin.setVisible(kind in ("article", "text"))

    def clear(self):
        self._data = None
        self.setEnabled(False)

    def _live_style_apply(self, *_):
        if self._loading or not self._data:
            return
        self.apply()

    def apply(self):
        if not self._data:
            return
        self._data.strapline       = self.strap_e.text().strip()
        self._data.title           = self.title_e.text().strip()
        self._data.abstract        = self.abstract_e.text().strip()
        url                        = self.url_e.text().strip()
        self._data.url             = (parse_links_text(url) or [{"url": ""}])[0]["url"] if url else ""
        self._data.mailto          = self.mailto_e.text().strip().removeprefix("mailto:")
        self._data.pdf_access      = self.access_c.currentData() or ""
        self._data.links           = parse_links_text(self.links_e.toPlainText())
        self._data.notes           = self.notes_e.toPlainText()
        self._data.box_style       = self.style_combo.currentData() or "broadsheet"
        self._data.font_family     = self.font_combo.currentFont().family()
        self._data.title_font_size = int(self.title_sz_spin.value())
        self._data.font_size       = int(self.body_sz_spin.value())
        self._data.bold            = self.bold_btn.isChecked()
        self._data.italic          = self.ital_btn.isChecked()
        self._data.underline       = self.und_btn.isChecked()
        self._data.drop_cap        = self.dc_cb.isChecked()
        self._data.align           = self.align_combo.currentText()
        self._data.columns         = int(self.cols_spin.value())
        self.changed.emit()

    def _on_rot_spin(self, val):
        if self._loading or not self._data:
            return
        self._loading = True
        self.rot_slider.setValue(int(round(val)))
        self._loading = False
        self._data.rotation = float(val)
        self.changed.emit()

    def _on_rot_slider(self, val):
        if self._loading or not self._data:
            return
        self._loading = True
        self.rot_spin.setValue(float(val))
        self._loading = False
        self._data.rotation = float(val)
        self.changed.emit()

    def _set_rotation(self, deg: float):
        if not self._data:
            return
        self._loading = True
        self.rot_spin.setValue(deg)
        self.rot_slider.setValue(int(round(deg)))
        self._loading = False
        self._data.rotation = float(deg)
        self.changed.emit()

    def _pick_fg(self):
        if not self._data:
            return
        c = QColorDialog.getColor(QColor(self._data.text_color or "#111111"), self, "Select Text / Ink Color")
        if c.isValid():
            self._data.text_color = c.name()
            self.changed.emit()

    def _pick_bg(self):
        if not self._data:
            return
        c = QColorDialog.getColor(QColor(self._data.bg_color or "#fdfdf8"), self, "Select Box Paper / Background Color")
        if c.isValid():
            self._data.bg_color = c.name()
            self.changed.emit()

    def _reset_colors(self):
        if not self._data:
            return
        self._data.text_color = ""
        self._data.bg_color   = ""
        self.changed.emit()

    def _on_split_clicked(self):
        if self._data:
            self.apply()
            self.split_article.emit(self._data)

    def _on_merge_clicked(self):
        if self._data and getattr(self._data, "group_id", ""):
            self.merge_group.emit(self._data.group_id)

    def _on_detach_clicked(self):
        if self._data and getattr(self._data, "group_id", ""):
            self.detach_group.emit(self._data)

    def _on_group_lock_toggled(self, checked):
        if self._loading or not self._data:
            return
        self._data.group_locked = bool(checked)
        self.changed.emit()

    def _apply_size(self):
        if not self._data:
            return
        self._data.w = float(self.w_spin.value())
        self._data.h = float(self.h_spin.value())
        self.changed.emit()

    def _apply_pos(self):
        if not self._data:
            return
        self._data.x = float(self.x_spin.value())
        self._data.y = float(self.y_spin.value())
        self.changed.emit()

    def _pick_cover(self):
        if not self._data:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Cover Image", "", IMAGE_FILTER
        )
        if path:
            self._data.cover_path = path
            self._data.embedded_image = ""
            self.changed.emit()


# ─── Image Editor (draw · crop · resize) ──────────────────────────────────────

IMAGE_FILTER = "Images (*.jpg *.jpeg *.png *.webp *.bmp *.gif *.tif *.tiff *.svg)"


def _qimage_to_array(img: QImage):
    img = img.convertToFormat(QImage.Format_ARGB32)
    ptr = img.constBits()
    ptr.setsize(img.byteCount())
    return np.frombuffer(ptr, np.uint32).reshape(img.height(), img.bytesPerLine() // 4)[:, :img.width()].copy()


def flood_fill_mask(img: QImage, x: int, y: int, tolerance: int = 32):
    """Pixels connected to (x, y) whose colour is within `tolerance` of it → bool array."""
    arr = _qimage_to_array(img)
    h, w = arr.shape
    t = arr[y, x]
    chans = [(arr >> s) & 0xFF for s in (24, 16, 8, 0)]
    tc = [(int(t) >> s) & 0xFF for s in (24, 16, 8, 0)]
    diff = np.zeros(arr.shape, np.int32)
    for c, v in zip(chans, tc):
        np.maximum(diff, np.abs(c.astype(np.int32) - v), out=diff)
    same = diff <= tolerance
    mask = np.zeros((h, w), bool)
    stack = [(x, y)]
    while stack:
        sx, sy = stack.pop()
        if mask[sy, sx] or not same[sy, sx]:
            continue
        row = same[sy]
        left = row[:sx + 1][::-1]
        l = sx - (int(np.argmin(left)) if not left.all() else sx + 1) + 1
        right = row[sx:]
        r = sx + (int(np.argmin(right)) if not right.all() else len(right)) - 1
        mask[sy, l:r + 1] = True
        for ny in (sy - 1, sy + 1):
            if 0 <= ny < h:
                cand = same[ny, l:r + 1] & ~mask[ny, l:r + 1]
                if cand.any():
                    starts = np.flatnonzero(np.diff(np.concatenate(([0], cand.view(np.int8)))) == 1)
                    stack.extend((l + int(s), ny) for s in starts)
    return mask


class ImageEditCanvas(QWidget):
    """The drawing surface: brushes, shapes, fill, text, colour picker and crop, with zoom
    and undo / redo. A stroke is painted on its own layer and composited with the chosen
    opacity, so overlapping segments of one stroke never darken."""
    edited = pyqtSignal()
    color_picked = pyqtSignal(QColor)
    zoom_changed = pyqtSignal(float)

    PAD = 12
    FREEHAND = ("pen", "brush", "marker", "spray", "erase")
    SHAPES = ("line", "arrow", "rect", "ellipse")

    def __init__(self, img: QImage):
        super().__init__()
        self.image = img.convertToFormat(QImage.Format_ARGB32)
        self.tool = "pen"
        self.pen_color = QColor("#111111")
        self.fill_color = QColor("#ffffff")
        self.pen_width = 4
        self.opacity = 1.0
        self.fill_shapes = False
        self.tolerance = 32
        self.text_font = QFont("Georgia", 28)
        self.crop_rect = QRectF()          # in image coordinates
        self.zoom = 1.0
        self._undo, self._redo = [], []
        self._before = None                # image at stroke start
        self._layer = None                 # this stroke, at full strength
        self._start = self._last = None
        self._crop_origin = None
        self._hover = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self._resize_to_zoom()

    # ── coordinates / zoom ──
    def _view_rect(self):
        return QRectF(self.PAD, self.PAD, self.image.width() * self.zoom, self.image.height() * self.zoom), self.zoom

    def _to_img(self, p):
        x = (p.x() - self.PAD) / self.zoom
        y = (p.y() - self.PAD) / self.zoom
        return QPointF(min(max(x, 0.0), float(self.image.width())), min(max(y, 0.0), float(self.image.height())))

    def set_zoom(self, z):
        self.zoom = max(0.05, min(8.0, z))
        self._resize_to_zoom()
        self.zoom_changed.emit(self.zoom)

    def fit_zoom(self, avail_w, avail_h):
        iw, ih = max(1, self.image.width()), max(1, self.image.height())
        self.set_zoom(min((avail_w - 2 * self.PAD) / iw, (avail_h - 2 * self.PAD) / ih, 4.0))

    def _resize_to_zoom(self):
        self.setFixedSize(int(self.image.width() * self.zoom) + 2 * self.PAD,
                          int(self.image.height() * self.zoom) + 2 * self.PAD)
        self.update()

    # ── history ──
    def push_undo(self):
        self._undo.append(self.image.copy())
        del self._undo[:-40]
        self._redo.clear()

    def undo(self):
        if self._undo:
            self._redo.append(self.image)
            self._replace(self._undo.pop())

    def redo(self):
        if self._redo:
            self._undo.append(self.image)
            self._replace(self._redo.pop())

    def _replace(self, img):
        resized = img.size() != self.image.size()
        self.image = img
        self.crop_rect = QRectF()
        if resized:
            self._resize_to_zoom()
        self.update(); self.edited.emit()

    def set_image(self, img: QImage, keep_history=True):
        if keep_history:
            self.push_undo()
        self._replace(img.convertToFormat(QImage.Format_ARGB32))

    # ── painting the widget ──
    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#2b2b2b"))
        vr, s = self._view_rect()
        tile = 10
        p.save(); p.setClipRect(vr.intersected(QRectF(e.rect())))
        yy = int(vr.top())
        while yy < vr.bottom():
            xx = int(vr.left())
            while xx < vr.right():
                odd = ((xx - int(vr.left())) // tile + (yy - int(vr.top())) // tile) % 2
                p.fillRect(xx, yy, tile, tile, QColor("#cfcfcf" if odd else "#f2f2f2"))
                xx += tile
            yy += tile
        p.restore()
        p.setRenderHint(QPainter.SmoothPixmapTransform, s < 1.0)
        p.drawImage(vr, self.image)
        if not self.crop_rect.isNull():
            cr = QRectF(vr.left() + self.crop_rect.left() * s, vr.top() + self.crop_rect.top() * s,
                        self.crop_rect.width() * s, self.crop_rect.height() * s)
            shade = QPainterPath(); shade.addRect(vr)
            hole = QPainterPath(); hole.addRect(cr)
            p.fillPath(shade.subtracted(hole), QColor(0, 0, 0, 120))
            p.setPen(QPen(QColor("#2979FF"), 1.5, Qt.DashLine))
            p.drawRect(cr)
        if self._hover is not None and self.tool in self.FREEHAND:   # brush outline
            r = self.pen_width * (3 if self.tool == "erase" else 1) * s / 2.0
            c = QPointF(vr.left() + self._hover.x() * s, vr.top() + self._hover.y() * s)
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(QPen(QColor(0, 0, 0, 160), 1)); p.setBrush(Qt.NoBrush)
            p.drawEllipse(c, r + 1, r + 1)
            p.setPen(QPen(QColor(255, 255, 255, 200), 1))
            p.drawEllipse(c, r, r)

    # ── mouse ──
    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        ip = self._to_img(e.pos())
        xi = min(self.image.width() - 1, int(ip.x())); yi = min(self.image.height() - 1, int(ip.y()))
        if self.tool == "crop":
            self._crop_origin = ip
            self.crop_rect = QRectF(ip, ip)
        elif self.tool == "picker":
            c = QColor(self.image.pixel(xi, yi))
            self.color_picked.emit(c)
        elif self.tool == "fill":
            self._fill(xi, yi)
        elif self.tool == "text":
            self._place_text(ip)
        else:
            self.push_undo()
            self._before = self.image.copy()
            self._layer = QImage(self.image.size(), QImage.Format_ARGB32_Premultiplied)
            self._layer.fill(Qt.transparent)
            self._start = self._last = ip
            if self.tool in self.FREEHAND:
                self._freehand(ip, ip)
            self._compose()
        self.update()

    def mouseMoveEvent(self, e):
        ip = self._to_img(e.pos())
        self._hover = ip
        if not (e.buttons() & Qt.LeftButton):
            if self.tool in self.FREEHAND:
                self.update()
            return
        if self.tool == "crop" and self._crop_origin is not None:
            self.crop_rect = QRectF(self._crop_origin, ip).normalized()
        elif self._layer is not None and self.tool in self.FREEHAND:
            self._freehand(self._last, ip)
            self._last = ip
            self._compose()
        elif self._layer is not None and self.tool in self.SHAPES:
            self._layer.fill(Qt.transparent)
            self._shape(self._start, ip, bool(e.modifiers() & Qt.ShiftModifier))
            self._compose()
        self.update()

    def mouseReleaseEvent(self, e):
        if self._layer is not None:
            self.edited.emit()
        self._layer = self._before = None
        self._start = self._last = self._crop_origin = None

    def leaveEvent(self, e):
        self._hover = None
        self.update()

    # ── stroke rendering ──
    def _layer_painter(self):
        p = QPainter(self._layer)
        p.setRenderHint(QPainter.Antialiasing)
        return p

    def _freehand(self, a, b):
        p = self._layer_painter()
        c = QColor(self.pen_color) if self.tool != "erase" else QColor("black")
        w = self.pen_width
        if self.tool == "pen" or self.tool == "erase":
            p.setPen(QPen(c, w * (3 if self.tool == "erase" else 1), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawLine(a, b)
        elif self.tool == "marker":
            p.setPen(QPen(c, w * 3, Qt.SolidLine, Qt.FlatCap, Qt.RoundJoin))
            p.drawLine(a, b)
        elif self.tool == "brush":                    # soft round dabs
            r = max(1.5, w * 1.5)
            dist = math.hypot(b.x() - a.x(), b.y() - a.y())
            steps = max(1, int(dist / max(1.0, r * 0.25)))
            p.setPen(Qt.NoPen)
            for i in range(steps + 1):
                t = i / steps
                pt = QPointF(a.x() + (b.x() - a.x()) * t, a.y() + (b.y() - a.y()) * t)
                g = QRadialGradient(pt, r)
                c0 = QColor(c); c0.setAlpha(70)
                c1 = QColor(c); c1.setAlpha(0)
                g.setColorAt(0, c0); g.setColorAt(1, c1)
                p.setBrush(QBrush(g))
                p.drawEllipse(pt, r, r)
        elif self.tool == "spray":
            r = max(4.0, w * 3.0)
            p.setPen(Qt.NoPen); p.setBrush(c)
            rng = random.Random()
            for _ in range(int(r * 1.5)):
                ang, dd = rng.uniform(0, 2 * math.pi), r * math.sqrt(rng.random())
                p.drawEllipse(QPointF(b.x() + dd * math.cos(ang), b.y() + dd * math.sin(ang)), 0.8, 0.8)
        p.end()

    def _shape(self, a, b, constrain):
        p = self._layer_painter()
        p.setPen(QPen(self.pen_color, self.pen_width, Qt.SolidLine, Qt.RoundCap, Qt.MiterJoin))
        p.setBrush(self.fill_color if self.fill_shapes else Qt.NoBrush)
        dx, dy = b.x() - a.x(), b.y() - a.y()
        if self.tool in ("line", "arrow"):
            if constrain:                              # snap to 45°
                ang = round(math.atan2(dy, dx) / (math.pi / 4)) * (math.pi / 4)
                ln = math.hypot(dx, dy)
                b = QPointF(a.x() + ln * math.cos(ang), a.y() + ln * math.sin(ang))
            p.drawLine(a, b)
            if self.tool == "arrow" and (a - b).manhattanLength() > 2:
                ang = math.atan2(b.y() - a.y(), b.x() - a.x())
                head = max(10.0, self.pen_width * 4.0)
                pts = [b, QPointF(b.x() - head * math.cos(ang - 0.45), b.y() - head * math.sin(ang - 0.45)),
                       QPointF(b.x() - head * math.cos(ang + 0.45), b.y() - head * math.sin(ang + 0.45))]
                path = QPainterPath(pts[0]); path.lineTo(pts[1]); path.lineTo(pts[2]); path.closeSubpath()
                p.setBrush(self.pen_color)
                p.drawPath(path)
        else:
            if constrain:                              # square / circle
                side = max(abs(dx), abs(dy))
                b = QPointF(a.x() + math.copysign(side, dx or 1), a.y() + math.copysign(side, dy or 1))
            r = QRectF(a, b).normalized()
            if self.tool == "rect":
                p.drawRect(r)
            else:
                p.drawEllipse(r)
        p.end()

    def _compose(self):
        img = self._before.copy()
        p = QPainter(img)
        p.setOpacity(self.opacity * (0.4 if self.tool == "marker" else 1.0))
        if self.tool == "erase":
            p.setCompositionMode(QPainter.CompositionMode_DestinationOut)
        elif self.tool == "marker":
            p.setCompositionMode(QPainter.CompositionMode_Multiply)
        p.drawImage(0, 0, self._layer)
        p.end()
        self.image = img

    def _fill(self, x, y):
        if _load_numpy() is None:
            QMessageBox.information(self, "Fill", "The fill tool needs numpy:  pip install numpy")
            return
        mask = flood_fill_mask(self.image, x, y, self.tolerance)
        c = self.pen_color
        argb = np.uint32((255 << 24) | (c.red() << 16) | (c.green() << 8) | c.blue())
        over = np.zeros(mask.shape, np.uint32)
        over[mask] = argb
        h, w = mask.shape
        layer = QImage(over.data, w, h, w * 4, QImage.Format_ARGB32).copy()
        self.push_undo()
        img = self.image.copy()
        p = QPainter(img); p.setOpacity(self.opacity); p.drawImage(0, 0, layer); p.end()
        self.image = img
        self.edited.emit()

    def _place_text(self, at):
        text, ok = QInputDialog.getMultiLineText(self, "Text", "Text:")
        if not ok or not text.strip():
            return
        self.push_undo()
        img = self.image.copy()
        p = QPainter(img)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setOpacity(self.opacity)
        p.setFont(self.text_font)
        p.setPen(self.pen_color)
        fm = QFontMetricsF(self.text_font)
        y = at.y() + fm.ascent()
        for line in text.splitlines():
            p.drawText(QPointF(at.x(), y), line)
            y += fm.lineSpacing()
        p.end()
        self.image = img
        self.edited.emit()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and self.tool == "crop":
            getattr(self.window(), "_apply_crop", lambda: None)()
            return
        super().keyPressEvent(e)


class ImageEditorDialog(QDialog):
    """Image editor / drawing canvas. result_image() returns the edited QImage;
    `source_path` / `modified` tell whether an opened file came back untouched."""

    TOOLS = (("pen", "✏", "Pen", "P"), ("brush", "🖌", "Soft brush", "B"), ("marker", "🖍", "Highlighter", "M"),
             ("spray", "💨", "Spray", "A"), ("erase", "⌫", "Eraser", "E"), ("line", "╱", "Line", "L"),
             ("arrow", "➚", "Arrow", "W"), ("rect", "▭", "Rectangle", "R"), ("ellipse", "◯", "Ellipse", "O"),
             ("fill", "🪣", "Fill", "G"), ("text", "T", "Text", "T"), ("picker", "💧", "Colour picker", "I"),
             ("crop", "⬚", "Crop", "C"))
    SWATCHES = ("#111111", "#ffffff", "#8b0000", "#e53935", "#fb8c00", "#fdd835", "#43a047",
                "#00897b", "#1e88e5", "#3949ab", "#8e24aa", "#6d4c41", "#9e9e9e", "#f5efe0")

    def __init__(self, img: QImage = None, parent=None, title="Image", source_path=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(1180, 800)
        self.source_path = source_path
        self.modified = False
        if img is None or img.isNull():
            img = self.blank_image(1200, 900)
        self.canvas = ImageEditCanvas(img)
        self.canvas.edited.connect(self._on_edited)
        self.canvas.color_picked.connect(self._on_picked)
        self.canvas.zoom_changed.connect(lambda z: self.zoom_lbl.setText(f"{z * 100:.0f}%"))
        self._fit_mode = True

        v = QVBoxLayout(self)

        # actions row
        acts = QHBoxLayout()
        def act(label, tip, fn, key=None):
            b = QPushButton(label); b.setToolTip(tip + (f"  ({key})" if key else ""))
            b.clicked.connect(fn)
            if key:
                b.setShortcut(QKeySequence(key))
            acts.addWidget(b); return b
        act("📂 Open…", "Open an image (replaces the canvas)", self._replace_from_file, "Ctrl+O")
        act("⊕ Place…", "Draw another image onto the canvas", self._place_image)
        act("📋 Paste", "Paste an image from the clipboard", self._paste, "Ctrl+V")
        act("▢ New…", "New blank canvas", self._new_blank, "Ctrl+N")
        acts.addSpacing(10)
        act("↶", "Undo", self.canvas.undo, "Ctrl+Z")
        act("↷", "Redo", self.canvas.redo, "Ctrl+Y")
        acts.addSpacing(10)
        act("⟲", "Rotate left", lambda: self._transform(QTransform().rotate(-90)))
        act("⟳", "Rotate right", lambda: self._transform(QTransform().rotate(90)))
        act("⇋", "Flip horizontal", lambda: self.canvas.set_image(self.canvas.image.mirrored(True, False)))
        act("⇵", "Flip vertical", lambda: self.canvas.set_image(self.canvas.image.mirrored(False, True)))
        act("✓ Crop", "Apply the crop selection", self._apply_crop, "Ctrl+Return")
        act("🧽 Clear", "Fill the canvas with the fill colour", self._clear)
        acts.addStretch()
        v.addLayout(acts)

        # options row
        opts = QHBoxLayout()
        self.color_btn = QPushButton(); self.color_btn.setFixedSize(30, 26); self.color_btn.setToolTip("Colour")
        self.color_btn.clicked.connect(self._pick_color)
        self.fill_btn = QPushButton(); self.fill_btn.setFixedSize(30, 26); self.fill_btn.setToolTip("Fill colour (shapes, Clear)")
        self.fill_btn.clicked.connect(self._pick_fill)
        swap = QPushButton("⇄"); swap.setFixedWidth(28); swap.setToolTip("Swap colours  (X)")
        swap.setShortcut(QKeySequence("X")); swap.clicked.connect(self._swap_colors)
        opts.addWidget(self.color_btn); opts.addWidget(swap); opts.addWidget(self.fill_btn)
        for hexc in self.SWATCHES:
            s = QPushButton(); s.setFixedSize(18, 18); s.setToolTip(hexc)
            s.setStyleSheet(f"background:{hexc};border:1px solid #666;border-radius:2px;padding:0;")
            s.clicked.connect(lambda _=False, c=hexc: self._set_color(QColor(c)))
            opts.addWidget(s)
        opts.addSpacing(10)
        self.width_spin = QSpinBox(); self.width_spin.setRange(1, 200); self.width_spin.setValue(4)
        self.width_spin.setSuffix(" px"); self.width_spin.setToolTip("Size  ([ / ])")
        self.width_spin.valueChanged.connect(lambda val: (setattr(self.canvas, "pen_width", val), self.canvas.update()))
        opts.addWidget(QLabel("Size:")); opts.addWidget(self.width_spin)
        self.op_spin = QSpinBox(); self.op_spin.setRange(5, 100); self.op_spin.setValue(100); self.op_spin.setSuffix(" %")
        self.op_spin.valueChanged.connect(lambda val: setattr(self.canvas, "opacity", val / 100.0))
        opts.addWidget(QLabel("Opacity:")); opts.addWidget(self.op_spin)
        self.fill_cb = QCheckBox("Filled shapes")
        self.fill_cb.toggled.connect(lambda on: setattr(self.canvas, "fill_shapes", on))
        opts.addWidget(self.fill_cb)
        self.tol_spin = QSpinBox(); self.tol_spin.setRange(0, 255); self.tol_spin.setValue(32)
        self.tol_spin.setToolTip("Fill tolerance")
        self.tol_spin.valueChanged.connect(lambda val: setattr(self.canvas, "tolerance", val))
        opts.addWidget(QLabel("Tol:")); opts.addWidget(self.tol_spin)
        self.font_btn = QFontComboBox(); self.font_btn.setCurrentFont(self.canvas.text_font)
        self.font_btn.setMaximumWidth(150)
        self.font_btn.currentFontChanged.connect(self._font_changed)
        self.font_size = QSpinBox(); self.font_size.setRange(6, 400); self.font_size.setValue(28); self.font_size.setSuffix(" pt")
        self.font_size.valueChanged.connect(lambda _: self._font_changed(self.font_btn.currentFont()))
        opts.addWidget(self.font_btn); opts.addWidget(self.font_size)
        opts.addStretch()
        v.addLayout(opts)

        body = QHBoxLayout()
        # tool palette
        pal = QGridLayout(); pal.setSpacing(3)
        self.tool_btns = {}
        group = QButtonGroup(self); group.setExclusive(True)
        for i, (key, icon, tip, sc) in enumerate(self.TOOLS):
            b = QToolButton(); b.setText(icon); b.setCheckable(True); b.setFixedSize(38, 34)
            b.setToolTip(f"{tip}  ({sc})"); b.setShortcut(QKeySequence(sc))
            b.setStyleSheet("QToolButton{font-size:16px;background:#383838;color:#ddd;border:1px solid #555;border-radius:3px}"
                            "QToolButton:checked{background:#1565C0;color:white;border-color:#2979FF}")
            b.clicked.connect(lambda _=False, k=key: self._set_tool(k))
            group.addButton(b)
            pal.addWidget(b, i // 2, i % 2)
            self.tool_btns[key] = b
        pal_w = QWidget(); pal_v = QVBoxLayout(pal_w); pal_v.setContentsMargins(0, 0, 0, 0)
        pal_v.addLayout(pal); pal_v.addStretch()
        body.addWidget(pal_w)

        self.scroll = QScrollArea()
        self.scroll.setWidget(self.canvas)
        self.scroll.setAlignment(Qt.AlignCenter)
        self.scroll.setStyleSheet("QScrollArea{background:#2b2b2b;border:none}")
        body.addWidget(self.scroll, 1)
        v.addLayout(body, 1)

        # bottom row: size + zoom
        bottom = QHBoxLayout()
        self.w_spin = QSpinBox(); self.w_spin.setRange(8, 12000); self.w_spin.setSuffix(" px")
        self.h_spin = QSpinBox(); self.h_spin.setRange(8, 12000); self.h_spin.setSuffix(" px")
        self.keep_ar = QCheckBox("Keep ratio"); self.keep_ar.setChecked(True)
        self.w_spin.valueChanged.connect(self._w_changed)
        self.h_spin.valueChanged.connect(self._h_changed)
        bottom.addWidget(QLabel("Size:")); bottom.addWidget(self.w_spin)
        bottom.addWidget(QLabel("×")); bottom.addWidget(self.h_spin); bottom.addWidget(self.keep_ar)
        resize_btn = QPushButton("Resize"); resize_btn.clicked.connect(self._apply_resize)
        bottom.addWidget(resize_btn)
        bottom.addStretch()
        for label, fn in (("−", lambda: self._zoom(1 / 1.25)), ("Fit", self._fit), ("100%", lambda: self._zoom_to(1.0)),
                          ("+", lambda: self._zoom(1.25))):
            b = QPushButton(label); b.setFixedWidth(46); b.clicked.connect(fn); bottom.addWidget(b)
        self.zoom_lbl = QLabel("100%"); self.zoom_lbl.setMinimumWidth(48)
        bottom.addWidget(self.zoom_lbl)
        bottom.addSpacing(12)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        bottom.addWidget(bb)
        v.addLayout(bottom)

        for key, delta in (("[", -1), ("]", 1)):
            b = QAction(self); b.setShortcut(QKeySequence(key))
            b.triggered.connect(lambda _=False, d=delta: self.width_spin.setValue(
                max(1, self.width_spin.value() + d * max(1, self.width_spin.value() // 6))))
            self.addAction(b)

        self._set_tool("pen")
        self._update_color_btns()
        self._sync_size_spins()
        self._font_changed(self.font_btn.currentFont())

    @staticmethod
    def blank_image(w, h, color="white"):
        img = QImage(w, h, QImage.Format_ARGB32)
        img.fill(QColor(color) if color != "transparent" else Qt.transparent)
        return img

    def result_image(self) -> QImage:
        return self.canvas.image

    # ── zoom ──
    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, self._fit)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._fit_mode:
            self._fit()

    def _fit(self):
        self._fit_mode = True
        vp = self.scroll.viewport().size()
        self.canvas.fit_zoom(vp.width(), vp.height())

    def _zoom(self, f):
        self._zoom_to(self.canvas.zoom * f)

    def _zoom_to(self, z):
        self._fit_mode = False
        self.canvas.set_zoom(z)

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            self._zoom(1.15 if e.angleDelta().y() > 0 else 1 / 1.15)
            e.accept()
        else:
            super().wheelEvent(e)

    # ── tools / colours ──
    def _set_tool(self, key):
        self.canvas.tool = key
        self.tool_btns[key].setChecked(True)
        if key != "crop":
            self.canvas.crop_rect = QRectF()
        self.canvas.setCursor(Qt.CrossCursor if key not in ("text",) else Qt.IBeamCursor)
        self.canvas.update()

    def _set_color(self, c):
        self.canvas.pen_color = QColor(c)
        self._update_color_btns()

    def _on_picked(self, c):
        self._set_color(c)
        self._set_tool("pen")

    def _pick_color(self):
        c = QColorDialog.getColor(self.canvas.pen_color, self, "Colour", QColorDialog.ShowAlphaChannel)
        if c.isValid():
            self._set_color(c)

    def _pick_fill(self):
        c = QColorDialog.getColor(self.canvas.fill_color, self, "Fill Colour", QColorDialog.ShowAlphaChannel)
        if c.isValid():
            self.canvas.fill_color = c
            self._update_color_btns()

    def _swap_colors(self):
        self.canvas.pen_color, self.canvas.fill_color = self.canvas.fill_color, self.canvas.pen_color
        self._update_color_btns()

    def _update_color_btns(self):
        for b, c in ((self.color_btn, self.canvas.pen_color), (self.fill_btn, self.canvas.fill_color)):
            b.setStyleSheet(f"background:{c.name()};border:2px solid #888;border-radius:3px;")

    def _font_changed(self, f):
        f = QFont(f)
        f.setPointSize(self.font_size.value())
        self.canvas.text_font = f

    def _on_edited(self):
        self.modified = True
        self._sync_size_spins()

    # ── whole-image operations ──
    def _apply_crop(self):
        r = self.canvas.crop_rect.toAlignedRect()
        if r.width() < 4 or r.height() < 4:
            return
        self.canvas.set_image(self.canvas.image.copy(r))
        if self._fit_mode:
            self._fit()

    def _transform(self, t):
        self.canvas.set_image(self.canvas.image.transformed(t, Qt.SmoothTransformation))
        if self._fit_mode:
            self._fit()

    def _clear(self):
        self.canvas.set_image(self.blank_image(self.canvas.image.width(), self.canvas.image.height(),
                                               self.canvas.fill_color.name() if self.canvas.fill_color.alpha() else "transparent"))

    def _new_blank(self):
        d = QDialog(self); d.setWindowTitle("New Canvas")
        f = QFormLayout(d)
        ws = QSpinBox(); ws.setRange(8, 12000); ws.setValue(1200); ws.setSuffix(" px")
        hs = QSpinBox(); hs.setRange(8, 12000); hs.setValue(900); hs.setSuffix(" px")
        bg = QComboBox()
        for label, val in (("White", "white"), ("Fill colour", "fill"), ("Transparent", "transparent")):
            bg.addItem(label, val)
        f.addRow("Width:", ws); f.addRow("Height:", hs); f.addRow("Background:", bg)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept); bb.rejected.connect(d.reject); f.addRow(bb)
        if d.exec_() == QDialog.Accepted:
            col = self.canvas.fill_color.name() if bg.currentData() == "fill" else bg.currentData()
            self.canvas.set_image(self.blank_image(ws.value(), hs.value(), col))
            self.source_path = ""
            self._fit()

    def _sync_size_spins(self):
        for sp, val in ((self.w_spin, self.canvas.image.width()), (self.h_spin, self.canvas.image.height())):
            sp.blockSignals(True); sp.setValue(val); sp.blockSignals(False)

    def _ratio(self):
        return self.canvas.image.width() / max(1.0, float(self.canvas.image.height()))

    def _w_changed(self, val):
        if self.keep_ar.isChecked():
            self.h_spin.blockSignals(True)
            self.h_spin.setValue(max(8, int(round(val / self._ratio()))))
            self.h_spin.blockSignals(False)

    def _h_changed(self, val):
        if self.keep_ar.isChecked():
            self.w_spin.blockSignals(True)
            self.w_spin.setValue(max(8, int(round(val * self._ratio()))))
            self.w_spin.blockSignals(False)

    def _apply_resize(self):
        w, h = self.w_spin.value(), self.h_spin.value()
        if (w, h) != (self.canvas.image.width(), self.canvas.image.height()):
            self.canvas.set_image(self.canvas.image.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
            if self._fit_mode:
                self._fit()

    # ── sources ──
    def _replace_from_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Image", "", IMAGE_FILTER)
        if path:
            img = read_image(path, 0)
            if not img.isNull():
                self.canvas.set_image(img)
                self.source_path = path
                self.modified = False
                self._fit()

    def _stamp(self, img: QImage):
        """Draw `img` centred onto the canvas, scaled to fit within 80 % of it."""
        base = self.canvas.image
        s = min(1.0, base.width() * 0.8 / max(1, img.width()), base.height() * 0.8 / max(1, img.height()))
        w, h = img.width() * s, img.height() * s
        out = base.copy()
        p = QPainter(out); p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(QRectF((base.width() - w) / 2, (base.height() - h) / 2, w, h), img)
        p.end()
        self.canvas.set_image(out)

    def _place_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Place Image", "", IMAGE_FILTER)
        if path:
            img = read_image(path, 0)
            if not img.isNull():
                self._stamp(img)

    def _paste(self):
        img = QApplication.clipboard().image()
        if not img.isNull():
            self._stamp(img)


class ImageSourceDialog(QDialog):
    """Insert Image: pick a file or start a blank drawing canvas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Insert Image")
        self.choice = None
        self.path = ""
        v = QVBoxLayout(self)
        file_btn = QPushButton("📂  From File…")
        draw_btn = QPushButton("✏  Drawing Canvas")
        for b in (file_btn, draw_btn):
            b.setMinimumHeight(44)
            v.addWidget(b)
        self.edit_cb = QCheckBox("Crop / resize before inserting")
        v.addWidget(self.edit_cb)
        file_btn.clicked.connect(self._from_file)
        draw_btn.clicked.connect(self._draw)
        bb = QDialogButtonBox(QDialogButtonBox.Cancel)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def _from_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose Image", "", IMAGE_FILTER)
        if path:
            self.choice, self.path = "file", path
            self.accept()

    def _draw(self):
        self.choice = "draw"
        self.accept()


# ─── Extract Text Dialog ───────────────────────────────────────────────────────

class ExtractTextDialog(QDialog):
    """Shows a document's full text; selected passages are sent to a card field."""
    insert = pyqtSignal(str, str)          # target, text

    TARGETS = (("append",   "＋ Add to Body"),
               ("body",     "Replace Body"),
               ("title",    "→ Headline"),
               ("abstract", "→ Standfirst"),
               ("strapline", "→ Kicker"),
               ("new_text", "＋ New Text Box"))

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Extract Text — {Path(path).name}")
        self.resize(760, 720)
        v = QVBoxLayout(self)

        find_row = QHBoxLayout()
        self.find_e = QLineEdit(); self.find_e.setPlaceholderText("Find")
        self.find_e.returnPressed.connect(self._find_next)
        find_btn = QPushButton("Next"); find_btn.clicked.connect(self._find_next)
        self.info_lbl = QLabel()
        find_row.addWidget(self.find_e, 1); find_row.addWidget(find_btn); find_row.addWidget(self.info_lbl)
        v.addLayout(find_row)

        paras = document_paragraphs(path)
        self.view = QTextEdit()
        self.view.setReadOnly(True)
        self.view.setPlainText("\n\n".join(paras))
        self.view.setStyleSheet("font-family:Georgia;font-size:12px;")
        v.addWidget(self.view, 1)
        self.info_lbl.setText(f"{len(paras)} paragraphs")

        btns = QHBoxLayout()
        for key, label in self.TARGETS:
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, k=key: self._send(k))
            btns.addWidget(b)
        v.addLayout(btns)

        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def _find_next(self):
        term = self.find_e.text()
        if term and not self.view.find(term):
            cur = self.view.textCursor(); cur.movePosition(cur.Start)
            self.view.setTextCursor(cur)
            self.view.find(term)

    def _send(self, target):
        text = self.view.textCursor().selectedText().replace("\u2029", "\n").strip()
        if not text:
            self.info_lbl.setText("Select text first")
            return
        if target in ("title", "abstract", "strapline"):
            text = re.sub(r"\s+", " ", text)
        else:
            text = re.sub(r"\n\s*\n+", "\n", text)       # one line per paragraph
        self.insert.emit(target, text)
        self.info_lbl.setText("Inserted")


# ─── Link Previews (favicon · title · description · image · embed) ────────────

_UA = "Mozilla/5.0 (FolioPress link preview)"


class _HeadParser(HTMLParser):
    """Collects <title>, <meta> and <link rel=icon> from a page head."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta, self.icons, self.title, self._in_title = {}, [], "", False

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key and a.get("content") and key not in self.meta:
                self.meta[key] = a["content"].strip()
        elif tag == "link" and "icon" in a.get("rel", "").lower() and a.get("href"):
            size = 0
            m = re.match(r"(\d+)x\d+", a.get("sizes", ""))
            if m:
                size = int(m.group(1))
            self.icons.append((size, a["href"]))
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def _http_get(url, limit=1_500_000, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(limit), r.headers.get_content_type() or "", r.geturl()


def _data_uri(raw: bytes, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


def _image_data_uri(raw: bytes, max_side: int) -> str:
    """Decode with Qt, shrink, re-encode — rejects anything that isn't really an image."""
    img = QImage()
    if not raw or not img.loadFromData(raw) or img.isNull():
        return ""
    if max(img.width(), img.height()) > max_side:
        img = img.scaled(max_side, max_side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    ba = QByteArray(); buf = QBuffer(ba); buf.open(QIODevice.WriteOnly)
    fmt = "PNG" if img.hasAlphaChannel() or max_side <= 128 else "JPG"
    img.save(buf, fmt, 85); buf.close()
    return _data_uri(bytes(ba), "image/png" if fmt == "PNG" else "image/jpeg")


def link_embed_url(url: str, meta: dict = None) -> str:
    """Embeddable player URL for known providers, or the page's own declared player."""
    u = urllib.parse.urlparse(url)
    host = u.netloc.lower().removeprefix("www.").removeprefix("m.")
    q = urllib.parse.parse_qs(u.query)
    if host in ("youtube.com", "music.youtube.com") and q.get("v"):
        return f"https://www.youtube-nocookie.com/embed/{q['v'][0]}"
    if host == "youtube.com" and u.path.startswith(("/shorts/", "/embed/")):
        return f"https://www.youtube-nocookie.com/embed/{u.path.split('/')[2]}"
    if host == "youtu.be" and u.path.strip("/"):
        return f"https://www.youtube-nocookie.com/embed/{u.path.strip('/').split('/')[0]}"
    if host == "vimeo.com" and re.match(r"/\d+", u.path):
        return f"https://player.vimeo.com/video/{u.path.strip('/').split('/')[0]}"
    if host == "open.spotify.com" and re.match(r"/(track|album|playlist|episode|show|artist)/", u.path):
        return "https://open.spotify.com/embed" + u.path
    if host == "soundcloud.com" and u.path.count("/") >= 2:
        return "https://w.soundcloud.com/player/?url=" + urllib.parse.quote(url, safe="") + "&visual=true"
    meta = meta or {}
    player = meta.get("twitter:player") or meta.get("og:video:secure_url") or ""
    if player.startswith("https://") and not re.search(r"\.(mp4|webm|mov|m3u8)(\?|$)", player):
        return player
    return ""


def fetch_link_preview(url: str) -> dict:
    """{icon, page_title, page_desc, image, embed} for a URL. Raises on network failure."""
    out = {"icon": "", "page_title": "", "page_desc": "", "image": "", "embed": ""}
    raw, ctype, final = _http_get(url)
    parser = _HeadParser()
    if "html" in ctype or not ctype:
        text = raw.decode("utf-8", errors="replace")
        head = text.split("</head>", 1)[0] if "</head>" in text else text[:300_000]
        parser.feed(head)
    m = parser.meta
    out["page_title"] = html.unescape(m.get("og:title") or m.get("twitter:title") or parser.title).strip()[:200]
    out["page_desc"]  = html.unescape(m.get("og:description") or m.get("twitter:description")
                                      or m.get("description") or "").strip()[:400]
    out["embed"] = link_embed_url(final, m) or link_embed_url(url, m)

    img_url = m.get("og:image:secure_url") or m.get("og:image") or m.get("twitter:image") or ""
    if img_url:
        try:
            out["image"] = _image_data_uri(_http_get(urllib.parse.urljoin(final, img_url), 4_000_000)[0], 720)
        except Exception:
            pass

    icon_urls = [urllib.parse.urljoin(final, h) for _, h in sorted(parser.icons, key=lambda t: -t[0])]
    icon_urls.append(urllib.parse.urljoin(final, "/favicon.ico"))
    for iu in icon_urls[:4]:
        try:
            if iu.lower().split("?")[0].endswith(".svg"):
                svg, _, _ = _http_get(iu, 200_000)
                if b"<svg" in svg[:2000].lower():
                    out["icon"] = _data_uri(svg, "image/svg+xml")
                    break
                continue
            out["icon"] = _image_data_uri(_http_get(iu, 400_000)[0], 64)
            if out["icon"]:
                break
        except Exception:
            continue
    return out


class DocImportWorker(QThread):
    """Reads headline / kicker / abstract / cover from documents off the UI thread."""
    item_done = pyqtSignal(str, dict, str)     # item id, fields, error

    FIELDS = ("file_path", "title", "strapline", "abstract", "notes", "embedded_image")

    def __init__(self, jobs):
        super().__init__()
        self.jobs = jobs                        # [(item id, path)]

    def run(self):
        for item_id, path in self.jobs:
            tmp = PortfolioItem("article")
            try:
                fill_article_from_document(tmp, path)
                self.item_done.emit(item_id, {k: getattr(tmp, k) for k in self.FIELDS}, "")
            except Exception as e:
                self.item_done.emit(item_id, {}, str(e)[:160])


class LinkPreviewWorker(QObject):
    """Fetches previews on a daemon thread (a slow site can never hold up closing the
    dialog or the app); results arrive on the UI thread through queued signals."""
    row_done = pyqtSignal(str, dict, str)      # url, preview, error
    finished = pyqtSignal()

    def __init__(self, urls, parent=None):
        super().__init__(parent)
        self.urls = urls
        self.cancelled = False
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def isRunning(self):
        return self._thread is not None and self._thread.is_alive()

    def cancel(self):
        self.cancelled = True

    def _run(self):
        try:
            for url in self.urls:
                if self.cancelled:
                    return
                try:
                    res, err = fetch_link_preview(url), ""
                except Exception as e:
                    res, err = {}, str(e)[:120]
                if self.cancelled:
                    return
                self.row_done.emit(url, res, err)
            self.finished.emit()
        except RuntimeError:
            pass                                # dialog (our parent) already deleted


def link_domain(url: str) -> str:
    return urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")


def data_uri_icon(uri: str) -> QIcon:
    if not uri or not uri.startswith("data:image/") or "svg" in uri[:30]:
        return QIcon()
    img = QImage()
    img.loadFromData(base64.b64decode(uri.split(",", 1)[1]))
    return QIcon(QPixmap.fromImage(img)) if not img.isNull() else QIcon()


# ─── Link Tree Dialog ──────────────────────────────────────────────────────────

class AboutDialog(QDialog):
    """Help ▸ About — a small masthead with the developer, links and the support button."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About FolioPress")
        self.setFixedWidth(440)
        self.setStyleSheet("QDialog{background:#faf6eb;} QLabel{color:#141414;}")
        v = QVBoxLayout(self)
        v.setContentsMargins(28, 24, 28, 20)
        v.setSpacing(6)

        icon = app_icon()
        if not icon.isNull():
            logo = QLabel()
            logo.setPixmap(icon.pixmap(72, 72))
            logo.setAlignment(Qt.AlignCenter)
            v.addWidget(logo)

        title = QLabel("FolioPress")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-family:Georgia;font-size:30px;font-weight:bold;")
        v.addWidget(title)

        meta = QLabel(f"VERSION {APP_VERSION}  ·  ALGORITHM BASED PORTFOLIO BUILDER")
        meta.setAlignment(Qt.AlignCenter)
        meta.setStyleSheet("font-size:9px;letter-spacing:1px;color:#686256;"
                           "border-top:3px double #141414;border-bottom:1px solid #141414;"
                           "padding:4px 0;")
        v.addWidget(meta)
        v.addSpacing(8)

        blurb = QLabel(
            "Turn the files on your drive into a typeset, portfolio website - algorithmically "
            "arranged on a canvas, exported as plain HTML you can host anywhere.")
        blurb.setWordWrap(True)
        blurb.setAlignment(Qt.AlignCenter)
        blurb.setStyleSheet("font-family:Georgia;font-size:13px;font-style:italic;")
        v.addWidget(blurb)
        v.addSpacing(10)

        byline = QLabel(f"<span style='font-size:9px;letter-spacing:1px;color:#686256;'>"
                        f"MADE WITH <span style='color:#8b0000;'>♥</span> BY</span><br>"
                        f"<span style='font-family:Georgia;font-size:17px;font-weight:bold;'>"
                        f"{html.escape(DEV_NAME)}</span>")
        byline.setAlignment(Qt.AlignCenter)
        v.addWidget(byline)

        links = [(f"mailto:{DEV_EMAIL}", DEV_EMAIL)] if DEV_EMAIL else []
        links += [(u, l) for u, l in ((DEV_GITHUB, "GitHub"), (DEV_WEBSITE, "Website")) if u]
        if links:
            row = QLabel("  ·  ".join(
                f'<a style="color:#8b0000;" href="{html.escape(u)}">{html.escape(l)}</a>'
                for u, l in links))
            row.setAlignment(Qt.AlignCenter)
            row.setOpenExternalLinks(True)
            v.addWidget(row)
        v.addSpacing(14)

        if SUPPORT_URL:
            pitch = QLabel("FolioPress is free and made by one person & her insane love for "
                           "partitioning algorithms, and web showcases. If it helped you, you can "
                           "chip in towards its upkeep - any amount helps.")
            pitch.setWordWrap(True)
            pitch.setAlignment(Qt.AlignCenter)
            pitch.setStyleSheet("font-size:11px;color:#686256;")
            v.addWidget(pitch)
            support = QPushButton("♥  Support FolioPress")
            support.setCursor(Qt.PointingHandCursor)
            support.setStyleSheet(
                "QPushButton{background:#8b0000;color:white;font-weight:bold;"
                "padding:8px 18px;border:none;border-radius:3px;}"
                "QPushButton:hover{background:#a31515;}")
            support.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(SUPPORT_URL)))
            v.addWidget(support, 0, Qt.AlignCenter)
            v.addSpacing(6)

        legal = QLabel(f"© {APP_YEAR} {html.escape(DEV_NAME)} · Open source under the MIT Licence")
        legal.setAlignment(Qt.AlignCenter)
        legal.setStyleSheet("font-size:9px;color:#686256;border-top:1px solid #bdb8ad;padding-top:6px;")
        v.addWidget(legal)

        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)


class LinkTreeDialog(QDialog):
    def __init__(self, links, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Link Tree")
        self.setMinimumSize(760, 460)
        self._worker = None
        v = QVBoxLayout(self)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Label", "URL", "Description", "Preview"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        v.addWidget(self.table)

        for lnk in links:
            self._add_row(lnk)

        btns = QHBoxLayout()
        add_btn = QPushButton("+ Add")
        add_btn.clicked.connect(lambda: self._add_row({}))
        del_btn = QPushButton("− Delete")
        del_btn.clicked.connect(lambda: self.table.removeRow(self.table.currentRow()))
        up_btn = QPushButton("↑"); up_btn.clicked.connect(lambda: self._move(-1))
        dn_btn = QPushButton("↓"); dn_btn.clicked.connect(lambda: self._move(1))
        self.fetch_btn = QPushButton("⟳ Fetch Previews")
        self.fetch_btn.setToolTip("Icon, title, description, image and player from each page")
        self.fetch_btn.clicked.connect(self._fetch_previews)
        self.status_lbl = QLabel()
        for b in (add_btn, del_btn, up_btn, dn_btn, self.fetch_btn):
            btns.addWidget(b)
        btns.addWidget(self.status_lbl, 1)
        v.addLayout(btns)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        v.addWidget(bb)

    # fetched preview data lives on the label cell
    def _add_row(self, lnk: dict, at: int = None):
        r = self.table.rowCount() if at is None else at
        self.table.insertRow(r)
        label = QTableWidgetItem(lnk.get("label", ""))
        meta = {k: lnk.get(k, "") for k in ("icon", "page_title", "page_desc", "image", "embed")}
        meta["fetched_url"] = lnk.get("url", "") if any(meta.values()) else ""
        label.setData(Qt.UserRole, meta)
        label.setIcon(data_uri_icon(meta["icon"]))
        self.table.setItem(r, 0, label)
        self.table.setItem(r, 1, QTableWidgetItem(lnk.get("url", "")))
        self.table.setItem(r, 2, QTableWidgetItem(lnk.get("desc", "")))
        prev = QTableWidgetItem("")
        prev.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
        prev.setCheckState(Qt.Checked if lnk.get("preview", True) else Qt.Unchecked)
        self.table.setItem(r, 3, prev)
        self._mark_embed(r)

    def _mark_embed(self, r):
        meta = self.table.item(r, 0).data(Qt.UserRole) or {}
        self.table.item(r, 3).setText("▶ player" if meta.get("embed") else ("🖼 card" if meta.get("image") else ""))

    def _row_link(self, r):
        g = lambda c: (self.table.item(r, c) or QTableWidgetItem()).text().strip()
        meta = dict(self.table.item(r, 0).data(Qt.UserRole) or {})
        url = g(1)
        if meta.get("fetched_url") != url:      # URL edited → stale preview
            meta = {"fetched_url": ""}
        link = {"label": g(0), "url": url, "desc": g(2),
                "preview": self.table.item(r, 3).checkState() == Qt.Checked}
        for k in ("icon", "page_title", "page_desc", "image", "embed"):
            link[k] = meta.get(k, "")
        return link

    def _move(self, d):
        r = self.table.currentRow()
        if r < 0 or not (0 <= r + d < self.table.rowCount()):
            return
        lnk = self._row_link(r)
        self.table.removeRow(r)
        self._add_row(lnk, r + d)
        self.table.setCurrentCell(r + d, 0)

    def _fetch_previews(self):
        jobs = []
        for r in range(self.table.rowCount()):
            url = self.table.item(r, 1).text().strip()
            if url and not re.match(r"https?://", url, re.I) and "." in url:
                url = "https://" + url
                self.table.item(r, 1).setText(url)
            if re.match(r"https?://", url, re.I) and url not in jobs:
                jobs.append(url)
        if not jobs or (self._worker and self._worker.isRunning()):
            return
        self.fetch_btn.setEnabled(False)
        self._pending = len(jobs)
        self._errors = 0
        self.status_lbl.setText(f"Fetching {len(jobs)}…")
        self._worker = LinkPreviewWorker(jobs, self)
        self._worker.row_done.connect(self._on_preview)
        self._worker.finished.connect(self._on_fetch_done)
        self._worker.start()

    def _on_preview(self, url, prev, err):
        self._pending -= 1
        if err:
            self._errors += 1
        for row in range(self.table.rowCount()):
            if err or self.table.item(row, 1).text().strip() != url:
                continue
            item = self.table.item(row, 0)
            item.setData(Qt.UserRole, dict(prev, fetched_url=url))
            item.setIcon(data_uri_icon(prev.get("icon", "")))
            if not item.text().strip() and prev.get("page_title"):
                item.setText(prev["page_title"][:60])
            if not self.table.item(row, 2).text().strip() and prev.get("page_desc"):
                self.table.item(row, 2).setText(prev["page_desc"][:140])
            self._mark_embed(row)
        self.status_lbl.setText(f"Fetching… {self._pending} left")

    def _on_fetch_done(self):
        self.fetch_btn.setEnabled(True)
        self.status_lbl.setText("Done" + (f" · {self._errors} unreachable" if self._errors else ""))

    def done(self, result):
        if self._worker:
            self._worker.cancel()               # don't wait on the network
        super().done(result)

    def get_links(self):
        out = []
        for r in range(self.table.rowCount()):
            lnk = self._row_link(r)
            if lnk["label"] or lnk["url"]:
                out.append(lnk)
        return out


# ─── Portfolio Settings Dialog ────────────────────────────────────────────────

class SettingsDialog(QDialog):
    def __init__(self, project: Project, parent=None, title="Portfolio Settings"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(500)
        v = QVBoxLayout(self)

        form = QFormLayout()
        self.title_e   = QLineEdit(project.title)
        self.author_e  = QLineEdit(project.author)
        self.email_e   = QLineEdit(getattr(project, "email", ""))
        self.email_e.setPlaceholderText("you@example.com")
        self.tagline_e = QLineEdit(project.tagline)
        form.addRow("Portfolio Title:", self.title_e)
        form.addRow("Name:",            self.author_e)
        form.addRow("Email:",           self.email_e)
        form.addRow("Tagline:",         self.tagline_e)

        pw_row = QHBoxLayout()
        self.pw_e = QLineEdit(getattr(project, "file_password", ""))
        self.pw_e.setEchoMode(QLineEdit.Password)
        self.pw_e.setPlaceholderText("none")
        self.pw_e.setToolTip("For password downloads. Not saved in the project file — asked again at export.")
        show_pw = QCheckBox("Show")
        show_pw.toggled.connect(lambda on: self.pw_e.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password))
        pw_row.addWidget(self.pw_e, 1); pw_row.addWidget(show_pw)

        self.access_c = QComboBox()
        for key, label in (("preview",  "Preview only"),
                           ("password", "Preview + password download"),
                           ("open",     "Preview + open download")):
            self.access_c.addItem(label, key)
        self.access_c.setCurrentIndex(max(0, self.access_c.findData(getattr(project, "pdf_access", "preview"))))
        self.access_c.setToolTip("What clicking a document card leads to in the exported portfolio")
        self.req_e = QLineEdit(getattr(project, "request_email", ""))
        self.req_e.setPlaceholderText("same as Email")
        self.access_c.currentIndexChanged.connect(self._sync_pw_enabled)

        form.addRow("Documents:", self.access_c)
        form.addRow("Request Email:", self.req_e)
        form.addRow("File Password:", pw_row)

        donate_row = QHBoxLayout()
        self.donate_e = QLineEdit(getattr(project, "donate_url", ""))
        self.donate_e.setPlaceholderText("ko-fi.com/you · paypal.me/you")
        self.donate_lbl_e = QLineEdit(getattr(project, "donate_label", "") or "Donate")
        self.donate_lbl_e.setMaximumWidth(120)
        self.donate_lbl_e.setToolTip("Button text")
        donate_row.addWidget(self.donate_e, 1); donate_row.addWidget(self.donate_lbl_e)
        form.addRow("Donate Link:", donate_row)
        v.addLayout(form)
        self._sync_pw_enabled()

        v.addWidget(QLabel("Introduction:"))
        self.intro_e = QTextEdit(project.intro)
        self.intro_e.setMinimumHeight(160)
        v.addWidget(self.intro_e)

        form2 = QFormLayout()
        self.theme_c = QComboBox()
        for key, label in THEME_LABELS.items():
            self.theme_c.addItem(label, key)
        self.theme_c.setCurrentIndex(max(0, self.theme_c.findData(project.theme)))
        form2.addRow("Theme:", self.theme_c)

        tex_row = QHBoxLayout()
        self.tex_c = QComboBox()
        for key, label in TEXTURES.items():
            self.tex_c.addItem(label, key)
        self.tex_c.setCurrentIndex(max(0, self.tex_c.findData(getattr(project, "texture", "none"))))
        self.tex_path = getattr(project, "texture_path", "")
        self.tex_preview = QLabel()
        self.tex_preview.setFixedSize(64, 32)
        self.tex_preview.setStyleSheet("border:1px solid #555;")
        self.tex_c.activated.connect(self._texture_chosen)
        self.theme_c.currentIndexChanged.connect(self._update_tex_preview)
        tex_row.addWidget(self.tex_c, 1); tex_row.addWidget(self.tex_preview)
        form2.addRow("Background:", tex_row)
        v.addLayout(form2)
        self._update_tex_preview()

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def get_values(self):
        return {
            "title":   self.title_e.text().strip(),
            "author":  self.author_e.text().strip(),
            "email":   self.email_e.text().strip(),
            "tagline": self.tagline_e.text().strip(),
            "intro":   self.intro_e.toPlainText(),
            "theme":   self.theme_c.currentData() or "broadsheet",
            "pdf_access":    self.access_c.currentData() or "preview",
            "request_email": self.req_e.text().strip(),
            "file_password": self.pw_e.text(),
            "donate_url":    (parse_links_text(self.donate_e.text()) or [{"url": ""}])[0]["url"],
            "donate_label":  self.donate_lbl_e.text().strip() or "Donate",
            "texture":       self.tex_c.currentData() or "none",
            "texture_path":  self.tex_path,
        }

    def _texture_chosen(self, *_):
        if self.tex_c.currentData() == "custom":
            path, _ = QFileDialog.getOpenFileName(self, "Background Image", "", IMAGE_FILTER)
            if path:
                self.tex_path = path
            elif not self.tex_path:
                self.tex_c.setCurrentIndex(0)
        self._update_tex_preview()

    def _update_tex_preview(self, *_):
        base = THEMES.get(self.theme_c.currentData() or "broadsheet", THEMES["broadsheet"])["bg"]
        tile = make_texture(self.tex_c.currentData() or "none", base, self.tex_path)
        pm = QPixmap(64, 32)
        pm.fill(QColor(base))
        if not tile.isNull():
            p = QPainter(pm)
            p.fillRect(pm.rect(), QBrush(QPixmap.fromImage(tile)))
            p.end()
        self.tex_preview.setPixmap(pm)

    def _sync_pw_enabled(self, *_):
        self.pw_e.setEnabled(self.access_c.currentData() == "password")


# ─── HTML Exporter ─────────────────────────────────────────────────────────────

# Display names for the portfolio themes (keys kept for saved projects)
THEME_LABELS = {
    "broadsheet": "Newspaper",
    "tabloid":    "Tabloid",
    "magazine":   "Magazine",
    "minimal":    "Academic",
    "dark":       "Editorial",
}

THEMES = {
    "broadsheet": dict(
        bg="#f5efe0", paper="#fffdf5", text="#1a1a1a", accent="#8b0000",
        accent2="#5c3317", col_rule="#bbb",
        font_head="Georgia,'Times New Roman',serif",
        font_body="Georgia,serif",
        font_mono="'Courier New',monospace",
        rule_h="4px double", rule_color="#111",
    ),
    "tabloid": dict(
        bg="#e4e4e4", paper="#ffffff", text="#000", accent="#cc0000",
        accent2="#880000", col_rule="#ccc",
        font_head="Impact,'Arial Black',sans-serif",
        font_body="Arial,Helvetica,sans-serif",
        font_mono="'Courier New',monospace",
        rule_h="6px solid", rule_color="#000",
    ),
    "magazine": dict(
        bg="#fafafa", paper="#fff", text="#1c1c1e", accent="#e91e63",
        accent2="#9c27b0", col_rule="#eee",
        font_head="'Playfair Display',Georgia,serif",
        font_body="'Lato',Arial,sans-serif",
        font_mono="monospace",
        rule_h="3px solid", rule_color="#e91e63",
    ),
    "minimal": dict(            # shown as "Academic"
        bg="#f7f7f4", paper="#ffffff", text="#1b1b1b", accent="#1f3a68",
        accent2="#5a5a5a", col_rule="#cfcfcf",
        font_head="'Garamond','Times New Roman',serif",
        font_body="'Times New Roman',Times,serif",
        font_mono="'Courier New',monospace",
        rule_h="1px solid", rule_color="#1b1b1b",
    ),
    "dark": dict(
        bg="#0d1117", paper="#161b22", text="#c9d1d9", accent="#58a6ff",
        accent2="#3fb950", col_rule="#30363d",
        font_head="'Georgia',serif",
        font_body="'Segoe UI',system-ui,sans-serif",
        font_mono="'Courier New',monospace",
        rule_h="2px solid", rule_color="#58a6ff",
    ),
}


class HTMLExporter:
    _texture_css = ""

    def export(self, project: Project, out_dir: str, scene: "FolioScene" = None) -> str:
        os.makedirs(out_dir, exist_ok=True)
        assets = os.path.join(out_dir, "assets")
        os.makedirs(assets, exist_ok=True)
        t = THEMES.get(project.theme, THEMES["broadsheet"])
        self._project   = project
        self._out_dir   = out_dir
        self._t         = t
        self._doc_pages = {}            # document path → its preview page (written once)
        tile = make_texture(getattr(project, "texture", "none"), t["bg"], getattr(project, "texture_path", ""))
        self._texture_css = ""
        if not tile.isNull():
            buf = QBuffer(); buf.open(QIODevice.WriteOnly)
            tile.save(buf, "PNG" if project.texture != "custom" else "JPG")
            tex = self._write_bytes(bytes(buf.data()), ".png" if project.texture != "custom" else ".jpg", assets)
            self._texture_css = f"background-image:url({tex});background-repeat:repeat;"

        # Export is always the BSP packing (never the free-form canvas grid)
        self._ensure_bsp_layout(project, scene)

        items_html, bsp_w, bsp_h = self._render_items(project.items, assets, t)
        main_html  = self._main_page(project, items_html, t, bsp_w, bsp_h)
        with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(main_html)

        if project.links:
            lt_html = self._linktree_page(project, t, assets)
            with open(os.path.join(out_dir, "links.html"), "w", encoding="utf-8") as f:
                f.write(lt_html)

        return out_dir

    def _item_scene_aabb(self, item: PortfolioItem):
        """Return (min_x, min_y, max_x, max_y) of the item's rotated bounding box."""
        w = max(1.0, float(item.w))
        h = max(1.0, float(item.h))
        cx = float(item.x) + w / 2.0
        cy = float(item.y) + h / 2.0
        theta = math.radians(float(getattr(item, "rotation", 0.0)))
        ct = abs(math.cos(theta))
        st = abs(math.sin(theta))
        aw = w * ct + h * st
        ah = w * st + h * ct
        return (cx - aw / 2.0, cy - ah / 2.0, cx + aw / 2.0, cy + ah / 2.0)

    def _ensure_bsp_layout(self, project: Project, scene: "FolioScene" = None):
        """Re-pack every item with the canvas BSP so the page matches a BSP layout."""
        if not project.items:
            return
        if scene is not None:
            scene.bsp_autolayout([c for c in scene.items() if isinstance(c, BaseCard)])
        else:
            tmp_scene = FolioScene()
            for it in project.items:
                tmp_scene.add_card(it)
            tmp_scene.bsp_autolayout(list(tmp_scene.items()))

    # ── asset copy ────────────────────────────────────────────────────────────

    @staticmethod
    def _hash_name(raw: bytes, ext: str, tag: str = "") -> str:
        return hashlib.sha256(raw).hexdigest()[:16] + tag + ext.lower()

    def _write_bytes(self, raw: bytes, ext: str, assets) -> str:
        """Store bytes under a content-hash name (identical files are stored once)."""
        name = self._hash_name(raw, ext)
        dst = os.path.join(assets, name)
        if not os.path.exists(dst):
            with open(dst, "wb") as f:
                f.write(raw)
        return f"assets/{name}"

    def _write_data_uri(self, uri: str, assets) -> str:
        m = re.match(r"data:(image/[\w.+-]+);base64,(.*)", uri or "", re.S)
        if not m:
            return ""
        ext = {"image/jpeg": ".jpg", "image/svg+xml": ".svg", "image/x-icon": ".ico"}.get(m.group(1), ".png")
        return self._write_bytes(base64.b64decode(m.group(2)), ext, assets)

    def _copy(self, src, assets):
        """Copy a file into assets/ under a content-hash name."""
        if not src or not os.path.isfile(src):
            return None
        return self._write_bytes(Path(src).read_bytes(), Path(src).suffix, assets)

    def _publish_doc(self, src, assets, mode=""):
        """The downloadable copy of a document, per its Document setting (blank → the
        portfolio's): None (preview only), an AES-256 encrypted PDF (password) or a plain copy (open)."""
        p = getattr(self, "_project", None)
        mode = mode or getattr(p, "pdf_access", "preview")
        if not src or not os.path.isfile(src):
            return None
        if mode == "open":
            return self._copy(src, assets)
        pw = getattr(p, "file_password", "")
        if mode != "password" or not pw or Path(src).suffix.lower() != ".pdf" or fitz is None:
            return None
        raw = Path(src).read_bytes()
        # name from content + password, so changing the password produces a new file
        name = self._hash_name(raw + pw.encode("utf-8"), ".pdf", "-locked")
        dst = os.path.join(assets, name)
        if not os.path.exists(dst):
            with fitz.open(src) as doc:
                doc.save(dst, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw=pw, owner_pw=pw,
                         permissions=fitz.PDF_PERM_PRINT | fitz.PDF_PERM_COPY | fitz.PDF_PERM_ACCESSIBILITY)
        return f"assets/{name}"

    # ── document preview pages ────────────────────────────────────────────────

    @staticmethod
    def _has_doc(item) -> bool:
        return Path(item.file_path or "").suffix.lower() in DOC_EXTS and os.path.isfile(item.file_path or "")

    def _doc_item(self, item):
        """The item holding this card's document: itself, or any piece of its article group."""
        if self._has_doc(item):
            return item
        gid = getattr(item, "group_id", "")
        if gid:
            for o in self._project.items:
                if o.group_id == gid and self._has_doc(o):
                    return o
        return None

    def _doc_meta(self, doc_item):
        """Kicker / headline / standfirst / links of a document, gathered across its group."""
        gid = getattr(doc_item, "group_id", "")
        members = [o for o in self._project.items if gid and o.group_id == gid] or [doc_item]
        def first(kind, *attrs):
            for o in members:
                if o.kind == kind:
                    for a in attrs:
                        if getattr(o, a, ""):
                            return getattr(o, a)
            return ""
        kicker   = first("strapline", "strapline", "title") or doc_item.strapline
        title    = first("headline", "title") or doc_item.title or Path(doc_item.file_path).stem
        abstract = first("abstract", "abstract", "notes") or doc_item.abstract
        links, seen = [], set()
        ordered = [doc_item] + [m for m in members if m is not doc_item]
        for o in ordered:
            for l in ([{"label": "", "url": o.url}] if o.url else []) + list(getattr(o, "links", []) or []):
                if l.get("url") and l["url"] not in seen:
                    seen.add(l["url"]); links.append(l)
        mailto = next((o.mailto for o in ordered if getattr(o, "mailto", "")), "")
        return kicker, title, abstract, links, mailto

    def _pdf_preview_pages(self, path, assets, max_pages=3, width=900):
        """First pages of a PDF rendered as JPEGs in assets/ → ([src], total pages)."""
        if fitz is None:
            return [], 0
        out = []
        try:
            with fitz.open(path) as doc:
                if doc.needs_pass:
                    return [], doc.page_count
                for page in list(doc)[:max_pages]:
                    zoom = width / max(1.0, page.rect.width)
                    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                    out.append(self._write_bytes(pix.tobytes("jpg", jpg_quality=82), ".jpg", assets))
                return out, doc.page_count
        except Exception:
            return out, 0

    def _doc_page(self, item, assets):
        """href of the preview page for the card's document (None if it has none)."""
        doc_item = self._doc_item(item)
        if doc_item is None:
            return None
        path = doc_item.file_path
        if path in self._doc_pages:
            return self._doc_pages[path]
        href = f"doc-{doc_item.id}.html"
        self._doc_pages[path] = href
        with open(os.path.join(self._out_dir, href), "w", encoding="utf-8") as f:
            f.write(self._doc_page_html(doc_item, assets))
        return href

    def _doc_page_html(self, doc_item, assets):
        esc, p, t = html.escape, self._project, self._t
        path = doc_item.file_path
        ext = Path(path).suffix.lower()
        kicker, title, abstract, links, card_mail = self._doc_meta(doc_item)

        if ext == ".pdf":
            pages, total = self._pdf_preview_pages(path, assets)
            shown = len(pages)
            figs = "".join(f'<figure class="pg"><img src="{s}" alt="Page {i + 1}" loading="lazy"></figure>'
                           for i, s in enumerate(pages))
            if shown:
                rng = "page 1" if shown == 1 else f"pages 1–{shown}"
                cap = f"Preview — {rng} of {total}" if total else "Preview"
            else:
                cap = "No preview available"
            meta = f"PDF · {total} page{'s' if total != 1 else ''}" if total else "PDF"
        else:
            paras = document_paragraphs(path)
            excerpt, n = [], 0
            for para in paras:
                excerpt.append(para); n += len(para)
                if n > 1800:
                    break
            figs = f'<div class="excerpt">{"".join(f"<p>{esc(x)}</p>" for x in excerpt)}</div>' if excerpt else ""
            cap = "Excerpt" if excerpt else "No preview available"
            meta = ext.lstrip(".").upper()

        buttons = []
        download = self._publish_doc(path, assets, getattr(doc_item, "pdf_access", ""))
        if download:
            locked = "-locked" in download
            buttons.append(f'<a class="btn btn-main" href="{download}" download="{esc(Path(path).stem)}{ext}">'
                           f'{"🔒 Download (password)" if locked else "⬇ Download"}</a>')
        for l in links:
            buttons.append(f'<a class="btn" href="{esc(l["url"])}" target="_blank" rel="noopener">'
                           f'{esc(l.get("label") or "Visit " + (link_domain(l["url"]) or "link"))} ↗</a>')
        to = card_mail or getattr(p, "request_email", "") or getattr(p, "email", "")
        if to and not (download and "-locked" not in download):
            subject = urllib.parse.quote(f"Request: {title}")
            body = urllib.parse.quote(f"Hello{' ' + p.author if p.author else ''},\n\n"
                                      f"I would like to read the full document “{title}”.\n\nThank you,\n")
            cls = "btn" if download else "btn btn-main"
            buttons.append(f'<a class="{cls}" href="mailto:{esc(to)}?subject={subject}&amp;body={body}">✉ Request the full document</a>')
        buttons.append(self._donate_html(p, "btn btn-donate"))
        actions = f'<div class="actions">{"".join(b for b in buttons if b)}</div>'

        more = '<p class="more">The full document is available on request.</p>' if not download and to else ""
        return self._detail_shell(title, kicker, meta, abstract, buttons, cap, f'<div class="pages">{figs}</div>',
                                  more, os.path.basename(path))

    def _detail_shell(self, title, kicker, meta, abstract, buttons, cap, body, more="", top_right=""):
        """Page used for document and picture previews: masthead link back, headline block,
        action buttons, then the preview itself (right-click / dragging of previews is off)."""
        esc, p, t = html.escape, self._project, self._t
        kicker_h = f'<div class="kicker">{esc(kicker)}</div>' if kicker else ""
        abs_h    = f'<p class="standfirst">{esc(abstract)}</p>' if abstract else ""
        bits     = [esc(x) for x in (p.author, meta) if x]
        meta_h   = f'<div class="meta">{" · ".join(bits)}</div>' if bits else ""
        actions  = f'<div class="actions">{"".join(b for b in buttons if b)}</div>'
        cap_h    = f'<div class="cap">{esc(cap)}</div>' if cap else ""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} — {esc(p.title)}</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{background:{t['bg']};{self._texture_css}color:{t['text']};font-family:{t['font_body']};line-height:1.5;padding:40px 16px 56px}}
a{{color:inherit;text-decoration:none}}
.wrap{{max-width:860px;margin:0 auto}}
.top{{display:flex;justify-content:space-between;align-items:center;font-family:{t['font_mono']};font-size:.75rem;
  border-bottom:{t['rule_h']} {t['rule_color']};padding-bottom:10px;margin-bottom:28px}}
.top a{{color:{t['accent']};font-weight:bold}}
.top a:hover{{text-decoration:underline}}
.kicker{{color:{t['accent']};font-weight:bold;letter-spacing:1.6px;text-transform:uppercase;font-size:.8rem;margin-bottom:6px}}
h1{{font-family:{t['font_head']};font-size:clamp(1.8rem,4.5vw,3rem);line-height:1.1}}
.meta{{font-family:{t['font_mono']};font-size:.72rem;opacity:.65;margin-top:10px}}
.standfirst{{font-style:italic;font-size:1.08rem;margin-top:16px;padding:12px 0;
  border-top:1px solid {t['col_rule']};border-bottom:1px solid {t['col_rule']}}}
.actions{{display:flex;flex-wrap:wrap;gap:10px;margin:22px 0 30px}}
.btn{{display:inline-flex;align-items:center;gap:6px;padding:9px 16px;border-radius:999px;cursor:pointer;
  border:1px solid {t['accent']};color:{t['accent']};background:{t['paper']};font-size:.88rem;font-weight:bold;
  transition:background .15s,color .15s}}
.btn:hover,.btn-main{{background:{t['accent']};color:#fff}}
.btn-main:hover{{filter:brightness(1.1)}}
.btn-donate{{border-color:{t['accent2']};color:{t['accent2']}}}
.btn-donate:hover{{background:{t['accent2']};color:#fff}}
.cap{{font-family:{t['font_mono']};font-size:.72rem;text-transform:uppercase;letter-spacing:1.4px;opacity:.7;margin-bottom:12px}}
.pages{{display:flex;flex-direction:column;gap:22px;user-select:none}}
.pg img{{width:100%;height:auto;display:block;background:#fff;box-shadow:0 4px 22px rgba(0,0,0,.18);
  -webkit-user-drag:none;pointer-events:none}}
.pic img{{background:transparent;max-height:82vh;width:auto;max-width:100%;margin:0 auto}}
.excerpt{{background:{t['paper']};border:1px solid {t['col_rule']};padding:26px 30px;column-width:320px;column-gap:30px;
  -webkit-mask-image:linear-gradient(#000 75%,transparent);mask-image:linear-gradient(#000 75%,transparent)}}
.excerpt p{{margin-bottom:.8em}}
.caption-text{{font-style:italic;text-align:center;margin-top:12px;opacity:.85}}
.more{{text-align:center;margin-top:28px;font-style:italic;opacity:.75}}
</style>
</head>
<body>
<div class="wrap">
  <div class="top"><a href="index.html">← {esc(p.title)}</a><span>{esc(top_right)}</span></div>
  {kicker_h}
  <h1>{esc(title)}</h1>
  {meta_h}
  {abs_h}
  {actions}
  {cap_h}
  {body}
  {more}
</div>
<script>document.addEventListener('contextmenu',function(e){{if(e.target.closest('.pg'))e.preventDefault();}});</script>
</body>
</html>"""

    def _image_page(self, item, assets):
        """Preview page for a picture: the web-size version only, its links, and a request
        for the high-resolution file by email."""
        href = f"img-{item.id}.html"
        src = self._copy_item_image(item, assets)
        if not src:
            return None
        esc, p = html.escape, self._project
        title = item.title or "Image"
        buttons = []
        links = ([{"label": "", "url": item.url}] if item.url else []) + list(getattr(item, "links", []) or [])
        for l in links:
            if l.get("url"):
                buttons.append(f'<a class="btn" href="{esc(l["url"])}" target="_blank" rel="noopener">'
                               f'{esc(l.get("label") or "Visit " + (link_domain(l["url"]) or "link"))} ↗</a>')
        to = getattr(item, "mailto", "") or getattr(p, "request_email", "") or getattr(p, "email", "")
        if to:
            subject = urllib.parse.quote(f"High-resolution request: {title}")
            body = urllib.parse.quote(f"Hello{' ' + p.author if p.author else ''},\n\n"
                                      f"I would like the high-resolution version of “{title}”.\n\nThank you,\n")
            buttons.insert(0, f'<a class="btn btn-main" href="mailto:{esc(to)}?subject={subject}&amp;body={body}">'
                              f'✉ Request high resolution</a>')
        buttons.append(self._donate_html(p, "btn btn-donate"))
        cap = f'<p class="caption-text">{esc(item.notes)}</p>' if item.notes and item.notes != title else ""
        page = self._detail_shell(title, item.strapline, "", "", buttons, "",
                                  f'<div class="pages"><figure class="pg pic"><img src="{src}" alt="{esc(title)}"></figure></div>{cap}')
        with open(os.path.join(self._out_dir, href), "w", encoding="utf-8") as f:
            f.write(page)
        return href

    @staticmethod
    def _donate_html(project, cls="donate-btn") -> str:
        url = getattr(project, "donate_url", "")
        if not url:
            return ""
        label = getattr(project, "donate_label", "") or "Donate"
        return f'<a class="{cls}" href="{html.escape(url)}" target="_blank" rel="noopener">♥ {html.escape(label)}</a>'

    WEB_SIDE = 1600          # long side of the published ("banner") version of a picture

    def _copy_item_image(self, item, assets, max_side=None):
        """Publish the card's picture (embedded > cover > image file) as a web-size copy.
        The high-res original is never written to the site."""
        img = item_image(item, max_side or self.WEB_SIDE)
        if img.isNull():
            return None
        side = max_side or self.WEB_SIDE
        if max(img.width(), img.height()) > side:
            img = img.scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        transparent = img.hasAlphaChannel() and \
            any(QColor.fromRgba(img.pixel(x, y)).alpha() < 250 for x, y in
                ((0, 0), (img.width() - 1, 0), (0, img.height() - 1), (img.width() - 1, img.height() - 1),
                 (img.width() // 2, img.height() // 2)))
        buf = QBuffer(); buf.open(QIODevice.WriteOnly)
        if transparent:
            img.save(buf, "PNG"); ext = ".png"
        else:
            img.convertToFormat(QImage.Format_RGB32).save(buf, "JPG", 86); ext = ".jpg"
        return self._write_bytes(bytes(buf.data()), ext, assets)

    # ── item renderers (exact BSP positioning & newspaper box styles) ─────────

    def _item_box_style(self, item: PortfolioItem, x0: float, y0: float):
        st = get_style_palette(item, "dark_dispatch" if item.kind == "url" else "broadsheet")
        fam = getattr(item, "font_family", "Georgia") or "Georgia"
        left = float(item.x) - x0
        top  = float(item.y) - y0
        w    = max(1.0, float(item.w))
        h    = max(1.0, float(item.h))
        rot  = float(getattr(item, "rotation", 0.0))

        css = [
            "position:absolute",
            f"left:{left:.2f}px",
            f"top:{top:.2f}px",
            f"width:{w:.2f}px",
            f"height:{h:.2f}px",
            f"font-family:'{fam}',Georgia,serif",
            f"background:{st['bg']}",
            f"color:{st['ink']}",
            f"text-align:{getattr(item, 'align', 'left')}",
            "transform-origin:50% 50%",
        ]
        if abs(rot) > 1e-3:
            css.append(f"transform:rotate({rot:.2f}deg)")

        if st.get("double_border"):
            css.append(f"border:2.5px solid {st['ink']}")
            css.append(f"outline:1px solid {st['rule']}")
            css.append("outline-offset:-6px")
        else:
            bw = "2px" if item.box_style == "tabloid_splash" else "1px"
            css.append(f"border:{bw} solid {st['rule']}")

        top_bar = st.get("top_bar", 0)
        if top_bar > 0:
            bar_col = st["accent"] if item.box_style == "tabloid_splash" else st["ink"]
            css.append(f"border-top:{top_bar}px solid {bar_col}")
            if item.box_style == "boxed_editorial":
                css.append(f"border-bottom:{top_bar}px solid {bar_col}")

        left_bar = st.get("left_bar", 0)
        if left_bar > 0:
            css.append(f"border-left:{left_bar}px solid {st['accent']}")

        if getattr(item, "bold", False):
            css.append("font-weight:bold")
        if getattr(item, "italic", False):
            css.append("font-style:italic")
        if getattr(item, "underline", False):
            css.append("text-decoration:underline")

        return ";".join(css), st

    def _render_items(self, items, assets, t):
        if not items:
            return "", 1200.0, 800.0

        aabbs = [self._item_scene_aabb(it) for it in items]
        x0 = min(b[0] for b in aabbs)
        y0 = min(b[1] for b in aabbs)
        x1 = max(b[2] for b in aabbs)
        y1 = max(b[3] for b in aabbs)
        bsp_w = max(320.0, x1 - x0)
        bsp_h = max(200.0, y1 - y0)

        parts = []
        for item in items:
            fn = {
                "image":     self._img_card,
                "article":   self._article_card,
                "strapline": self._strapline_card,
                "headline":  self._headline_card,
                "abstract":  self._abstract_card,
                "text":      self._text_card,
                "url":       self._url_card,
                "linktree":  self._linktree_card,
                "quote":     self._quote_card,
                "donate":    self._donate_card,
            }.get(item.kind, self._img_card)
            card_html = fn(item, assets, t, x0, y0).rstrip()
            extra = self._card_hit(item, assets) + self._link_chips(item)
            if extra and card_html.endswith("</div>"):
                card_html = card_html[:-len("</div>")] + extra + "\n</div>"
            parts.append(card_html)
        return "\n".join(parts), bsp_w, bsp_h

    def _img_card(self, item, assets, t, x0, y0):
        src = self._copy_item_image(item, assets)
        img = f'<img src="{src}" alt="{html.escape(item.title)}" loading="lazy" draggable="false">' if src else '<div class="no-img">📷</div>'
        # a set URL opens directly; otherwise the picture's preview page (web size + high-res request)
        page = None if item.url else self._image_page(item, assets)
        href = item.url or page
        target = ' target="_blank" rel="noopener"' if item.url else ""
        wa  = f'<a href="{href}"{target} style="display:block;width:100%;height:100%;">' if href else ""
        we  = "</a>" if href else ""
        style_str, _ = self._item_box_style(item, x0, y0)
        bg = item.bg_color if getattr(item, "bg_color", "") else "#111111"
        foot = ""
        if item.title or item.notes:
            label = item.title or item.notes
            cap = f'<p class="caption">{item.notes}</p>' if (item.title and item.notes) else ""
            foot = f'<div class="card-img-overlay"><h3>{label}</h3>{cap}</div>'
        return f"""<div class="card card-image" style="{style_str};background:{bg};border:none;">
  {wa}{img}{we}
  {foot}
</div>"""

    def _strapline_card(self, item, assets, t, x0, y0):
        style_str, st = self._item_box_style(item, x0, y0)
        txt = (item.strapline or item.title or "KICKER").upper()
        scale = min(item.w / 260.0, item.h / 38.0)
        pt = max(7.5, min(28.0, float(item.font_size or 10) * max(0.75, min(1.8, scale))))
        if item.box_style == "tabloid_splash":
            extra = f"background:{st['accent']};color:#fff;"
            fg = "#ffffff"
        else:
            extra = f"border-top:2px solid {st['accent']};border-bottom:1px solid {st['rule']};"
            fg = item.text_color or st["accent"]
        return f"""<div class="card card-strapline" style="{style_str};{extra}display:flex;align-items:center;padding:4px 12px;">
  <span style="width:100%;color:{fg};font-weight:bold;letter-spacing:1.8px;font-size:{pt:.1f}pt;line-height:1.1;">{txt}</span>
</div>"""

    def _headline_card(self, item, assets, t, x0, y0):
        style_str, st = self._item_box_style(item, x0, y0)
        scale = math.sqrt((item.w * item.h) / (380.0 * 90.0))
        pt = max(9.0, float(item.title_font_size or 18) * max(0.7, min(2.3, scale)))
        extra = "background:#111111;color:#ffffff;" if item.box_style == "tabloid_splash" else ""
        return f"""<div class="card card-headline" style="{style_str};{extra}display:flex;align-items:center;padding:8px 14px;">
  <h2 style="width:100%;font-size:{pt:.1f}pt;line-height:1.12;font-weight:bold;">{item.title or "Headline"}</h2>
</div>"""

    def _abstract_card(self, item, assets, t, x0, y0):
        style_str, st = self._item_box_style(item, x0, y0)
        txt = item.abstract or item.notes or item.title
        scale = math.sqrt((item.w * item.h) / (380.0 * 95.0))
        pt = max(7.5, float(item.font_size or 10) * max(0.8, min(1.8, scale)))
        return f"""<div class="card card-abstract" style="{style_str};display:flex;align-items:center;padding:10px 14px;font-style:italic;">
  <div style="width:100%;border-top:1px solid {st['rule']};border-bottom:1px solid {st['rule']};padding:6px 0;font-size:{pt:.1f}pt;line-height:1.4;">{txt}</div>
</div>"""

    def _article_card(self, item, assets, t, x0, y0):
        style_str, st = self._item_box_style(item, x0, y0)
        scale = max(0.75, min(1.75, math.sqrt((item.w * item.h) / (380.0 * 300.0))))
        head_pt = max(9.5, float(item.title_font_size or 15) * scale)
        body_pt = max(7.0, float(item.font_size or 9) * scale)
        thumb_src = self._copy_item_image(item, assets, 900)
        thumb     = f'<img src="{thumb_src}" class="art-thumb" style="max-width:{int(min(item.w * 0.35, 130 * scale))}px;" alt="">' if thumb_src else ""
        dc_cls    = " drop-cap" if getattr(item, "drop_cap", False) else ""
        cols      = max(1, min(4, int(getattr(item, "columns", 2))))
        strap_h   = f'<div style="color:{st["accent"]};font-weight:bold;letter-spacing:1.4px;font-size:{max(7.5, 8.5 * scale):.1f}pt;text-transform:uppercase;margin-bottom:3px;">{item.strapline}</div>' if getattr(item, "strapline", "") else ""

        show_title = item.title if item.title else ("" if getattr(item, "group_id", "") else "Headline")
        if show_title:
            if st.get("banner_head"):
                title_h = f'<h2 class="art-title" style="background:{st["accent"]};color:#fff;padding:4px 8px;font-size:{head_pt:.1f}pt;margin-bottom:6px;">{show_title}</h2>'
            else:
                title_h = f'<h2 class="art-title" style="font-size:{head_pt:.1f}pt;border-bottom:1px solid {st["rule"]};padding-bottom:5px;margin-bottom:6px;">{show_title}</h2>'
        else:
            title_h = ""

        abs_h     = f'<p style="font-style:italic;color:{st["muted"]};border-bottom:1px dotted {st["rule"]};padding-bottom:6px;margin-bottom:8px;font-size:{max(7.5, body_pt * 0.96):.1f}pt;">{item.abstract}</p>' if getattr(item, "abstract", "") else ""
        body_paras = self._paras_html(item.notes, getattr(item, "drop_cap", False))
        # plain footer text — the whole card is the link (see _card_hit)
        links     = []
        if self._has_doc(item):
            links.append(f'<span class="art-url art-file" style="color:{st["accent"]}">'
                         f'📄 {html.escape(os.path.basename(item.file_path))} · Preview ↗</span>')
        if item.url:
            links.append(f'<span class="art-url" style="color:{st["muted"]}">{html.escape(item.url[:60])}</span>')
        url_lnk   = f'<div class="art-links">{"".join(links)}</div>' if links else ""
        return f"""<div class="card card-article" style="{style_str};display:flex;flex-direction:column;">
  {strap_h}{title_h}{abs_h}
  <div class="art-body" style="flex:1;min-height:0;overflow:hidden;">
    {thumb}
    <div class="art-text{dc_cls}" style="flex:1;column-count:{cols};column-gap:14px;column-rule:1px solid {st['rule']};font-size:{body_pt:.1f}pt;line-height:1.38;">{body_paras}</div>
  </div>
  {url_lnk}
</div>"""

    def _text_card(self, item, assets, t, x0, y0):
        style_str, st = self._item_box_style(item, x0, y0)
        scale   = max(0.75, min(1.8, math.sqrt((item.w * item.h) / (420.0 * 280.0))))
        head_pt = max(9.0, float(item.title_font_size or 13) * scale)
        body_pt = max(7.0, float(item.font_size or 9) * scale)
        dc_cls  = " drop-cap" if getattr(item, "drop_cap", False) else ""
        cols    = max(1, min(4, int(getattr(item, "columns", 2))))
        strap   = f'<div style="color:{st["accent"]};font-weight:bold;letter-spacing:1.4px;font-size:{max(7.0, 8.0 * scale):.1f}pt;text-transform:uppercase;margin-bottom:3px;">{item.strapline}</div>' if getattr(item, "strapline", "") else ""
        head    = f'<h3 style="font-size:{head_pt:.1f}pt;border-bottom:1px solid {st["rule"]};padding-bottom:4px;margin-bottom:6px;">{item.title}</h3>' if item.title else ""
        paras   = self._paras_html(item.notes, getattr(item, "drop_cap", False))
        rule_st = "dashed" if item.box_style == "broadsheet" else "solid"
        return f"""<div class="card card-text" style="{style_str};display:flex;flex-direction:column;">
  {strap}{head}
  <div class="text-cols{dc_cls}" style="flex:1;min-height:0;overflow:hidden;column-count:{cols};column-gap:14px;column-rule:1px {rule_st} {st['rule']};font-size:{body_pt:.1f}pt;line-height:1.38;">{paras}</div>
</div>"""

    def _url_card(self, item, assets, t, x0, y0):
        style_str, st = self._item_box_style(item, x0, y0)
        scale   = max(0.75, min(1.75, math.sqrt((item.w * item.h) / (300.0 * 120.0))))
        head_pt = max(8.5, float(item.title_font_size or 12) * scale)
        body_pt = max(6.5, float(item.font_size or 8.5) * scale)
        strap   = f'<span style="color:{st["accent"]};font-weight:bold;letter-spacing:1.2px;font-size:{max(6.5, 7.5 * scale):.1f}pt;text-transform:uppercase;">{item.strapline}</span>' if getattr(item, "strapline", "") else ""
        desc    = f'<span class="ul-desc" style="color:{st["ink"]};font-size:{body_pt:.1f}pt;">{item.notes}</span>' if item.notes else ""
        title_col = st["accent"] if item.box_style == "dark_dispatch" else st["ink"]
        return f"""<div class="card card-url" style="{style_str};">
  <a href="{item.url}" target="_blank" rel="noopener" class="ul-link" style="width:100%;height:100%;position:relative;">
    {strap}
    <span class="ul-name" style="color:{title_col};font-size:{head_pt:.1f}pt;">{item.title or item.url}</span>
    <span class="ul-addr" style="color:{st['muted']};font-size:{max(6.5, 7.5 * scale):.1f}pt;">{item.url}</span>
    {desc}
    <span class="ul-arrow" style="color:{st['accent']};position:absolute;right:12px;bottom:8px;font-size:{max(10.0, 13.0 * scale):.1f}pt;">↗</span>
  </a>
</div>"""

    def _quote_card(self, item, assets, t, x0, y0):
        style_str, st = self._item_box_style(item, x0, y0)
        mark = max(24.0, min(90.0, item.h * 0.42))
        pt = quote_font_pt(item.notes, item.w - 28 - mark * 0.55, item.h - 40) * 0.9
        fg = item.text_color or st["ink"]
        attrib = (f'<footer style="color:{st["accent"]};font-size:{max(7.0, pt * 0.62):.1f}pt;">— {html.escape(item.title.upper())}</footer>'
                  if item.title else "")
        return f"""<div class="card card-quote" style="{style_str};padding:10px 14px 10px {14 + mark * 0.55:.0f}px;">
  <span class="q-mark" style="color:{st['accent']};font-size:{mark:.0f}px;">“</span>
  <blockquote style="color:{fg};font-size:{pt:.1f}pt;">{html.escape(item.notes or "")}{attrib}</blockquote>
</div>"""

    def _donate_card(self, item, assets, t, x0, y0):
        style_str, st = self._item_box_style(item, x0, y0)
        url = item.url or getattr(self._project, "donate_url", "")
        label = html.escape(item.title or getattr(self._project, "donate_label", "") or "Donate")
        accent = item.text_color or st["accent"]
        heart = min(item.h * (0.38 if item.notes else 0.48), item.w * 0.3)
        pill = max(18.0, min(heart * 0.34, item.h * 0.2))
        msg = f'<span class="dn-msg" style="color:{st["ink"]};">{html.escape(item.notes)}</span>' if item.notes else ""
        tag = "a" if url else "div"
        href = f' href="{html.escape(url)}" target="_blank" rel="noopener"' if url else ""
        return f"""<div class="card card-donate" style="{style_str};">
  <{tag} class="dn-link"{href}>
    <span class="dn-heart" style="color:{accent};font-size:{heart * 1.05:.0f}px;">♥</span>
    <span class="dn-pill" style="background:{accent};font-size:{pill * 0.42:.1f}px;height:{pill:.0f}px;padding:0 {pill * 0.7:.0f}px;">{label}</span>
    {msg}
  </{tag}>
</div>"""

    def _card_hit(self, item, assets) -> str:
        """Whole-card link: a document card (or any piece of its article group) opens the
        document's preview page; an article without a document opens its URL."""
        if item.kind not in ("article", "strapline", "headline", "abstract"):
            return ""
        page = self._doc_page(item, assets)
        if page:
            return f'\n  <a class="card-hit" href="{page}" aria-label="{html.escape(item.title or "Open document")}"></a>'
        if item.kind == "article" and item.url:
            return f'\n  <a class="card-hit" href="{html.escape(item.url)}" target="_blank" rel="noopener" aria-label="{html.escape(item.title or item.url)}"></a>'
        return ""

    @staticmethod
    def _link_chips(item) -> str:
        """Attached links as small chips pinned to the card's bottom edge. Kinds that don't
        use their URL themselves (kicker / headline / standfirst / text) show it first."""
        links = list(getattr(item, "links", []) or [])
        if item.url and item.kind in ("strapline", "headline", "abstract", "text"):
            links.insert(0, {"label": "", "url": item.url})
        mail = getattr(item, "mailto", "")
        if not links and not mail:
            return ""
        chips = "".join(
            f'<a class="chip" href="{html.escape(l["url"])}" target="_blank" rel="noopener">'
            f'{html.escape(l.get("label") or link_domain(l["url"]) or l["url"])} ↗</a>'
            for l in links)
        if mail:
            subject = urllib.parse.quote(item.title or item.strapline or "Hello")
            chips += f'<a class="chip" href="mailto:{html.escape(mail)}?subject={subject}">✉ Contact</a>'
        return f'\n  <div class="card-chips">{chips}</div>'

    @staticmethod
    def _paras_html(text, drop_cap=False):
        """One <p> per line; the drop cap is a real floated span (::first-letter breaks in columns)."""
        paras = [p.strip() for p in (text or "").split("\n") if p.strip()]
        out = []
        for i, p in enumerate(paras):
            if i == 0 and drop_cap and len(p) >= 2:
                out.append(f'<p class="dc-p"><span class="dc">{p[0]}</span>{p[1:].lstrip()}</p>')
                continue
            out.append(f"<p>{p}</p>")
        return "".join(out)

    def _linktree_card(self, item, assets, t, x0, y0):
        style_str, st = self._item_box_style(item, x0, y0)
        scale   = max(0.75, min(1.6, math.sqrt((item.w * item.h) / (300.0 * 260.0))))
        head_pt = max(9.0, float(item.title_font_size or 13) * scale)
        name_pt = max(7.5, float(item.font_size or 10) * scale)
        links   = [l for l in getattr(self, "_project", Project()).links if l.get("url")]
        esc = html.escape
        icon_px = int(max(14, 16 * scale))
        rows = []
        for l in links:
            icon_src = self._write_data_uri(l.get("icon", ""), assets)
            icon = (f'<img src="{icon_src}" class="lt-row-icon" style="width:{icon_px}px;height:{icon_px}px" alt="">'
                    if icon_src else "")
            name = l.get("label") or l.get("page_title") or l["url"]
            play = " ▶" if l.get("embed") and l.get("preview", True) else ""
            rows.append(
                f'<a href="{esc(l["url"])}" class="lt-row" target="_blank" rel="noopener" style="border-left:3px solid {st["accent"]};">'
                f'{icon}<span class="lt-row-text">'
                f'<span class="lt-row-name" style="font-size:{name_pt:.1f}pt;">{esc(name)}</span>'
                f'<span class="lt-row-url" style="color:{st["muted"]};font-size:{max(6.5, 7 * scale):.1f}pt;">{esc(link_domain(l["url"]))}{play}</span>'
                f'</span></a>')
        rows = "".join(rows)
        more = f'<a href="links.html" class="lt-more" style="color:{st["accent"]};">All links ↗</a>' if links else ""
        return f"""<div class="card card-linktree" style="{style_str};display:flex;flex-direction:column;padding:8px 12px;">
  <h3 style="font-size:{head_pt:.1f}pt;border-bottom:1px solid {st['rule']};padding-bottom:4px;margin-bottom:6px;">{item.title or "Links"}</h3>
  <div style="flex:1;min-height:0;overflow:hidden;display:flex;flex-direction:column;gap:6px;">{rows}</div>
  {more}
</div>"""

    # ── pages ─────────────────────────────────────────────────────────────────

    def _main_page(self, project, items_html, t, bsp_w=2920.0, bsp_h=1960.0):
        intro_sec = ""
        if project.intro:
            paras = "".join(f"<p>{p.strip()}</p>" for p in project.intro.split("\n\n") if p.strip())
            intro_sec = f'<section class="intro"><div class="intro-inner">{paras}</div></section>'

        links_nav = '<a href="links.html" class="mast-nav-link">Links ↗</a>' if project.links else ""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{project.title}</title>
<style>
/* ── reset ── */
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
img{{display:block;max-width:100%}}
a{{color:inherit;text-decoration:none}}

/* ── tokens ── */
:root{{
  --bg:    {t['bg']};
  --paper: {t['paper']};
  --text:  {t['text']};
  --acc:   {t['accent']};
  --acc2:  {t['accent2']};
  --rule:  {t['col_rule']};
  --fh:    {t['font_head']};
  --fb:    {t['font_body']};
  --fm:    {t['font_mono']};
}}
body{{background:var(--bg);{self._texture_css}color:var(--text);font-family:var(--fb);line-height:1.5}}

/* ── masthead ── */
.masthead{{
  background:var(--paper);
  border-bottom:{t['rule_h']} {t['rule_color']};
  text-align:center;
  padding:28px 40px 16px;
}}
.masthead h1{{
  font-family:var(--fh);
  font-size:clamp(2.2rem,6vw,5.5rem);
  letter-spacing:-1px;line-height:1;
  color:var(--text);
}}
.mast-tagline{{
  font-style:italic;color:#999;margin-top:6px;font-size:1rem;
}}
.mast-meta{{
  font-family:var(--fm);font-size:.68rem;color:#999;
  border-top:1px solid var(--rule);margin-top:10px;padding-top:8px;
  display:flex;justify-content:space-between;align-items:center;
}}
.mast-nav-link{{color:var(--acc);font-weight:bold;}}
.mast-actions{{display:flex;align-items:center;gap:14px}}
.donate-btn{{font-family:var(--fm);font-weight:bold;font-size:.72rem;padding:4px 12px;border-radius:999px;
  background:var(--acc);color:#fff;transition:filter .15s}}
.donate-btn:hover{{filter:brightness(1.12)}}
.mast-email:hover{{color:var(--acc);text-decoration:underline}}

/* ── intro ── */
.intro{{max-width:960px;margin:28px auto;padding:0 24px}}
.intro-inner{{
  column-count:2;column-gap:36px;column-rule:1px solid var(--rule);
  font-size:1.02rem;
}}
.intro-inner p{{margin-bottom:.9em}}

/* ── BSP Packed Newspaper Stage ── */
.bsp-stage{{
  width:calc(100% - 48px);
  max-width:1800px;
  margin:28px auto;
  position:relative;
  overflow:hidden;
}}
.bsp-canvas{{
  position:relative;
  transform-origin:0 0;
}}

/* ── cards ── */
.card{{
  background:var(--paper);
  overflow:hidden;
  transition:box-shadow .2s;
}}
.card:hover{{box-shadow:0 6px 24px rgba(0,0,0,.16);z-index:5}}
.card-hit{{position:absolute;inset:0;z-index:1;cursor:pointer}}
.card:has(.card-hit):hover .art-title,.card:has(.card-hit):hover h2{{text-decoration:underline;text-decoration-thickness:1px}}

/* attached links */
.card-chips{{position:absolute;right:8px;bottom:8px;display:flex;flex-wrap:wrap;justify-content:flex-end;
  gap:4px;max-width:calc(100% - 16px);z-index:2}}
.chip{{font-family:var(--fm);font-size:10px;line-height:1;padding:4px 8px;border-radius:999px;
  background:var(--paper);color:var(--acc);border:1px solid var(--acc);white-space:nowrap;
  box-shadow:0 1px 3px rgba(0,0,0,.15)}}
.chip:hover{{background:var(--acc);color:var(--paper)}}

/* drop cap */
.dc-p{{display:flow-root;break-inside:avoid}}
.dc{{
  float:left;
  font-size:2.4em;
  line-height:0.84;
  padding-right:6px;
  padding-top:2px;
  font-weight:bold;
  color:var(--acc);
}}

/* image */
.card-image img{{width:100%;height:100%;object-fit:contain;display:block;}}
.no-img{{width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:3rem;color:#555;background:#111;}}
.card-img-overlay{{
  position:absolute;left:0;right:0;bottom:0;
  padding:14px 12px 8px;
  background:linear-gradient(to bottom,rgba(0,0,0,0),rgba(0,0,0,.82));
  color:#fff;
}}
.card-img-overlay h3{{font-size:1rem;line-height:1.2}}
.caption{{font-size:.78rem;color:#ddd;margin-top:3px}}

/* article */
.card-article{{padding:12px 14px}}
.art-title{{line-height:1.15;}}
.art-body{{display:flex;gap:12px}}
.art-thumb{{height:auto;object-fit:contain;align-self:flex-start;flex-shrink:0}}
.art-text p{{margin-bottom:.55em}}
.art-url{{
  display:block;margin-top:6px;font-family:var(--fm);
  font-size:.65rem;word-break:break-all;
}}
.art-url:hover{{text-decoration:underline}}
.art-links{{display:flex;flex-wrap:wrap;gap:4px 14px;align-items:baseline}}
.art-file{{font-weight:bold}}

/* pull quote */
.card-quote{{display:flex;align-items:center;position:absolute}}
.q-mark{{position:absolute;left:10px;top:-0.18em;font-family:Georgia,serif;font-weight:bold;line-height:1}}
.card-quote blockquote{{font-style:italic;line-height:1.3;width:100%}}
.card-quote footer{{font-style:normal;font-weight:bold;letter-spacing:1.2px;text-align:right;margin-top:8px}}

/* heart / donate */
.dn-link{{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;width:100%;height:100%;padding:8px;text-align:center}}
.dn-heart{{line-height:1;transition:transform .2s}}
.dn-link:hover .dn-heart{{transform:scale(1.12)}}
.dn-pill{{display:inline-flex;align-items:center;border-radius:999px;color:#fff;font-weight:bold;font-family:var(--fm)}}
.dn-msg{{font-style:italic;font-size:.82rem}}

/* text */
.card-text{{padding:10px 12px}}
.text-cols p{{margin-bottom:.55em}}

/* url */
.ul-link{{
  display:flex;flex-direction:column;gap:4px;padding:10px 14px;
  transition:filter .2s;
}}
.ul-link:hover{{filter:brightness(1.06)}}
.ul-name{{font-weight:bold;line-height:1.2}}
.ul-addr{{font-family:var(--fm);word-break:break-all}}

/* link tree */
.lt-row{{display:flex;align-items:center;gap:8px;padding:2px 0 2px 8px}}
.lt-row-icon{{flex-shrink:0;object-fit:contain;border-radius:3px}}
.lt-row-text{{display:flex;flex-direction:column;min-width:0}}
.lt-row:hover .lt-row-name{{text-decoration:underline}}
.lt-row-name{{font-weight:bold;line-height:1.2}}
.lt-row-url{{font-family:var(--fm);word-break:break-all}}
.lt-more{{font-family:var(--fm);font-size:.7rem;margin-top:6px;font-weight:bold}}

/* ── footer ── */
footer{{
  text-align:center;padding:28px;font-family:var(--fm);
  font-size:.68rem;color:#888;border-top:1px solid var(--rule);
  margin-top:48px;
}}
</style>
</head>
<body>
<header class="masthead">
  <h1>{project.title}</h1>
  {f'<p class="mast-tagline">{project.tagline}</p>' if project.tagline else ""}
  <div class="mast-meta">
    <span>{project.author}{f' · <a href="mailto:{html.escape(project.email)}" class="mast-email">{html.escape(project.email)}</a>' if getattr(project, "email", "") else ""}</span>
    <span class="mast-actions">{links_nav}{self._donate_html(project)}</span>
  </div>
</header>
{intro_sec}
<main class="bsp-stage" id="bsp-stage">
  <div class="bsp-canvas" id="bsp-canvas" data-w="{bsp_w:.2f}" data-h="{bsp_h:.2f}" style="width:{bsp_w:.2f}px;height:{bsp_h:.2f}px;">
{items_html}
  </div>
</main>
<footer>
  <p>{project.title} · {project.author} · Built with FolioPress {APP_VERSION}</p>
</footer>
<script>
(function(){{
  var stage  = document.getElementById('bsp-stage');
  var canvas = document.getElementById('bsp-canvas');
  if (!stage || !canvas) return;
  var bw = parseFloat(canvas.getAttribute('data-w')) || 1200;
  var bh = parseFloat(canvas.getAttribute('data-h')) || 800;
  function fitBSP(){{
    var sw = stage.clientWidth;
    if (sw <= 0) return;
    var scale = sw / bw;
    canvas.style.transform = 'scale(' + scale + ')';
    stage.style.height = Math.ceil(bh * scale) + 'px';
  }}
  document.addEventListener('contextmenu', function(e){{ if (e.target.tagName === 'IMG') e.preventDefault(); }});
  window.addEventListener('resize', fitBSP);
  if (window.ResizeObserver) new ResizeObserver(fitBSP).observe(stage);
  fitBSP();
}})();
</script>
</body>
</html>"""

    @staticmethod
    def _embed_height(embed: str) -> str:
        """CSS sizing for a player iframe."""
        if "spotify.com" in embed:
            return "height:352px" if re.search(r"/(album|playlist|show|artist)/", embed) else "height:152px"
        if "soundcloud.com" in embed:
            return "height:300px"
        return "aspect-ratio:16/9"

    def _linktree_page(self, project, t, assets):
        esc = html.escape
        rows = []
        for l in project.links:
            if not l.get("url"):
                continue
            url = esc(l["url"])
            name = esc(l.get("label") or l.get("page_title") or link_domain(l["url"]) or l["url"])
            desc = l.get("desc") or (l.get("page_desc") if l.get("preview", True) else "")
            icon_src = self._write_data_uri(l.get("icon", ""), assets)
            icon = (f'<img class="lt-icon" src="{icon_src}" alt="">' if icon_src
                    else f'<span class="lt-icon lt-icon-letter">{esc((name[:1] or "•").upper())}</span>')
            head = (f'<a class="lt-row" href="{url}" target="_blank" rel="noopener">{icon}'
                    f'<span class="lt-text"><span class="lt-name">{name}</span>'
                    f'<span class="lt-domain">{esc(link_domain(l["url"]))}</span>'
                    f'{f"""<span class="lt-desc">{esc(desc)}</span>""" if desc else ""}</span>'
                    f'<span class="lt-arrow">↗</span></a>')
            media = ""
            if l.get("preview", True) and l.get("embed"):
                media = (f'<iframe class="lt-embed" style="{self._embed_height(l["embed"])}" src="{esc(l["embed"])}" '
                         f'loading="lazy" referrerpolicy="strict-origin-when-cross-origin" '
                         f'allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" '
                         f'allowfullscreen title="{name}"></iframe>')
            elif l.get("preview", True) and l.get("image"):
                img_src = self._write_data_uri(l["image"], assets)
                if img_src:
                    media = f'<a href="{url}" target="_blank" rel="noopener"><img class="lt-image" src="{img_src}" alt="" loading="lazy"></a>'
            rows.append(f'<div class="lt-card{" has-media" if media else ""}">{media}{head}</div>')

        # documents from the portfolio, linked to their preview pages
        files = []
        seen = set()
        for it in project.items:
            if self._has_doc(it):
                page = self._doc_page(it, assets)
                if page and page not in seen:
                    seen.add(page)
                    files.append(f'<a class="lt-file" href="{page}">'
                                 f'<span>{esc(self._doc_meta(it)[1])}</span>'
                                 f'<span class="lt-domain">{esc(Path(it.file_path).suffix.upper().lstrip("."))} ↗</span></a>')
        files_sec = (f'<h2 class="lt-section">Files</h2><div class="lt-files">{"".join(files)}</div>' if files else "")

        name = esc(project.author or project.title)
        initials = "".join(p[0] for p in (project.author or project.title).split()[:2]).upper() or "•"
        email = esc(getattr(project, "email", "") or "")
        email_h = f'<a class="lt-email" href="mailto:{email}">✉ {email}</a>' if email else ""
        email_h += self._donate_html(project, "lt-email lt-donate")
        tagline = f'<p class="lt-tagline">{esc(project.tagline)}</p>' if project.tagline else ""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(project.title)} — Links</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{background:{t['bg']};{self._texture_css}color:{t['text']};font-family:{t['font_body']};min-height:100vh;
  display:flex;flex-direction:column;align-items:center;padding:56px 16px 40px}}
a{{color:inherit;text-decoration:none}}
.lt-wrap{{width:100%;max-width:560px}}
.lt-profile{{text-align:center;margin-bottom:32px}}
.lt-avatar{{width:84px;height:84px;border-radius:50%;margin:0 auto 14px;display:flex;align-items:center;justify-content:center;
  background:{t['accent']};color:#fff;font-family:{t['font_head']};font-size:2rem;font-weight:bold;
  box-shadow:0 0 0 4px {t['paper']},0 0 0 5px {t['col_rule']}}}
.lt-profile h1{{font-family:{t['font_head']};font-size:1.9rem;line-height:1.15}}
.lt-tagline{{color:{t['accent2']};font-style:italic;margin-top:6px}}
.lt-email{{display:inline-block;margin-top:12px;padding:5px 14px;border:1px solid {t['col_rule']};border-radius:999px;
  font-size:.82rem;background:{t['paper']}}}
.lt-email:hover{{border-color:{t['accent']};color:{t['accent']}}}
.lt-donate{{margin-left:8px;background:{t['accent']};border-color:{t['accent']};color:#fff;font-weight:bold}}
.lt-donate:hover{{color:#fff;filter:brightness(1.12)}}
.lt-stack{{display:flex;flex-direction:column;gap:12px}}
.lt-card{{background:{t['paper']};border:1px solid {t['col_rule']};border-radius:10px;overflow:hidden;
  transition:transform .15s,box-shadow .15s}}
.lt-card:hover{{transform:translateY(-2px);box-shadow:0 6px 18px rgba(0,0,0,.10)}}
.lt-row{{display:flex;align-items:center;gap:14px;padding:12px 16px}}
.lt-icon{{width:36px;height:36px;flex-shrink:0;border-radius:8px;object-fit:contain;background:#fff;padding:4px;
  border:1px solid {t['col_rule']}}}
.lt-icon-letter{{display:flex;align-items:center;justify-content:center;background:{t['accent']};color:#fff;
  border:none;font-weight:bold;font-family:{t['font_head']}}}
.lt-text{{display:flex;flex-direction:column;min-width:0;flex:1}}
.lt-name{{font-weight:bold;font-family:{t['font_head']};font-size:1.02rem;line-height:1.25}}
.lt-domain{{font-family:{t['font_mono']};font-size:.7rem;opacity:.6;margin-top:1px}}
.lt-desc{{font-size:.82rem;opacity:.8;margin-top:4px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
.lt-arrow{{color:{t['accent']};font-weight:bold;opacity:.5;transition:opacity .15s}}
.lt-card:hover .lt-arrow{{opacity:1}}
.lt-image{{display:block;width:100%;max-height:260px;object-fit:cover;border-bottom:1px solid {t['col_rule']}}}
.lt-embed{{display:block;width:100%;border:0;border-bottom:1px solid {t['col_rule']};background:#000}}
.lt-section{{font-family:{t['font_head']};font-size:.8rem;letter-spacing:2px;text-transform:uppercase;
  margin:34px 0 10px;color:{t['accent']};border-bottom:1px solid {t['col_rule']};padding-bottom:6px}}
.lt-files{{display:flex;flex-direction:column}}
.lt-file{{display:flex;justify-content:space-between;gap:12px;padding:9px 2px;border-bottom:1px dotted {t['col_rule']}}}
.lt-file:hover{{color:{t['accent']}}}
.back{{display:block;text-align:center;margin-top:36px;font-size:.8rem;color:{t['accent']}}}
.back:hover{{text-decoration:underline}}
</style>
</head>
<body>
<div class="lt-wrap">
  <header class="lt-profile">
    <div class="lt-avatar">{esc(initials)}</div>
    <h1>{name}</h1>
    {tagline}
    {email_h}
  </header>
  <div class="lt-stack">{"".join(rows)}</div>
  {files_sec}
  <a href="index.html" class="back">← Portfolio</a>
</div>
</body>
</html>"""


# ─── Main Window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project      = Project()
        self.cards_map    = {}          # item.id → BaseCard
        self._doc_jobs    = []          # [(item id, path)] waiting for DocImportWorker
        self._doc_worker  = None

        self.setWindowTitle(f"FolioPress — {self.project.title}")
        self.resize(1500, 940)

        self._build_ui()
        self._build_menus()
        self._apply_dark_chrome()
        self._mark_saved()
        self.status.showMessage("FolioPress ready — open a folder, drag files onto canvas, or use the toolbar to begin.")

    # ── chrome / style ────────────────────────────────────────────────────────

    def _apply_dark_chrome(self):
        self.setStyleSheet("""
        QMainWindow,QDialog  { background: #252526; }
        QDockWidget          { font-size:11px; color:#ccc; }
        QDockWidget::title   { background:#333; color:#bbb; padding:5px 8px; font-weight:bold; letter-spacing:0.5px; }
        QLabel               { color:#ccc; }
        QLineEdit,QTextEdit,QPlainTextEdit,QSpinBox,QComboBox {
            background:#1e1e1e;color:#ddd;border:1px solid #444;
            padding:5px;border-radius:3px;
        }
        QLineEdit:focus,QTextEdit:focus,QPlainTextEdit:focus { border:1px solid #2979FF; }
        QPushButton          { background:#383838;color:#ddd;border:1px solid #555;padding:5px 10px;border-radius:3px; }
        QPushButton:hover    { background:#484848; }
        QPushButton:checked  { background:#1565C0;color:white; }
        QTreeView            { background:#1e1e1e;color:#ccc;border:none; }
        QTreeView::item:hover    { background:#2a2d2e; }
        QTreeView::item:selected { background:#1565C0; }
        QTableWidget         { background:#1e1e1e;color:#ccc;gridline-color:#333; }
        QHeaderView::section { background:#333;color:#aaa;border:none;padding:5px; }
        QStatusBar           { background:#252526;color:#888;font-size:10px; }
        QMenuBar             { background:#252526;color:#ccc; }
        QMenuBar::item:selected { background:#333; }
        QMenu                { background:#252526;color:#ccc;border:1px solid #444; }
        QMenu::item:selected { background:#333; }
        QToolBar             { background:#2d2d2d;border:none;spacing:5px;padding:3px 6px; }
        QScrollBar:vertical,QScrollBar:horizontal { background:#2d2d2d;width:10px;border:none; }
        QScrollBar::handle:vertical,QScrollBar::handle:horizontal { background:#555;border-radius:5px;min-height:30px; }
        QFormLayout QLabel   { color:#aaa; }
        """)

    # ── UI layout ────────────────────────────────────────────────────────────

    def _build_ui(self):
        # canvas
        self.scene = FolioScene()
        self.scene.item_selected.connect(self._on_select)
        self.view  = FolioView(self.scene, self)
        self.setCentralWidget(self.view)

        # file browser dock (left)
        self.browser = FileBrowser()
        self.browser.files_requested.connect(self._batch_add_files)
        fdock = QDockWidget("📁  Files", self)
        fdock.setWidget(self.browser)
        fdock.setMinimumWidth(210)
        self.addDockWidget(Qt.LeftDockWidgetArea, fdock)

        # properties dock (right)
        self.props = PropertiesPanel()
        self.props.changed.connect(self._on_props_changed)
        self.props.split_article.connect(self._split_article_into_group)
        self.props.merge_group.connect(self._merge_article_group)
        self.props.detach_group.connect(self._detach_item_from_group)
        self.props.replace_source.connect(self._replace_source)
        self.props.edit_image.connect(self._edit_item_image)
        self.props.extract_text.connect(self._extract_text)
        self.props.fetch_url.connect(self._fetch_url_card)
        self.props.edit_linktree.connect(self._edit_links)
        pdock = QDockWidget("⚙  Properties", self)
        pdock.setObjectName("properties")
        pdock.setWidget(self.props)
        pdock.setMinimumWidth(265)
        pdock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable |
                          QDockWidget.DockWidgetClosable)
        pdock.setTitleBarWidget(DockTitleBar(pdock))
        self.addDockWidget(Qt.RightDockWidgetArea, pdock)
        pdock.hide()                    # opens when a card is clicked
        self.props_dock = pdock

        # toolbar
        tb = self.addToolBar("Tools")
        tb.setMovable(False)

        def _btn(label, tip, fn, style=""):
            b = QPushButton(label); b.setToolTip(tip)
            b.clicked.connect(fn)
            if style: b.setStyleSheet(style)
            tb.addWidget(b); return b

        self.snap_btn = QPushButton("⊞  Snap")
        self.snap_btn.setCheckable(True); self.snap_btn.setChecked(True)
        self.snap_btn.setToolTip("Toggle snap-to-grid (Ctrl+G)")
        self.snap_btn.toggled.connect(self._toggle_snap)
        tb.addWidget(self.snap_btn)
        tb.addSeparator()

        _btn("📷 Image", "Insert image", self._insert_image)
        _btn("📥 Import", "Import PDF / RTF / TXT", self._import_documents)
        for label, tip, kind in [("📄 Article", "Article", "article"), ("✏ Text", "Text box", "text"),
                                 ("❝ Quote", "Pull quote", "quote"), ("▬ Kicker", "Kicker / strapline", "strapline"),
                                 ("🔗 Link", "Link", "url")]:
            _btn(label, tip, lambda c=False, k=kind: self._add_blank(k))
        _btn("🌳 Link Tree", "Link tree", self._add_linktree)
        _btn("♥ Heart", "Donate button", self._add_donate,
             "color:#ff5c7a;font-weight:bold;")

        _btn("📰 Article Group", "Kicker / Headline / Standfirst / Body",
             self._add_article_group,
             "background:#4a148c;color:white;font-weight:bold;padding:5px 10px;border-radius:3px;")
        tb.addSeparator()

        _btn("↺ -90°", "Rotate -90°", lambda: self._rotate_selected(-90.0))
        _btn("↻ +90°", "Rotate +90°", lambda: self._rotate_selected(90.0))
        _btn("🔗 Group", "Group", self._group_selected)
        _btn("🔓 Ungroup", "Ungroup", self._ungroup_selected)
        tb.addSeparator()

        _btn("⊞  BSP Layout", "BSP layout",
             self._bsp_all,
             "background:#1565C0;color:white;font-weight:bold;padding:5px 10px;border-radius:3px;")
        _btn("↔  Align Left",  "Align left",  self._align_left)
        _btn("↕  Align Top",   "Align top",   self._align_top)
        _btn("⤢  Stack",       "Stack",       self._stack)
        tb.addSeparator()

        _btn("🚀  Export HTML", "Export HTML",
             self.export_portfolio,
             "background:#8b0000;color:white;font-weight:bold;padding:6px 16px;border-radius:3px;")

        # status
        self.status = self.statusBar()

    # ── menus ────────────────────────────────────────────────────────────────

    def _build_menus(self):
        mb = self.menuBar()

        fm = mb.addMenu("&File")
        self._act(fm, "&New Project",    self._new_project,   "Ctrl+N")
        self._act(fm, "&Open Project…",  self._open_project,  "Ctrl+O")
        self._act(fm, "&Save Project",   self._save_project,  "Ctrl+S")
        self._act(fm, "Save &As…",       self._save_as)
        fm.addSeparator()
        self._act(fm, "&Insert Image…",            self._insert_image, "Ctrl+I")
        self._act(fm, "Import &PDF / RTF / TXT…",  self._import_documents, "Ctrl+Shift+I")
        fm.addSeparator()
        self._act(fm, "&Export Portfolio…", self.export_portfolio, "Ctrl+E")
        fm.addSeparator()
        self._act(fm, "&Quit", self.close, "Ctrl+Q")

        em = mb.addMenu("&Edit")
        self._act(em, "Portfolio &Settings…", self._project_settings)
        self._act(em, "Edit &Link Tree…",     self._edit_links)
        self._act(em, "Add Link &Tree Box",   self._add_linktree)
        em.addSeparator()
        self._act(em, "Add Article &Group",   self._add_article_group, "Ctrl+Shift+A")
        self._act(em, "Add &Kicker",          lambda: self._add_blank("strapline"))
        self._act(em, "Add &Headline",        lambda: self._add_blank("headline"))
        self._act(em, "Add &Standfirst",      lambda: self._add_blank("abstract"))
        self._act(em, "Add Pull &Quote",      lambda: self._add_blank("quote"))
        self._act(em, "Add ♥ &Heart Button",  self._add_donate)
        em.addSeparator()
        self._act(em, "&Group Selected",      self._group_selected,   "Ctrl+L")
        self._act(em, "&Ungroup Selected",    self._ungroup_selected, "Ctrl+U")
        self._act(em, "Rotate &Left (-90°)",  lambda: self._rotate_selected(-90.0), "Ctrl+[")
        self._act(em, "Rotate &Right (+90°)", lambda: self._rotate_selected(90.0),  "Ctrl+]")
        self._act(em, "Reset Rotation (0°)",  lambda: self._rotate_selected(0.0, absolute=True))
        em.addSeparator()
        self._act(em, "&Delete Selected",   self._delete_selected, "Delete")
        self._act(em, "Select &All",        self._select_all,   "Ctrl+A")
        em.addSeparator()
        self._act(em, "Raise to Front",     self._raise_front)
        self._act(em, "Send to Back",       self._send_back)

        vm = mb.addMenu("&View")
        self._act(vm, "Toggle &Grid Snap", lambda: self.snap_btn.toggle(), "Ctrl+G")
        self._act(vm, "&Fit Canvas",        self._fit, "Ctrl+0")
        vm.addAction(self.props_dock.toggleViewAction())
        self._act(vm, "Zoom &In",           lambda: self.view.scale(1.2,1.2), "Ctrl+=")
        self._act(vm, "Zoom &Out",          lambda: self.view.scale(1/1.2,1/1.2), "Ctrl+-")

        lm = mb.addMenu("&Layout")
        self._act(lm, "&BSP Auto-Layout (All)",      self._bsp_all)
        self._act(lm, "BSP Auto-Layout (&Selected)", self._bsp_sel)
        lm.addSeparator()
        self._act(lm, "Align &Left",  self._align_left)
        self._act(lm, "Align &Top",   self._align_top)
        self._act(lm, "&Stack Vertical", self._stack)

        hm = mb.addMenu("&Help")
        self._act(hm, "&About FolioPress…", lambda: AboutDialog(self).exec_())
        if SUPPORT_URL:
            self._act(hm, "♥ &Support FolioPress…",
                      lambda: QDesktopServices.openUrl(QUrl(SUPPORT_URL)))

    def _act(self, menu, label, fn, shortcut=None):
        a = QAction(label, self)
        if shortcut: a.setShortcut(shortcut)
        a.triggered.connect(fn)
        menu.addAction(a)
        return a

    # ── snap / selection ─────────────────────────────────────────────────────

    def _toggle_snap(self, on):
        self.scene.snap_to_grid = on
        self.scene.update()
        self.status.showMessage(f"Snap-to-grid: {'ON' if on else 'off'}")

    def _on_select(self, data):
        if data:
            self.props.load(data)
            if not self.props_dock.isVisible():
                self.props_dock.show()
        else:
            self.props.clear()
            self.props_dock.hide()

    def _on_props_changed(self):
        """Reload the card visual, geometry, rotation, and group state after properties changed."""
        self.scene._in_bsp_layout = True
        try:
            for card in self.scene.items():
                if isinstance(card, BaseCard):
                    card.prepareGeometryChange()
                    card.setPos(card.data.x, card.data.y)
                    card._sync_transform()
                    if hasattr(card, "_reload"):
                        card._reload()
                    card.update()
        finally:
            self.scene._in_bsp_layout = False
        self.scene.update()

    # ── adding items ─────────────────────────────────────────────────────────

    def add_file_at(self, path: str, x: float, y: float):
        ext = Path(path).suffix.lower()
        if ext in IMAGE_EXTS:
            kind = "image"
            size = QImageReader(path).size()          # header only — no full decode
            if size.isValid() and size.height() > 0:
                ar = float(size.width()) / float(size.height())
                base_area = 320.0 * 240.0
                h = max(80.0, math.sqrt(base_area / ar))
                w = max(120.0, h * ar)
            else:
                w, h = 320.0, 240.0
        elif ext in DOC_EXTS:
            kind = "article"
            w, h = 380.0, 300.0
        else:
            return None

        data = PortfolioItem(kind)
        data.file_path = path
        data.title = Path(path).stem.replace("_"," ").replace("-"," ").title()
        data.x = round(x / GRID) * GRID if self.scene.snap_to_grid else x
        data.y = round(y / GRID) * GRID if self.scene.snap_to_grid else y
        data.w, data.h = w, h

        self.project.items.append(data)
        card = self.scene.add_card(data)
        self.cards_map[data.id] = card
        if kind == "article" and os.path.isfile(path):
            self._queue_doc_import(data, path)      # headline / abstract / cover fill in shortly
        self.status.showMessage(f"Added: {data.title}")
        return card

    # ── background document reading ──────────────────────────────────────────

    def _queue_doc_import(self, data: PortfolioItem, path: str):
        self._doc_jobs.append((data.id, path))
        if self._doc_worker is None or not self._doc_worker.isRunning():
            self._start_doc_worker()

    def _start_doc_worker(self):
        if not self._doc_jobs:
            return
        jobs, self._doc_jobs = self._doc_jobs, []
        self._doc_worker = DocImportWorker(jobs)
        self._doc_worker.item_done.connect(self._on_doc_imported)
        self._doc_worker.finished.connect(self._start_doc_worker)   # pick up jobs queued meanwhile
        self._doc_worker.start()

    def _on_doc_imported(self, item_id: str, fields: dict, err: str):
        card = self.cards_map.get(item_id)
        if card is None:
            return                                    # card deleted meanwhile
        if err:
            self.status.showMessage(f"Could not read {Path(card.data.file_path).name}: {err}")
            return
        for k, v in fields.items():
            setattr(card.data, k, v)
        if hasattr(card, "_reload"):
            card._reload()
        card.update()
        if self.props._data is card.data:
            self.props.load(card.data)
        self.status.showMessage(f"Read: {card.data.title}")

    def _add_blank(self, kind):
        defaults = {
            "image":     (320, 240, "Image"),
            "article":   (400, 320, "Headline"),
            "strapline": (380, 42,  "KICKER"),
            "headline":  (380, 88,  "Headline"),
            "abstract":  (380, 92,  "Standfirst"),
            "text":      (420, 280, "Title"),
            "url":       (300, 120, "Link"),
            "linktree":  (320, 300, "Links"),
            "quote":     (400, 170, ""),
            "donate":    (240, 150, ""),
        }
        w, h, default_text = defaults.get(kind, (320, 240, "New Card"))
        data = PortfolioItem(kind)
        data.x, data.y = float(GRID * 6), float(GRID * 6)
        data.w, data.h = float(w), float(h)

        if kind == "strapline":
            data.strapline = default_text
            data.title     = default_text
            data.font_size = 10
            data.bold      = True
        elif kind == "headline":
            data.title           = default_text
            data.title_font_size = 20
            data.bold            = True
        elif kind == "abstract":
            data.abstract  = default_text
            data.notes     = default_text
            data.italic    = True
            data.columns   = 1
        elif kind == "article":
            data.strapline = "KICKER"
            data.title     = default_text
            data.abstract  = "Standfirst"
        elif kind == "text":
            data.title = default_text
        elif kind == "url":
            data.title = default_text
            data.url   = "https://"
        elif kind == "linktree":
            data.title   = default_text
            data.columns = 1
        elif kind == "quote":
            data.notes           = "A line worth repeating."
            data.title           = self.project.author
            data.title_font_size = 18
            data.columns         = 1
        elif kind == "donate":
            data.title    = self.project.donate_label or "Donate"
            data.notes    = "Support my work"
            data.align    = "center"
            data.columns  = 1

        self.project.items.append(data)
        card = self.scene.add_card(data)
        self.cards_map[data.id] = card
        self.scene.clearSelection()
        card.setSelected(True)
        self.props.load(data)
        return card

    def _add_article_group(self):
        """
        Create a complete newspaper article composed of 4 linked, separable,
        rotatable cards: Strapline, Headline (Title), Abstract, and Article Body.
        """
        gid = uuid.uuid4().hex[:8]
        x0, y0 = float(GRID * 5), float(GRID * 5)
        w0 = 420.0
        gap = float(GRID // 2)

        strap = PortfolioItem("strapline")
        strap.group_id  = gid
        strap.strapline = "KICKER"
        strap.title     = strap.strapline
        strap.x, strap.y, strap.w, strap.h = x0, y0, w0, 40.0
        strap.font_size = 9
        strap.bold      = True

        head = PortfolioItem("headline")
        head.group_id        = gid
        head.title           = "Headline"
        head.x, head.y, head.w, head.h = x0, y0 + 40.0 + gap, w0, 86.0
        head.title_font_size = 20
        head.bold            = True

        abst = PortfolioItem("abstract")
        abst.group_id = gid
        abst.abstract = "Standfirst"
        abst.notes    = abst.abstract
        abst.x, abst.y, abst.w, abst.h = x0, head.y + head.h + gap, w0, 84.0
        abst.font_size = 10
        abst.italic    = True
        abst.columns   = 1

        body = PortfolioItem("article")
        body.group_id  = gid
        body.title     = ""   # Title is in the separate HeadlineCard
        body.notes     = ""
        body.x, body.y, body.w, body.h = x0, abst.y + abst.h + gap, w0, 260.0
        body.columns  = 2
        body.drop_cap = True

        created = []
        for it in (strap, head, abst, body):
            self.project.items.append(it)
            c = self.scene.add_card(it)
            self.cards_map[it.id] = c
            created.append(c)

        self.scene.clearSelection()
        created[1].setSelected(True)
        self.props.load(head)
        self.status.showMessage("Article group added.")

    def _split_article_into_group(self, data: PortfolioItem):
        """Split a single Article card into linked Strapline, Headline, Abstract, and Body cards."""
        if not data or data.kind != "article":
            return
        gid = uuid.uuid4().hex[:8]
        x0, y0, w0 = data.x, data.y, max(260.0, data.w)
        gap = float(GRID // 2)

        def _copy_style(src: PortfolioItem, dst: PortfolioItem):
            for k in ("font_family", "font_size", "title_font_size", "bold", "italic",
                      "underline", "align", "box_style", "text_color", "bg_color", "rotation"):
                setattr(dst, k, getattr(src, k))
            dst.group_id     = gid
            dst.group_locked = True

        strap = PortfolioItem("strapline")
        _copy_style(data, strap)
        strap.strapline = data.strapline or "KICKER"
        strap.title     = strap.strapline
        strap.x, strap.y, strap.w, strap.h = x0, y0, w0, 40.0

        head = PortfolioItem("headline")
        _copy_style(data, head)
        head.title = data.title or "Headline"
        head.x, head.y, head.w, head.h = x0, strap.y + strap.h + gap, w0, 84.0

        abst = PortfolioItem("abstract")
        _copy_style(data, abst)
        abst.abstract = data.abstract or "Standfirst"
        abst.notes    = abst.abstract
        abst.columns  = 1
        abst.x, abst.y, abst.w, abst.h = x0, head.y + head.h + gap, w0, 80.0

        # Transform the existing article card into the Body component of the group
        data.group_id     = gid
        data.group_locked = True
        data.strapline    = ""
        data.title        = ""
        data.abstract     = ""
        data.x            = x0
        data.y            = abst.y + abst.h + gap
        data.w            = w0
        data.h            = max(180.0, data.h)

        for it in (strap, head, abst):
            self.project.items.append(it)
            c = self.scene.add_card(it)
            self.cards_map[it.id] = c

        self._on_props_changed()
        self.props.load(data)
        self.status.showMessage("Article split.")

    def _merge_article_group(self, gid: str):
        """Merge a grouped Strapline + Title + Abstract + Body back into one unified Article card."""
        if not gid:
            return
        members = [i for i in self.project.items if getattr(i, "group_id", "") == gid]
        if not members:
            return

        body_item = next((i for i in members if i.kind == "article"), None)
        if not body_item:
            body_item = PortfolioItem("article")
            body_item.x = min(i.x for i in members)
            body_item.y = min(i.y for i in members)
            body_item.w = max(i.w for i in members)
            body_item.h = sum(i.h for i in members)
            self.project.items.append(body_item)
            c = self.scene.add_card(body_item)
            self.cards_map[body_item.id] = c

        for m in members:
            if m is body_item:
                continue
            if m.kind == "strapline" and (m.strapline or m.title):
                body_item.strapline = m.strapline or m.title
            elif m.kind == "headline" and m.title:
                body_item.title = m.title
            elif m.kind == "abstract" and (m.abstract or m.notes):
                body_item.abstract = m.abstract or m.notes
            elif m.notes and not body_item.notes:
                body_item.notes = m.notes
            # Remove merged sub-card
            card_obj = self.cards_map.pop(m.id, None)
            if card_obj:
                self.scene.removeItem(card_obj)
            self.project.items = [i for i in self.project.items if i.id != m.id]

        body_item.group_id = ""
        body_item.x = min(m.x for m in members)
        body_item.y = min(m.y for m in members)
        body_item.h = max(280.0, body_item.h)
        self._on_props_changed()
        self.props.load(body_item)
        self.status.showMessage("Group merged.")

    def _detach_item_from_group(self, data: PortfolioItem):
        if not data:
            return
        data.group_id = ""
        self._on_props_changed()
        self.props.load(data)
        self.status.showMessage(f"Detached {data.kind} from group.")

    def _group_selected(self):
        sel = [c for c in self.scene.selectedItems() if isinstance(c, BaseCard)]
        if len(sel) < 2:
            self.status.showMessage("Select 2 or more cards to group them.")
            return
        gid = uuid.uuid4().hex[:8]
        for c in sel:
            c.data.group_id     = gid
            c.data.group_locked = True
            c.update()
        self.props.load(sel[0].data)
        self.status.showMessage(f"Grouped {len(sel)} cards [{gid}].")

    def _ungroup_selected(self):
        sel = [c for c in self.scene.selectedItems() if isinstance(c, BaseCard)]
        if not sel:
            return
        gids = {c.data.group_id for c in sel if getattr(c.data, "group_id", "")}
        for c in self.scene.items():
            if isinstance(c, BaseCard) and (c in sel or getattr(c.data, "group_id", "") in gids):
                c.data.group_id = ""
                c.update()
        self.props.load(sel[0].data)
        self.status.showMessage("Ungrouped selected cards.")

    def _rotate_selected(self, delta_deg: float, absolute: bool = False):
        sel = [c for c in self.scene.selectedItems() if isinstance(c, BaseCard)]
        if not sel:
            return
        for c in sel:
            if absolute:
                deg = delta_deg
            else:
                deg = (float(getattr(c.data, "rotation", 0.0)) + delta_deg)
                while deg > 180.0:
                    deg -= 360.0
                while deg <= -180.0:
                    deg += 360.0
            c.data.rotation = float(deg)
            c._sync_transform()
            c.update()
        self.props.load(sel[0].data)
        self.status.showMessage(f"Rotated selected card(s) to {sel[0].data.rotation:.0f}°.")

    def _batch_add_files(self, paths):
        """Grid-place files then BSP."""
        COLS = 4
        for i, path in enumerate(paths):
            col = i % COLS
            row = i // COLS
            x = float(GRID * 4 + col * (GRID * 20))
            y = float(GRID * 4 + row * (GRID * 16))
            self.add_file_at(path, x, y)
        if paths:
            self.scene.bsp_autolayout()
            self.status.showMessage(f"Batch added {len(paths)} files and auto-laid out.")

    def _place_new(self, data: PortfolioItem):
        self.project.items.append(data)
        card = self.scene.add_card(data)
        self.cards_map[data.id] = card
        self.scene.clearSelection()
        card.setSelected(True)
        self.props.load(data)
        return card

    def _image_card_size(self, img: QImage):
        ar = img.width() / max(1.0, float(img.height()))
        h = max(80.0, math.sqrt(320.0 * 240.0 / ar))
        return max(120.0, h * ar), h

    def _insert_image(self):
        """Opens the drawing canvas: draw from scratch, or Open / Place / Paste a picture and edit it."""
        ed = ImageEditorDialog(None, self, "Insert Image")
        if ed.exec_() != QDialog.Accepted:
            return
        data = PortfolioItem("image")
        data.x, data.y = float(GRID * 6), float(GRID * 6)
        img = ed.result_image()
        if ed.source_path and not ed.modified:
            data.file_path = ed.source_path          # untouched file: keep the original as the high-res
        else:
            data.embedded_image = image_to_b64(img)
            data.file_path = ed.source_path
        data.title = (Path(ed.source_path).stem.replace("_", " ").replace("-", " ").title()
                      if ed.source_path else "Drawing")
        if img.isNull():
            QMessageBox.warning(self, "Insert Image", "Could not read that image.")
            return
        data.w, data.h = self._image_card_size(img)
        self._place_new(data)
        self.status.showMessage("Image inserted.")

    def _import_documents(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Import", "", "Documents (*.pdf *.rtf *.txt *.md);;PDF (*.pdf);;RTF (*.rtf);;Text (*.txt *.md)")
        for i, p in enumerate(paths):
            self.add_file_at(p, GRID * 6 + i * GRID * 2, GRID * 6 + i * GRID * 2)
        if paths:
            self.status.showMessage(f"Imported {len(paths)} document(s).")

    def _add_donate(self):
        """Place the ♥ donate button in the layout (asks for the link the first time)."""
        if not self.project.donate_url:
            url, ok = QInputDialog.getText(self, "Donate Link", "Your donate page (Ko-fi, PayPal, Buy Me a Coffee…):")
            if not ok or not url.strip():
                return
            self.project.donate_url = parse_links_text(url.strip())[0]["url"]
        self._add_blank("donate")
        self.status.showMessage("Heart button added — it links to your donate page.")

    def _add_linktree(self):
        existing = next((c for c in self.scene.items()
                         if isinstance(c, LinkTreeCard)), None)
        if existing:
            self.scene.clearSelection()
            existing.setSelected(True)
            self.view.centerOn(existing)
        else:
            self._add_blank("linktree")
        if not self.project.links:
            self._edit_links()

    def _card_for(self, data: PortfolioItem):
        return self.cards_map.get(data.id)

    def _replace_source(self, data: PortfolioItem):
        if data.kind == "image":
            src = ImageSourceDialog(self)
            src.setWindowTitle("Replace Image")
            if src.exec_() != QDialog.Accepted:
                return
            if src.choice == "file":
                img = QImage(src.path)
                if img.isNull():
                    return
                data.file_path, data.cover_path, data.embedded_image = src.path, "", ""
                if src.edit_cb.isChecked():
                    ed = ImageEditorDialog(img, self, "Edit Image")
                    if ed.exec_() == QDialog.Accepted:
                        img = ed.result_image()
                        data.embedded_image = image_to_b64(img)
            else:
                ed = ImageEditorDialog(None, self, "Drawing")
                if ed.exec_() != QDialog.Accepted:
                    return
                img = ed.result_image()
                data.file_path, data.cover_path = "", ""
                data.embedded_image = image_to_b64(img)
            # keep the card's area, adopt the new aspect ratio
            area = data.w * data.h
            ar = img.width() / max(1.0, float(img.height()))
            data.h = math.sqrt(area / ar)
            data.w = data.h * ar
        elif data.kind == "article":
            path, _ = QFileDialog.getOpenFileName(
                self, "Replace Document", "", "Documents (*.pdf *.rtf *.txt *.md)")
            if not path:
                return
            if (data.notes or data.abstract) and QMessageBox.question(
                    self, "Replace Document", "Replace this article's text with the new document?",
                    QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
                return
            data.file_path = path
            self._queue_doc_import(data, path)
        elif data.kind == "text":
            path, _ = QFileDialog.getOpenFileName(
                self, "Text from File", "", "Documents (*.pdf *.rtf *.txt *.md)")
            if path:
                self._extract_text(data, path)     # pick the passages to insert
            return
        else:
            return
        self._on_props_changed()
        self.props.load(data)
        self.status.showMessage("Replaced.")

    def _attach_link(self, data: PortfolioItem):
        d = QDialog(self)
        d.setWindowTitle("Attach Link")
        form = QFormLayout(d)
        label_e = QLineEdit(); label_e.setPlaceholderText("optional")
        url_e = QLineEdit(); url_e.setPlaceholderText("https://")
        form.addRow("Label:", label_e)
        form.addRow("URL:", url_e)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept); bb.rejected.connect(d.reject)
        form.addRow(bb)
        d.setMinimumWidth(420)
        if d.exec_() != QDialog.Accepted:
            return
        new = parse_links_text(f"{label_e.text().strip()} | {url_e.text().strip()}" if label_e.text().strip()
                               else url_e.text().strip())
        if not new:
            return
        data.links = list(getattr(data, "links", []) or []) + new
        card = self.cards_map.get(data.id)
        if card:
            card.update()
        self.props.load(data)
        self.status.showMessage(f"Link attached ({len(data.links)} on this card).")

    def _fetch_url_card(self, data: PortfolioItem):
        """Fill a link card's name / description from the page itself."""
        if not re.match(r"https?://", data.url or "", re.I):
            self.status.showMessage("Enter an http(s) address first.")
            return
        worker = LinkPreviewWorker([data.url], self)
        self._url_workers = [w for w in getattr(self, "_url_workers", []) if w.isRunning()] + [worker]

        def done(url, res, err):
            if err or not res:
                self.status.showMessage(f"Couldn't fetch {link_domain(url)}: {err or 'no data'}")
                return
            data.title = res.get("page_title") or data.title
            data.notes = res.get("page_desc") or data.notes
            self._on_props_changed()
            if self.props._data is data:
                self.props.load(data)
            self.status.showMessage(f"Fetched {link_domain(url)}.")

        worker.row_done.connect(done)
        self.status.showMessage(f"Fetching {link_domain(data.url)}…")
        worker.start()

    def _extract_text(self, data: PortfolioItem, path: str = None):
        path = path or data.file_path
        if not path or not os.path.isfile(path):
            QMessageBox.information(self, "Extract Text", "The source document isn't available.")
            return
        dlg = ExtractTextDialog(path, self)

        def apply(target, text):
            if target == "new_text":
                t = PortfolioItem("text")
                t.notes = text
                t.columns = 1 if len(text) < 600 else 2
                t.x, t.y = data.x + data.w + GRID, data.y
                t.w, t.h = 360.0, 280.0
                self._place_new(t)
                return
            if target == "append":
                data.notes = (data.notes.rstrip("\n") + "\n" + text) if data.notes.strip() else text
            elif target == "body":
                data.notes = text
            else:
                setattr(data, target, text)
            self._on_props_changed()
            self.props.load(data)

        dlg.insert.connect(apply)
        dlg.exec_()
        self.props.load(data)

    def _edit_item_image(self, data: PortfolioItem):
        img = item_image(data, max_side=2400)
        ed = ImageEditorDialog(img if not img.isNull() else None, self, "Edit Image")
        if ed.exec_() != QDialog.Accepted:
            return
        out = ed.result_image()
        data.embedded_image = image_to_b64(out)
        if data.kind == "image" and not img.isNull() and (out.width(), out.height()) != (img.width(), img.height()):
            area = data.w * data.h
            ar = out.width() / max(1.0, float(out.height()))
            data.h = math.sqrt(area / ar)
            data.w = data.h * ar
        self._on_props_changed()
        self.props.load(data)

    # ── layout commands ──────────────────────────────────────────────────────

    def _bsp_all(self):
        self.scene.bsp_autolayout(None)

    def _bsp_sel(self):
        sel = [c for c in self.scene.selectedItems() if isinstance(c, BaseCard)]
        if sel: self.scene.bsp_autolayout(sel)

    def _align_left(self):
        sel = [c for c in self.scene.selectedItems() if isinstance(c, BaseCard)]
        if not sel: return
        mx = min(c.pos().x() for c in sel)
        for c in sel:
            c.setPos(mx, c.pos().y()); c.data.x = mx

    def _align_top(self):
        sel = [c for c in self.scene.selectedItems() if isinstance(c, BaseCard)]
        if not sel: return
        my = min(c.pos().y() for c in sel)
        for c in sel:
            c.setPos(c.pos().x(), my); c.data.y = my

    def _stack(self):
        sel = [c for c in self.scene.selectedItems() if isinstance(c, BaseCard)]
        x, y = 60.0, 60.0
        for c in sel:
            c.setPos(x, y); c.data.x, c.data.y = x, y
            y += c.data.h + GRID

    def _select_all(self):
        """Select every card on the canvas."""
        for c in self.scene.items():
            if isinstance(c, BaseCard):
                c.setSelected(True)

    def _delete_selected(self):
        for c in list(self.scene.selectedItems()):
            if isinstance(c, BaseCard):
                self.project.items = [i for i in self.project.items if i.id != c.data.id]
                self.cards_map.pop(c.data.id, None)
                self.scene.removeItem(c)
        self.props.clear()

    def _raise_front(self):
        for c in self.scene.selectedItems(): c.setZValue(c.zValue() + 1)

    def _send_back(self):
        for c in self.scene.selectedItems(): c.setZValue(c.zValue() - 1)

    def _fit(self):
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    # ── context menu for cards ────────────────────────────────────────────────

    def show_item_context(self, card: BaseCard, screen_pos):
        menu = QMenu(self)
        menu.addAction("Properties…",      lambda: self.props.load(card.data))
        menu.addAction("🔗 Attach Link…",  lambda: self._attach_link(card.data))
        if card.data.kind == "image":
            menu.addAction("⇄ Replace Image…", lambda: self._replace_source(card.data))
            menu.addAction("✎ Edit Image…",    lambda: self._edit_item_image(card.data))
        elif card.data.kind == "article":
            menu.addAction("⇄ Replace Document…", lambda: self._replace_source(card.data))
            menu.addAction("📑 Extract Text…",    lambda: self._extract_text(card.data))
            menu.addAction("Set Cover…",          lambda: self._pick_cover(card))
            menu.addAction("✎ Edit Cover…",       lambda: self._edit_item_image(card.data))
        elif card.data.kind == "linktree":
            menu.addAction("Edit Links…", self._edit_links)
        elif card.data.kind == "text":
            menu.addAction("⇄ Text from File…", lambda: self._replace_source(card.data))
        elif card.data.kind == "url":
            menu.addAction("⟳ Fetch Title && Description", lambda: self._fetch_url_card(card.data))
        menu.addSeparator()
        if card.data.kind == "article" and not getattr(card.data, "group_id", ""):
            menu.addAction("✂ Split", lambda: self._split_article_into_group(card.data))
        if getattr(card.data, "group_id", ""):
            gid = card.data.group_id
            menu.addAction("⊕ Merge Group", lambda: self._merge_article_group(gid))
            menu.addAction("🔓 Detach",     lambda: self._detach_item_from_group(card.data))
        menu.addSeparator()
        menu.addAction("↺ Rotate -90°", lambda: (setattr(card.data, "rotation", -90.0), card._sync_transform(), card.update(), self.props.load(card.data)))
        menu.addAction("↻ Rotate +90°", lambda: (setattr(card.data, "rotation", 90.0),  card._sync_transform(), card.update(), self.props.load(card.data)))
        menu.addAction("Reset Rotation (0°)",      lambda: (setattr(card.data, "rotation", 0.0),   card._sync_transform(), card.update(), self.props.load(card.data)))
        menu.addSeparator()
        menu.addAction("Raise to Front", lambda: card.setZValue(card.zValue()+1))
        menu.addAction("Send to Back",   lambda: card.setZValue(card.zValue()-1))
        menu.addSeparator()
        menu.addAction("Delete",         lambda: self._delete_card(card))
        menu.exec_(screen_pos)

    def _pick_cover(self, card):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Cover", "", IMAGE_FILTER)
        if path:
            card.data.cover_path = path
            card.data.embedded_image = ""
            if hasattr(card, '_reload'): card._reload()
            card.update()

    def _delete_card(self, card):
        self.project.items = [i for i in self.project.items if i.id != card.data.id]
        self.cards_map.pop(card.data.id, None)
        self.scene.removeItem(card)
        self.props.clear()

    # ── project ───────────────────────────────────────────────────────────────

    def _project_settings(self):
        d = SettingsDialog(self.project, self)
        if d.exec_() == QDialog.Accepted:
            v = d.get_values()
            for k, val in v.items(): setattr(self.project, k, val)
            self.setWindowTitle(f"FolioPress — {self.project.title}")
            self._apply_texture()

    def _apply_texture(self):
        p = self.project
        if getattr(p, "texture", "none") == "none":
            self.scene.set_texture(None)
        else:
            base = THEMES.get(p.theme, THEMES["broadsheet"])["bg"]
            self.scene.set_texture(make_texture(p.texture, base, p.texture_path), base)

    def _edit_links(self):
        d = LinkTreeDialog(self.project.links, self)
        if d.exec_() == QDialog.Accepted:
            self.project.links = d.get_links()
            self._on_props_changed()

    def _new_project(self):
        if QMessageBox.question(
            self, "New Project",
            "Start a new project? All unsaved changes will be lost.",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            fresh = Project()
            d = SettingsDialog(fresh, self, "New Portfolio")
            if d.exec_() != QDialog.Accepted:
                return
            for k, val in d.get_values().items():
                setattr(fresh, k, val)
            self.scene.clear()
            self.project    = fresh
            self.cards_map  = {}
            self.props.clear()
            self.setWindowTitle(f"FolioPress — {self.project.title}")
            self._apply_texture()
            self._mark_saved()

    def _open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "FolioPress Project (*.folio.json)")
        if not path: return
        try:
            self.project   = Project.load(path)
            self.cards_map = {}
            self.scene.clear()
            for item in self.project.items:
                card = self.scene.add_card(item)
                self.cards_map[item.id] = card
            self.setWindowTitle(f"FolioPress — {self.project.title}")
            self.status.showMessage(f"Opened: {path}")
            self._apply_texture()
            self._mark_saved()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open project:\n{e}")

    def _mark_saved(self):
        self._saved_snapshot = self.project.snapshot()

    def _is_dirty(self) -> bool:
        return self.project.snapshot() != getattr(self, "_saved_snapshot", None)

    def _save_project(self) -> bool:
        if not self.project.path:
            return self._save_as()
        self.project.save(self.project.path)
        self._mark_saved()
        self.status.showMessage(f"Saved: {self.project.path}")
        return True

    def _save_as(self) -> bool:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project As", "", "FolioPress Project (*.folio.json)")
        if not path:
            return False
        if not path.endswith(".folio.json"): path += ".folio.json"
        self.project.save(path)
        self._mark_saved()
        self.status.showMessage(f"Saved: {path}")
        return True

    # ── export ────────────────────────────────────────────────────────────────

    def export_portfolio(self):
        out = QFileDialog.getExistingDirectory(self, "Export Portfolio To Folder")
        if not out: return
        p = self.project
        note = ""
        wants_pw = any((getattr(i, "pdf_access", "") or p.pdf_access) == "password"
                       for i in p.items if Path(i.file_path or "").suffix.lower() == ".pdf")
        if wants_pw and not p.file_password:
            pw, ok = QInputDialog.getText(self, "File Password",
                                          "Password for the PDF downloads:", QLineEdit.Password)
            if ok and pw:
                p.file_password = pw
            else:
                note = "<br>• No password given — password documents exported as preview only"
        try:
            exporter = HTMLExporter()
            result = exporter.export(p, out, scene=self.scene)
            n_docs = len(exporter._doc_pages)
            msg = QMessageBox(self)
            msg.setWindowTitle("Export Complete!")
            msg.setText(
                f"<b>Portfolio exported successfully.</b><br><br>"
                f"<code>{result}</code><br><br>"
                f"Files:<br>"
                f"• <b>index.html</b> — main portfolio<br>"
                f"{'• <b>links.html</b> — link tree<br>' if self.project.links else ''}"
                f"{f'• <b>doc-*.html</b> — {n_docs} document preview page(s)<br>' if n_docs else ''}"
                f"• <b>assets/</b> — copied images & files"
                f"{note}"
            )
            msg.setStandardButtons(QMessageBox.Open | QMessageBox.Ok)
            if msg.exec_() == QMessageBox.Open:
                import webbrowser
                webbrowser.open(f"file://{os.path.join(result, 'index.html')}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def closeEvent(self, e):
        if self._is_dirty():
            reply = QMessageBox.question(
                self, "Quit FolioPress",
                "Save project before quitting?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            if reply == QMessageBox.Cancel or (reply == QMessageBox.Save and not self._save_project()):
                e.ignore()
                return
        # Document reading is local and quick; never let a running QThread outlive the app
        # (Qt aborts the process, and Windows error reporting then stalls the exit).
        self._doc_jobs = []
        for w in getattr(self, "_url_workers", []):
            w.cancel()
        if self._doc_worker is not None and self._doc_worker.isRunning():
            self._doc_worker.wait(3000)
        e.accept()


# ─── Entry Point ───────────────────────────────────────────────────────────────

def main():
    if sys.platform == "win32":
        # own taskbar button + icon instead of grouping under python.exe
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName("FolioPress")
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("FolioPress")
    app.setDesktopFileName("foliopress")       # Linux: match foliopress.desktop for the dock icon
    app.setWindowIcon(app_icon())

    # slightly nicer default font on Linux/Windows
    font = QFont("Segoe UI", 9) if sys.platform == "win32" else QFont("SF Pro Text", 10)
    app.setFont(font)

    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
