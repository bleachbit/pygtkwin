#!/bin/bash

set -e
set -x

current_dir=$(pwd)
work_dir=$(mktemp -d --suffix=gtktheme)
cd $work_dir

download_and_extract() {
    local url="$1"
    local filename="${url##*/}"

    wget -q "$url" -O "$filename" || { echo "Failed to download $filename"; exit 1; }
    sha256sum "$filename"
    tar -xf "$filename"
    rm "$filename"
}

ADAWAITA_VERSION=47.0
ADAWAITA_URL="https://download.gnome.org/sources/adwaita-icon-theme/47/adwaita-icon-theme-${ADAWAITA_VERSION}.tar.xz"
download_and_extract $ADAWAITA_URL
mkdir -p gtk-themes/share/icons
mv adwaita-icon-theme-${ADAWAITA_VERSION}/Adwaita gtk-themes/share/icons
cp adwaita-icon-theme-${ADAWAITA_VERSION}/index.theme gtk-themes/share/icons/Adwaita/index.theme

# Adwaita 47+ split legacy (fullcolor) icons into a separate package.
# The main index.theme inherits AdwaitaLegacy, so both are required.
ADAWAITA_LEGACY_VERSION=46.2
ADAWAITA_LEGACY_URL="https://download.gnome.org/sources/adwaita-icon-theme-legacy/46/adwaita-icon-theme-legacy-${ADAWAITA_LEGACY_VERSION}.tar.xz"
download_and_extract $ADAWAITA_LEGACY_URL
mv adwaita-icon-theme-legacy-${ADAWAITA_LEGACY_VERSION}/AdwaitaLegacy gtk-themes/share/icons
cp adwaita-icon-theme-legacy-${ADAWAITA_LEGACY_VERSION}/index.theme gtk-themes/share/icons/AdwaitaLegacy/index.theme

# hicolor is the ultimate fallback icon theme.
HICOLOR_VERSION=0.17
HICOLOR_URL="https://icon-theme.freedesktop.org/releases/hicolor-icon-theme-${HICOLOR_VERSION}.tar.xz"
download_and_extract $HICOLOR_URL
mkdir -p gtk-themes/share/icons/hicolor
cp hicolor-icon-theme-${HICOLOR_VERSION}/index.theme gtk-themes/share/icons/hicolor/index.theme

GTK_VER=3.24.52
GTK_URL="https://download.gnome.org/sources/gtk/3.24/gtk-$GTK_VER.tar.xz"
download_and_extract $GTK_URL
cd gtk-$GTK_VER/gtk/theme/Adwaita || { echo "Failed to cd into Adwaita"; exit 1; }
./parse-sass.sh
if [ ! -f gtk-contained.css ]; then
    echo "Error: gtk-contained.css not found"
    exit 1
fi
cd $work_dir
mkdir -p gtk-themes/share/themes/Adwaita/gtk-3.0
mv gtk-$GTK_VER/gtk/theme/Adwaita/gtk-contained.css gtk-themes/share/themes/Adwaita/gtk-3.0/gtk.css
cp gtk-$GTK_VER/gtk/theme/Adwaita/gtk-contained-dark.css gtk-themes/share/themes/Adwaita/gtk-3.0/gtk-dark.css
cp -r gtk-$GTK_VER/gtk/theme/Adwaita/assets gtk-themes/share/themes/Adwaita/gtk-3.0/assets

# GTK expects a theme index.theme; BleachBit's installer also checks for it.
cat > gtk-themes/share/themes/Adwaita/index.theme << 'EOF'
[X-GNOME-Metatheme]
Name=Adwaita
Type=X-GNOME-Metatheme
Comment=There is only one
Encoding=UTF-8
GtkTheme=Adwaita
MetacityTheme=Adwaita
IconTheme=Adwaita
CursorTheme=Adwaita
CursorSize=24
EOF

GNOME_THEMES_VER=3.28
GTKTHEMES_URL="https://download.gnome.org/sources/gnome-themes-extra/3.28/gnome-themes-extra-$GNOME_THEMES_VER.tar.xz"
download_and_extract $GTKTHEMES_URL
mkdir -p gtk-themes/share/icons/HighContrast
rm gnome-themes-extra-${GNOME_THEMES_VER}/themes/HighContrast/icons/scalable/Makefile.am
mv gnome-themes-extra-${GNOME_THEMES_VER}/themes/HighContrast/icons/scalable gtk-themes/share/icons/HighContrast
cp gnome-themes-extra-${GNOME_THEMES_VER}/themes/HighContrast/icons/index.theme gtk-themes/share/icons/HighContrast/index.theme

7za a -tzip -mx=9 -mfb=258 -mpass=15 "$current_dir/gtk-themes.zip" gtk-themes
du -b "$current_dir/gtk-themes.zip"
sha256sum "$current_dir/gtk-themes.zip"
