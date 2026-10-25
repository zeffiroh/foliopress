# FolioPress - Portfolio Builder

A desktop Python app that turns your hard drive files into a rich, typeset portfolio website.

---

## Quick Start

**Download:** grab the latest build from [Releases](../../releases/latest)
- **Windows** — `…-windows-x64-setup.exe` (installer) or `…-windows-x64.zip` (portable: unzip, run `FolioPress.exe`)
- **Linux** — `…-linux-x64.tar.gz`: unpack, then `./install-linux.sh` (adds it to your app menu) or just `./FolioPress`

**From source:**

```bash
pip install -r requirements.txt
python foliopress.py
```

---

## Features

### 📁 File Browser (left panel)
- **Open Folder** — browse any folder on your drive
- Filter bar to find files quickly
- **Double-click** a file → adds it to canvas at a default position
- **Select multiple** files (Ctrl/Shift+click) then **"Add Selected → Canvas"**
- **"Add All Files → Canvas"** — pulls every supported file from the folder and BSP-auto-arranges them

### 🖼 Canvas (center)
- **Drag files from the file browser or from your OS** straight onto the canvas
- **Middle-mouse button** to pan; **scroll wheel** to zoom in/out
- **Ctrl+0** to fit everything on screen
- **Rubber-band drag** to select multiple cards at once
- **Ctrl+A** to select all

### ⊞ Snap-to-Grid
- Grid is 20 px by default, shown as dots on the canvas
- Toggle with the **Snap** button or **Ctrl+G**
- All moves and resizes snap automatically when enabled

### ↔ Card Types
| Card | Use for |
|------|---------|
| 📷 Image | Photos, illustrations, renders |
| 📄 Article | PDFs, docs — with thumbnail + body text |
| ✏ Text | Prose blocks, bios, artist statements |
| 🔗 URL | Links that generate a clickable card |

Each card is **resizable** by dragging the blue handle in the bottom-right corner.

### 📥 Import (PDF · RTF · TXT)
- **PDF** → article with headline (PDF title, or the largest type on page 1), kicker (keywords/author), standfirst (the Abstract section, or the first real paragraph) and cover (largest real picture on the first pages — no page previews). Reading happens in the background; the card appears at once and fills in
- **RTF / TXT / MD** → article with headline and standfirst
- The body starts empty: **📑 Extract Text…** shows the full document; select passages and add them to the body, headline, standfirst, kicker, or a new text box

### 🖼 Images & Drawing
- **📷 Image** opens the drawing canvas: draw from scratch, or **Open / Place / Paste** a picture and edit it
- Tools: pen, soft brush, highlighter, spray, eraser, line, arrow, rectangle, ellipse (Shift = straight / square / circle), fill, text, colour picker, crop
- Colour + fill colour (X swaps), swatches, size (`[` `]`), opacity, filled shapes, fill tolerance, font
- Undo / redo, rotate, flip, resize, clear, new canvas; zoom with Ctrl+wheel, Fit, 100 %
- An opened file you don't change is kept as the original (high-res) file
- **⇄ Replace** swaps an image card's picture or an article's PDF/RTF/TXT; **✎ Edit Image** reopens the editor
- **High-res vs web:** the site only ever gets a web-size copy (1600 px long side). Clicking a picture opens its page with that copy and **✉ Request high resolution**. Set an **Opens** URL to link elsewhere instead

### ❝ Quote, ▬ Kicker, ♥ Heart
- **❝ Quote** — pull quote with attribution
- **▬ Kicker** — a standalone strapline
- **♥ Heart** — your donate button as a box in the layout (asks for the donate link the first time)

### 🔲 Auto-Layouts
- **BSP Layout (All)** — Binary Space Partitioning fills the canvas intelligently, sizing cards to fill their region
- **BSP Layout (Selected)** — BSP only the cards you've selected
- **Align Left / Top** — snap selected cards to a common edge
- **Stack Vertical** — arrange selected cards top-to-bottom
- **Raise / Send Back** — control z-order via Edit menu or right-click

### ⚙ Properties Panel (right)
Opens when you click a card and hides when nothing is selected. **⧉** floats it as its own window (double-click the bar too), **▾** collapses it (to a thin strip when docked), **✕** closes it; View ▸ Properties brings it back. Style, Rotation and Size & Position fold away.

Shows only what the selected card type uses:

| Card | Fields | Actions |
|------|--------|---------|
| Image | Title, Opens (URL), Email, Links, Caption | Replace Image, Edit Image |
| Article | Kicker, Headline, Standfirst, Link, Email, Document access, Links, Body | Replace / Attach Document, Extract Text, Set Cover, Edit Cover, Split into Group |
| Text | Kicker, Title, URL, Email, Links, Text | Text from File (pick passages) |
| Link | Kicker, Name, Address, Email, Links, Description | Fetch Title & Description |
| Link Tree | Title | Edit Link Tree |
| Quote | Quote, Attribution, Source, Email, Links | |
| Heart | Button, Message, Donate link (blank → portfolio's) | |
| Kicker / Headline / Standfirst | their text, URL, Email, Links | Lock / Merge / Detach when grouped |

- **Email** — a ✉ Contact button on the card; on a document it's also where requests go (blank → portfolio email)
- **Document** — this document's access (blank → the portfolio's Documents setting)
- **Links** — `Label | url`, one per line, shown as chips on the card
- Style, rotation, size and position are below (no typography for pictures)

Press **✓ Apply** to update the card visual.

### 🌐 Portfolio Settings (Edit menu)
- Portfolio title, author name, tagline
- Introduction / About text (multi-paragraph, displayed as 2-column newspaper intro)
- **Theme**: Newspaper · Tabloid · Magazine · Academic · Editorial

### 🔗 Link Tree
- **🌳 Link Tree** (toolbar) adds a link-tree box to the layout; double-click it to edit Label + URL + Description
- **⟳ Fetch Previews** pulls each page's favicon, title, description and preview image; YouTube, Vimeo, Spotify, SoundCloud and pages that declare a player get an embedded player (untick **Preview** for a plain row)
- Exported as a box in the page plus `links.html`: profile (name, tagline, email), link cards, and a **Files** list of the portfolio's documents
- Players need the site to be hosted — YouTube refuses to play from a page opened as a local file

### 👤 Name, Email, Documents, Donate
- Asked when you create a new portfolio (also under Edit ▸ Portfolio Settings)
- Email shows in the masthead and on the link page
- **Documents** — what clicking a document card opens:
  - *Preview only* — a page with the first 3 pages (or an excerpt), the card's links and a **✉ Request the full document** email button. The file itself is not published
  - *Preview + password download* — adds the PDF, encrypted with AES-256 under your **File Password**
  - *Preview + open download* — adds a plain copy
- **Request Email** — where requests go (blank → your Email)
- **File Password** is not saved in the project file; export asks for it if it's missing
- **Donate Link** (Ko-fi, PayPal, Buy Me a Coffee…) + button text → a ♥ button in the masthead, on the link page and on every document / picture page
- **Background** — Paper, Newsprint, Linen, Canvas, Graph Paper, Dots or your own image, tiled behind the portfolio (and shown on the canvas)

### ❔ Help ▸ About
- **About FolioPress** — version, developer, contact links
- **♥ Support FolioPress** — opens the developer's support page (`support` in `links.json`)
- Logo and support badge live in `branding/`

---

## Exporting

**Toolbar → 🚀 Export HTML** or **Ctrl+E**

Export always re-runs the BSP layout first, so the page is the packed BSP arrangement. Choose an output folder. FolioPress creates:

```
my-portfolio/
├── index.html       ← main newspaper-style portfolio
├── links.html       ← link tree (if you added links)
├── doc-….html       ← one preview page per document
├── img-….html       ← one page per picture (web size + high-res request)
└── assets/          ← web-size images, page previews, downloads
```

Assets are named by a hash of their contents (`3f9a…c2.jpg`), so each file is stored once. Image cards open the full image. Article cards — and every piece of a split article group — open the document's preview page.

Open `index.html` in any browser. Upload the whole folder to GitHub Pages, Netlify, or any host.

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Ctrl+N | New project |
| Ctrl+O | Open project |
| Ctrl+S | Save project |
| Ctrl+E | Export portfolio |
| Ctrl+G | Toggle snap-to-grid |
| Ctrl+0 | Fit canvas |
| Ctrl+= | Zoom in |
| Ctrl+- | Zoom out |
| Ctrl+A | Select all |
| Delete | Delete selected |
| Middle drag | Pan canvas |
| Scroll wheel | Zoom |

---

## Supported File Types

| Type | Extensions |
|------|-----------|
| Images | .jpg .jpeg .png .gif .webp .bmp .tiff .svg |
| Documents | .pdf .doc .docx .txt .md .rtf .odt |

---

## Themes

Newspaper · Tabloid · Magazine · Academic · Editorial

---

## Building & Releasing

```bash
python rebuild.py             # clean + Windows zip & installer + Linux (Docker) → release/
python rebuild.py --no-linux  # skip Linux
```

It builds in its own `.venv-build/` (PyInstaller bundles every package it can see, and extra Qt bindings like PyQt6 abort the build). The Windows installer needs Inno Setup 6; the Linux build needs Docker Desktop running.

---

## Saving Your Project

Projects are saved as `.folio.json` — a plain JSON file that stores all card data and settings. Asset files (images, PDFs) are referenced by their original paths, so keep them in place until you export.

On export, all assets are copied into the `assets/` folder, making the output self-contained.
