# PyInstaller spec — one-folder build of FolioPress.
#   pyinstaller packaging/foliopress.spec --noconfirm
# (packaging/build.py runs this and archives the result.)

import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
ICON = ROOT / "branding" / ("foliopress.icns" if sys.platform == "darwin" else "foliopress.ico")

a = Analysis(
    [str(ROOT / "foliopress.py")],
    pathex=[str(ROOT)],
    datas=[(str(ROOT / "branding" / "icons"), "branding/icons"),
           (str(ROOT / "links.json"), ".")],
    excludes=["tkinter", "unittest", "pydoc", "PyQt5.QtWebEngineWidgets",
              "PyQt5.QtWebEngineCore", "PyQt5.QtQml", "PyQt5.QtQuick", "PyQt5.QtMultimedia"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="FolioPress",
    icon=str(ICON),
    console=False,
    upx=False,
    version=str(ROOT / "packaging" / "version_info.txt") if sys.platform == "win32" else None,
)

coll = COLLECT(exe, a.binaries, a.datas, name="FolioPress", upx=False)

if sys.platform == "darwin":
    app = BUNDLE(coll, name="FolioPress.app", icon=str(ICON),
                 bundle_identifier="com.zeffiroh.foliopress")
