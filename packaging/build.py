#!/usr/bin/env python3
"""
Build a FolioPress release for the current OS.

    python packaging/build.py            # → release/FolioPress-<ver>-<os>-<arch>.(zip|tar.gz)
    python packaging/build.py --installer   # Windows: also the Inno Setup installer

Needs: pip install -r requirements.txt pyinstaller pillow
"""

import argparse, json, platform, re, shutil, subprocess, sys, tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "packaging"
DIST, BUILD, RELEASE = ROOT / "dist", ROOT / "build", ROOT / "release"


def app_version():
    m = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', (ROOT / "foliopress.py").read_text("utf-8"), re.M)
    return m.group(1)


def os_tag():
    return {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")


def arch_tag():
    m = platform.machine().lower()
    return {"amd64": "x64", "x86_64": "x64", "aarch64": "arm64"}.get(m, m)


def write_version_info(ver):
    """Windows file properties (Explorer ▸ Properties ▸ Details)."""
    nums = (ver.split(".") + ["0"] * 4)[:4]
    tup = ", ".join(str(int(re.sub(r"\D.*", "", n) or 0)) for n in nums)
    (PKG / "version_info.txt").write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({tup}), prodvers=({tup})),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Mitali Aayat Mahnoor Sharma'),
      StringStruct('FileDescription', 'FolioPress - algorithmic portfolio builder'),
      StringStruct('FileVersion', '{ver}'),
      StringStruct('InternalName', 'FolioPress'),
      StringStruct('LegalCopyright', '© Mitali Aayat Mahnoor Sharma'),
      StringStruct('OriginalFilename', 'FolioPress.exe'),
      StringStruct('ProductName', 'FolioPress'),
      StringStruct('ProductVersion', '{ver}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""", "utf-8")


def run(*cmd):
    print(">>", " ".join(map(str, cmd)), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, cwd=ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--installer", action="store_true", help="Windows: build the Inno Setup installer too")
    args = ap.parse_args()

    ver = app_version()
    name = f"FolioPress-{ver}-{os_tag()}-{arch_tag()}"
    if sys.platform == "win32":
        write_version_info(ver)

    if not (ROOT / "branding" / "foliopress.ico").exists():
        run(sys.executable, PKG / "make_icons.py")
    shutil.rmtree(DIST, ignore_errors=True)
    shutil.rmtree(BUILD, ignore_errors=True)
    run(sys.executable, "-m", "PyInstaller", PKG / "foliopress.spec", "--noconfirm",
        "--distpath", DIST, "--workpath", BUILD)

    app_dir = DIST / "FolioPress"
    shutil.copy(ROOT / "LICENSE", app_dir / "LICENSE.txt")
    RELEASE.mkdir(exist_ok=True)
    if sys.platform.startswith("linux"):
        shutil.copy(PKG / "foliopress.desktop", app_dir)
        shutil.copy(PKG / "install-linux.sh", app_dir)
        shutil.copytree(ROOT / "branding" / "icons", app_dir / "icons", dirs_exist_ok=True)
        out = RELEASE / f"{name}.tar.gz"
        def exec_bits(ti):           # a checkout from Windows loses +x
            if ti.name.endswith(("/FolioPress", "/install-linux.sh")) or ti.isdir():
                ti.mode = 0o755
            return ti
        with tarfile.open(out, "w:gz") as tf:
            tf.add(app_dir, arcname=name, filter=exec_bits)
    else:
        out = Path(shutil.make_archive(str(RELEASE / name), "zip", DIST, "FolioPress"))
    print("built:", out)

    if args.installer and sys.platform == "win32":
        candidates = [shutil.which("iscc"),
                      Path.home() / "AppData/Local/Programs/Inno Setup 6/ISCC.exe",   # winget --scope user
                      Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe")]
        iscc = next((str(c) for c in candidates if c and Path(c).exists()), None)
        if not iscc:
            sys.exit("Inno Setup not found — install it from https://jrsoftware.org/isdl.php")
        links = json.loads((ROOT / "links.json").read_text("utf-8"))
        app_url = links.get("website") or links.get("github") or ""
        run(iscc, f"/DAppVersion={ver}", f"/DOutputName=FolioPress-{ver}-windows-{arch_tag()}-setup",
            f"/DAppURL={app_url}", PKG / "foliopress.iss")


if __name__ == "__main__":
    main()
