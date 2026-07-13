#!/usr/bin/env python3
"""Remove platform-specific duplicate symbols from a base GIR.

The gobject-introspection port can generate GLib-2.0.gir and Gio-2.0.gir by
scanning all installed headers, including platform-specific headers.  GLib
2.88 generates dedicated GLibWin32-2.0 and GioWin32-2.0 GIRs instead.  When
both namespaces contain the same symbol, PyGObject emits a platform-specific
symbol name-conflict warning.

Usage: python3 filter_glib_gir.py <base.gir> <platform.gir> [output.gir]
"""

import sys
import xml.etree.ElementTree as ET

# GIR namespace URIs and their conventional prefixes.  ElementTree otherwise
# rewrites prefixes as ns0:/ns1: on write, which g-ir-compiler rejects with
# "element ns0:repository from state 1 is unknown" / "Expected namespace
# element in the gir file".  Registering the default (core) namespace with an
# empty prefix keeps <repository> and <namespace> unprefixed as required.
_GIR_NAMESPACES = {
    'http://www.gtk.org/introspection/core/1.0': '',
    'http://www.gtk.org/introspection/c/1.0': 'c',
    'http://www.gtk.org/introspection/doc/1.0': 'doc',
    'http://www.gtk.org/introspection/glib/1.0': 'glib',
}
for _uri, _prefix in _GIR_NAMESPACES.items():
    ET.register_namespace(_prefix, _uri)

C_IDENTIFIER = '{http://www.gtk.org/introspection/c/1.0}identifier'
C_TYPE = '{http://www.gtk.org/introspection/c/1.0}type'


def localname(tag):
    """Strip namespace prefix from an ElementTree tag."""
    return tag.split('}')[-1] if '}' in tag else tag


def namespace(root):
    """Return the first namespace element from a GIR repository."""
    for element in root:
        if localname(element.tag) == 'namespace':
            return element
    raise ValueError('GIR repository does not contain a namespace')


def platform_symbols(platform_namespace):
    """Return C identifiers and types defined by a platform namespace."""
    return {
        attribute: {
            element.get(attribute)
            for element in platform_namespace
            if element.get(attribute)
        }
        for attribute in (C_IDENTIFIER, C_TYPE)
    }


def is_platform_symbol(element, symbols):
    """Return whether a top-level GIR element duplicates a platform symbol."""
    return any(element.get(attribute) in values for attribute, values in symbols.items())


def filter_gir(base_path, platform_path, output_path):
    """Filter platform duplicates from a base GIR using a platform GIR."""
    base_tree = ET.parse(base_path)
    platform_tree = ET.parse(platform_path)
    base_namespace = namespace(base_tree.getroot())
    symbols = platform_symbols(namespace(platform_tree.getroot()))

    removed = 0
    for element in list(base_namespace):
        if is_platform_symbol(element, symbols):
            base_namespace.remove(element)
            removed += 1

    base_tree.write(output_path, encoding='utf-8', xml_declaration=True)
    print(f'Removed {removed} platform element(s) from {base_path} -> {output_path}')
    return removed


if __name__ == '__main__':
    if len(sys.argv) not in (3, 4):
        print(f'Usage: {sys.argv[0]} <base.gir> <platform.gir> [output.gir]', file=sys.stderr)
        sys.exit(1)
    base, platform = sys.argv[1:3]
    output = sys.argv[3] if len(sys.argv) == 4 else base
    filter_gir(base, platform, output)
