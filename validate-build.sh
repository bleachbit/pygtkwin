#!/usr/bin/env bash
# Validate that the vcpkg build produced expected key files.
# Usage: ./validate-build.sh <vcpkg_installed_triplet_dir>
# Example: ./validate-build.sh vcpkg/installed/x86-windows
set -euo pipefail

dir="${1:?usage: $0 <triplet_dir>}"
bindir="$dir/bin"

if [ ! -d "$bindir" ]; then
    echo "ERROR: bin directory not found: $bindir" >&2
    exit 1
fi

errors=0

check_glob() {
    local pattern="$1" label="$2" subdir="$3"
    local searchdir="$dir/$subdir"
    local found
    found=$(find "$searchdir" -name "$pattern" -type f 2>/dev/null || true)
    if [ -z "$found" ]; then
        echo "FAIL: $label not found (pattern: $pattern in $searchdir)"
        errors=$((errors + 1))
    else
        echo "OK:   $label -> ${found#$dir/}"
    fi
}

echo "=== Build validation: $bindir ==="

check_glob 'python.exe'           'python.exe'           'tools/python3'
check_glob 'gdbus.exe'            'gdbus.exe'            'tools/glib'
check_glob 'rsvg-*.dll'           'librsvg DLL'          'bin'
check_glob 'croco-*.dll'          'libcroco DLL'         'bin'
check_glob 'gdk_pixbuf-*.dll'     'gdk-pixbuf DLL'       'bin'
check_glob 'pixbufloader-svg.dll' 'pixbufloader-svg DLL' 'lib/gdk-pixbuf-2.0/2.10.0/loaders'
check_glob 'cairo*.dll'           'cairo DLL'            'bin'
check_glob 'glib-*.dll'           'glib DLL'             'bin'
check_glob 'libxml2.dll'          'libxml2 DLL'          'bin'

echo "=== Validation complete: $errors error(s) ==="

if [ "$errors" -gt 0 ]; then
    exit 1
fi
