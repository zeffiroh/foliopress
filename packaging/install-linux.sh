#!/bin/sh
# Install FolioPress for the current user: app in ~/.local/opt, launcher in the app menu.
# Run from the unpacked release folder:  ./install-linux.sh    (./install-linux.sh --uninstall to remove)
set -e

HERE=$(cd "$(dirname "$0")" && pwd)
PREFIX="${XDG_DATA_HOME:-$HOME/.local/share}"
OPT="$HOME/.local/opt/foliopress"
BIN="$HOME/.local/bin"

if [ "$1" = "--uninstall" ]; then
    rm -rf "$OPT" "$BIN/foliopress" "$PREFIX/applications/foliopress.desktop"
    for d in "$PREFIX"/icons/hicolor/*/apps/foliopress.png; do rm -f "$d"; done
    echo "FolioPress removed."
    exit 0
fi

rm -rf "$OPT"
mkdir -p "$OPT" "$BIN" "$PREFIX/applications"
cp -r "$HERE"/. "$OPT"/
ln -sf "$OPT/FolioPress" "$BIN/foliopress"

for png in "$HERE"/icons/*.png; do
    s=$(basename "$png" .png)
    mkdir -p "$PREFIX/icons/hicolor/${s}x${s}/apps"
    cp "$png" "$PREFIX/icons/hicolor/${s}x${s}/apps/foliopress.png"
done

sed "s|^Exec=.*|Exec=$OPT/FolioPress %F|" "$HERE/foliopress.desktop" > "$PREFIX/applications/foliopress.desktop"
command -v update-desktop-database >/dev/null && update-desktop-database "$PREFIX/applications" || true
command -v gtk-update-icon-cache  >/dev/null && gtk-update-icon-cache -q "$PREFIX/icons/hicolor" || true

echo "FolioPress installed - find it in your app menu, or run: foliopress"
