#!/usr/bin/env python3
"""
One-shot rebuild of every FolioPress release.

    python rebuild.py              # clean, then Windows zip + installer, then Linux (Docker)
    python rebuild.py --no-linux   # skip the Linux build

Results land in release/. First run sets up .venv-build/ (a clean Python for
PyInstaller), later runs reuse it.
"""

import argparse, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv-build"
VPY = VENV / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
GENERATED = ["build", "dist", "release", "__pycache__", "packaging/version_info.txt"]


def step(msg):
    print(f"\n=== {msg}", flush=True)


def run(*cmd):
    subprocess.run([str(c) for c in cmd], check=True, cwd=ROOT)


def clean():
    step("Cleaning")
    for name in GENERATED:
        p = ROOT / name
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()


def ensure_venv():
    if not VPY.exists():
        step("Creating .venv-build")
        run(sys.executable, "-m", "venv", VENV)
    step("Installing build dependencies")
    run(VPY, "-m", "pip", "install", "-q", "--upgrade", "pip")
    run(VPY, "-m", "pip", "install", "-q", "-r", "requirements.txt", "pyinstaller", "pillow")


def build_native():
    if sys.platform == "win32":
        step("Building Windows (zip + installer)")
        run(VPY, "packaging/build.py", "--installer")
    else:
        step("Building for this OS")
        run(VPY, "packaging/build.py")


def build_linux():
    step("Building Linux (Docker, Ubuntu 22.04)")
    docker = shutil.which("docker")
    if not docker or subprocess.run([docker, "info"], capture_output=True).returncode != 0:
        print("Docker isn't running — skipped. Start Docker Desktop and run again for the Linux build.")
        return False
    run(docker, "run", "--rm", "-v", f"{ROOT}:/src", "-w", "/src",
        "ubuntu:22.04", "sh", "packaging/build-linux.sh")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-linux", action="store_true", help="skip the Linux build")
    args = ap.parse_args()

    clean()
    ensure_venv()
    build_native()
    if sys.platform == "win32" and not args.no_linux:
        build_linux()          # build.py clears dist/ itself; release/ keeps the Windows files

    step("Done")
    for f in sorted((ROOT / "release").glob("*")):
        print(f"  {f.name:48} {f.stat().st_size / 1e6:6.1f} MB")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        sys.exit(f"\nBuild failed at: {' '.join(map(str, e.cmd))}")
