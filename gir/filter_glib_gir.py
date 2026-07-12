#!/usr/bin/env python3
"""Remove GLibWin32-specific symbols from GLib-2.0.gir to avoid
PyGObject "Name conflict for platform-specific symbol" warnings.

The gobject-introspection port generates GLib-2.0.gir by scanning ALL
installed glib headers, including gwin32.h.  This means GLib-2.0.gir
contains g_win32_* functions and the GWin32OSType enum that also appear
in our hand-written GLibWin32-2.0.gir.  When both typelibs are loaded,
PyGObject 3.56.3 emits "Name conflict" PyGIWarning messages for each
duplicate symbol (see pygobject bug #760).

In a normal glib 2.88.0 build with introspection=enabled, glib's own
meson build removes these symbols from GLib-2.0.gir (MR !4881).  We
replicate that by filtering them out post-build.

Symbols to remove (defined in glib/gwin32.h):
  - Functions with c:identifier starting with "g_win32_" EXCEPT:
    - g_io_channel_win32_* (defined in giochannel.h, stays in GLib)
    - g_win32_get_system_data_dirs_for_module (defined in gutils.h, stays in GLib)
  - The GWin32OSType enumeration (c:type="GWin32OSType")
  - Function macros G_WIN32_HAVE_WIDECHAR_API, G_WIN32_IS_NT_BASED,
    G_WIN32_DLLMAIN_FOR_DLL_NAME

Usage: python3 filter_glib_gir.py <GLib-2.0.gir> [output.gir]
"""

import sys
import xml.etree.ElementTree as ET

# Symbols to remove from GLib-2.0.gir (defined in gwin32.h, now in GLibWin32-2.0.gir)
WIN32_C_IDENTIFIERS = {
    'g_win32_ftruncate',
    'g_win32_getlocale',
    'g_win32_error_message',
    'g_win32_get_package_installation_directory',
    'g_win32_get_package_installation_subdirectory',
    'g_win32_get_package_installation_directory_of_module',
    'g_win32_get_windows_version',
    'g_win32_locale_filename_from_utf8',
    'g_win32_get_command_line',
    'g_win32_check_windows_version',
}

WIN32_MACRO_C_IDENTIFIERS = {
    'G_WIN32_HAVE_WIDECHAR_API',
    'G_WIN32_IS_NT_BASED',
    'G_WIN32_DLLMAIN_FOR_DLL_NAME',
}

# Namespace URIs used in GIR files
NS = {
    '': 'http://www.gtk.org/introspection/core/1.0',
    'c': 'http://www.gtk.org/introspection/c/1.0',
    'glib': 'http://www.gtk.org/introspection/glib/1.0',
}


def localname(tag):
    """Strip namespace prefix from an ElementTree tag."""
    return tag.split('}')[-1] if '}' in tag else tag


def should_remove(elem):
    """Check if an element should be removed from GLib-2.0.gir."""
    name = localname(elem.tag)

    if name == 'function':
        cid = elem.get('{http://www.gtk.org/introspection/c/1.0}identifier', '')
        if cid in WIN32_C_IDENTIFIERS:
            return True

    if name == 'function-macro':
        cid = elem.get('{http://www.gtk.org/introspection/c/1.0}identifier', '')
        if cid in WIN32_MACRO_C_IDENTIFIERS:
            return True

    if name == 'enumeration':
        ctype = elem.get('{http://www.gtk.org/introspection/c/1.0}type', '')
        if ctype == 'GWin32OSType':
            return True

    return False


def filter_gir(input_path, output_path):
    """Filter win32 symbols from a GLib-2.0.gir file."""
    tree = ET.parse(input_path)
    root = tree.getroot()

    removed = 0
    for ns_elem in root:
        if localname(ns_elem.tag) != 'namespace':
            continue
        to_remove = []
        for child in list(ns_elem):
            if should_remove(child):
                to_remove.append(child)
        for elem in to_remove:
            ns_elem.remove(elem)
            removed += 1

    tree.write(output_path, encoding='utf-8', xml_declaration=True)
    print(f"Removed {removed} win32 element(s) from {input_path} -> {output_path}")
    return removed


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <GLib-2.0.gir> [output.gir]", file=sys.stderr)
        sys.exit(1)
    inp = sys.argv[1]
    outp = sys.argv[2] if len(sys.argv) > 2 else inp
    filter_gir(inp, outp)
