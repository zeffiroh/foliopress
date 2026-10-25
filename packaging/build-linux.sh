#!/bin/sh
# Build the Linux release inside an Ubuntu 22.04 container (glibc 2.35), so it runs on
# Ubuntu 22.04+, Debian 12+, Fedora 36+, Mint 21+. Used by CI and for local builds:
#
#   docker run --rm -v "$PWD:/src" -w /src ubuntu:22.04 sh packaging/build-linux.sh
#
# Output: release/FolioPress-<ver>-linux-x64.tar.gz
set -e
export DEBIAN_FRONTEND=noninteractive

apt-get update -qq
# python + binutils (PyInstaller's dependency scan) · the rest: libraries Qt loads at runtime
apt-get install -y -qq --no-install-recommends \
    python3 python3-venv python3-pip libpython3.10 binutils \
    libgl1 libegl1 libglib2.0-0 libfontconfig1 libdbus-1-3 \
    libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
    libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 libxcb-xkb1 libxcb-xfixes0 > /dev/null

# a venv outside /src, so the mounted project folder stays clean
python3 -m venv /opt/build-venv
PY=/opt/build-venv/bin/python
$PY -m pip install -q --upgrade pip
$PY -m pip install -q -r requirements.txt pyinstaller pillow
$PY packaging/build.py
