#!/usr/bin/env python3
"""
Generate the GTK3 debloat patch from gtk3-debloat.json.

Usage:
    python3 generate_gtk3_debloat.py

This script:
  1. Downloads and extracts the GTK3 source tarball.
  2. Applies all debloat changes described in gtk3-debloat.json.
  3. Generates a git diff (the GTK source patch).
  4. Creates the vcpkg portfile patch (adds the source patch + meson options).
  5. Writes the combined patch to 0003-vcpkg-gtk3-debloat.patch.

The generated patch is committed to the repo and applied at build time.
To update the debloat configuration, edit gtk3-debloat.json and re-run this script.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(SCRIPT_DIR, "gtk3-debloat.json")
OUTPUT_PATCH = os.path.join(SCRIPT_DIR, "0003-vcpkg-gtk3-debloat.patch")


def run(cmd, cwd=None, check=True):
    """Run a command and return its output."""
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Command failed: {' '.join(cmd)}", file=sys.stderr)
        print(f"stdout: {result.stdout}", file=sys.stderr)
        print(f"stderr: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result


def download_and_extract_gtk(version, work_dir):
    """Download and extract the GTK source tarball."""
    url = f"https://download.gnome.org/sources/gtk/3.24/gtk-{version}.tar.xz"
    tarball = os.path.join(work_dir, f"gtk-{version}.tar.xz")
    print(f"Downloading {url}...")
    urllib.request.urlretrieve(url, tarball)
    print("Extracting...")
    run(["tar", "xf", tarball], cwd=work_dir)
    src_dir = os.path.join(work_dir, f"gtk-{version}")
    return src_dir


def init_git_repo(src_dir):
    """Initialize a git repo in the source dir so we can diff."""
    run(["git", "init"], cwd=src_dir)
    run(["git", "add", "-A"], cwd=src_dir)
    run(["git", "commit", "-m", "gtk upstream", "--quiet",
         "--allow-empty"], cwd=src_dir)
    # Set author so diff doesn't show author warnings
    run(["git", "config", "user.email", "debloat@local"], cwd=src_dir)
    run(["git", "config", "user.name", "Debloat"], cwd=src_dir)


def remove_line_from_file(file_path, line_content):
    """Remove a line containing line_content from file_path."""
    with open(file_path, 'r') as f:
        lines = f.readlines()
    new_lines = [l for l in lines if line_content not in l]
    if len(new_lines) == len(lines):
        print(f"  WARNING: '{line_content}' not found in {file_path}")
    with open(file_path, 'w') as f:
        f.writelines(new_lines)


def remove_lines_matching(file_path, patterns):
    """Remove all lines containing any of the given patterns from file_path."""
    with open(file_path, 'r') as f:
        lines = f.readlines()
    new_lines = [l for l in lines if not any(p in l for p in patterns)]
    removed = len(lines) - len(new_lines)
    if removed == 0:
        print(f"  WARNING: no matches for {patterns} in {file_path}")
    with open(file_path, 'w') as f:
        f.writelines(new_lines)


def stub_function(file_path, function_name, replacement_body):
    """Replace a function body with a stub.

    Finds the function definition and replaces everything between
    the opening brace and closing brace with replacement_body.
    """
    with open(file_path, 'r') as f:
        content = f.read()

    # Match: function_name(...) ... { ... }
    # We look for the function signature, then find the opening brace,
    # then replace everything up to the matching closing brace.
    # This is a simple approach that works for functions with balanced braces.
    pattern = rf'({re.escape(function_name)}\s*\([^)]*\)\s*)\{{'

    match = re.search(pattern, content)
    if not match:
        print(f"  WARNING: function '{function_name}' not found in {file_path}")
        return

    # Find the matching closing brace
    brace_start = match.end() - 1  # position of opening {
    depth = 0
    i = brace_start
    while i < len(content):
        if content[i] == '{':
            depth += 1
        elif content[i] == '}':
            depth -= 1
            if depth == 0:
                break
        i += 1

    if depth != 0:
        print(f"  WARNING: unbalanced braces for '{function_name}' in {file_path}")
        return

    # Replace the function body
    # Keep the signature, replace the body
    sig_end = match.end() - 1  # position before {
    new_content = content[:sig_end] + replacement_body + content[i+1:]

    with open(file_path, 'w') as f:
        f.write(new_content)


def replace_in_file(file_path, old, new):
    """Replace old with new in file_path."""
    with open(file_path, 'r') as f:
        content = f.read()
    if old not in content:
        print(f"  WARNING: '{old}' not found in {file_path}")
        return
    content = content.replace(old, new)
    with open(file_path, 'w') as f:
        f.write(content)


def apply_gresource_changes(gtk_dir, config):
    """Modify gen-gtk-gresources-xml.py to exclude resources."""
    gen_script = os.path.join(gtk_dir, "gtk", "gen-gtk-gresources-xml.py")
    with open(gen_script, 'r') as f:
        content = f.read()

    # 1. Remove themes (e.g. HighContrast)
    for theme in config.get("remove_themes", []):
        # Remove the theme CSS block
        theme_css_pattern = rf"xml \+= '''\n    <file>theme/{theme}/gtk\.css</file>\n.*?'''\n\n"
        content = re.sub(theme_css_pattern, '', content, flags=re.DOTALL)

        # Remove theme asset loops
        for ext in ['.png', '.svg']:
            asset_pattern = rf"for f in get_files\('theme/{theme}/assets', '{ext}'\):\n  xml \+= '    <file>theme/{theme}/assets/\{{0\}}</file>\\n'\.format\(f\)\n\n?"
            content = re.sub(asset_pattern, '', content)

        # Remove any remaining theme references
        content = re.sub(rf"    <file[^>]*>theme/{theme}/[^<]+</file>\n", '', content)
        content = re.sub(rf"    <file[^>]*alias='theme/{theme}[^>]+>[^<]+</file>\n", '', content)

    # 2. Exclude .ui files
    exclude_ui = config.get("exclude_ui", [])
    if exclude_ui:
        # Build the excluded_ui set and the filter
        ui_set_lines = "\n".join(f"    '{ui}'," for ui in sorted(exclude_ui))
        old_ui_loop = "for f in get_files('ui', '.ui'):\n  xml += '    <file preprocess=\\'xml-stripblanks\\'>ui/{0}</file>\\n'.format(f)"
        new_ui_block = f"""# Exclude .ui files for widgets not used by BleachBit and for platform-
# inappropriate dialogs (Unix print dialogs, macOS quartz application).
# The corresponding C source is either not compiled on Windows (printunix,
# quartz) or never instantiated by BleachBit (emoji, font/color/app chooser,
# assistant, recent chooser, volume button, search bar, lock button, action
# bar).  Removing the template resources saves .rdata in the shared library.
excluded_ui = {{
{ui_set_lines}
}}

for f in get_files('ui', '.ui'):
  if f in excluded_ui:
    continue
  xml += '    <file preprocess=\\'xml-stripblanks\\'>ui/{{0}}</file>\\n'.format(f)"""
        content = content.replace(old_ui_loop, new_ui_block)

    # 3. Remove inspector .ui files + logo
    if config.get("remove_inspector"):
        # Remove the inspector .ui loop
        content = re.sub(
            r"for f in get_files\('inspector', '\.ui'\):\n  xml \+= '    <file compressed=\\'true\\' preprocess=\\'xml-stripblanks\\'>inspector/\{0\}</file>\\n'\.format\(f\)\n\n?",
            '', content)
        # Remove inspector logo
        content = content.replace("    <file>inspector/logo.png</file>\n", '')

    # 4. Remove emoji data
    if config.get("remove_emoji_data"):
        content = content.replace("    <file>emoji/en.data</file>\n", '')

    with open(gen_script, 'w') as f:
        f.write(content)


def apply_inspector_stub(gtk_dir):
    """Stub gtk_window_set_debugging() to a no-op in gtkwindow.c."""
    file_path = os.path.join(gtk_dir, "gtk", "gtkwindow.c")
    stub_function(file_path, "gtk_window_set_debugging",
                  """{
  /* Inspector resources have been stripped from the gresource bundle to
   * reduce the shared-library size.  The interactive debugger is therefore
   * disabled unconditionally; attempting to create the inspector window
   * would fail because its GtkBuilder templates are no longer available. */
  (void) enable;
  (void) select;
  (void) warn;
}""")


def apply_debloat(gtk_dir, config):
    """Apply all debloat changes to the GTK source tree."""
    gtk_subdir = os.path.join(gtk_dir, "gtk")
    meson_build = os.path.join(gtk_subdir, "meson.build")
    gtk_h = os.path.join(gtk_subdir, "gtk.h")

    # --- Remove compilation units ---
    for unit in config.get("remove_compilation_units", []):
        print("Removing compilation units...")
        sources = unit.get("sources", [])
        headers = unit.get("headers", [])
        a11y_sources = unit.get("a11y_sources", [])
        a11y_headers = unit.get("a11y_headers", [])

        # Remove .c from gtk/meson.build (gtk_sources list)
        remove_lines_matching(meson_build, sources)

        # Remove .h from gtk/meson.build (gtk_gir_public_headers list)
        remove_lines_matching(meson_build, headers)

        # Remove #include from gtk/gtk.h
        for h in headers:
            remove_line_from_file(gtk_h, f"#include <gtk/{h}>")

        # Remove a11y .c and .h from gtk/a11y/meson.build
        a11y_meson = os.path.join(gtk_subdir, "a11y", "meson.build")
        if os.path.exists(a11y_meson):
            remove_lines_matching(a11y_meson, a11y_sources + a11y_headers)

    # --- Stub callers and remove sources ---
    for stub_config in config.get("stub_callers", []):
        print("Stubbing callers...")

        # Apply function stubs
        for stub in stub_config.get("stubs", []):
            file_path = os.path.join(gtk_dir, stub["file"])
            stub_function(file_path, stub["function"], stub["replacement"])

        # Replace specific calls
        for repl in stub_config.get("replace_calls", []):
            file_path = os.path.join(gtk_dir, repl["file"])
            replace_in_file(file_path, repl["old"], repl["new"])

        # Remove includes
        for inc in stub_config.get("remove_includes", []):
            file_path = os.path.join(gtk_dir, inc["file"])
            for h in inc["headers"]:
                remove_line_from_file(file_path, f"#include \"{h}\"")

        # Remove .c sources from meson.build
        sources_to_remove = stub_config.get("sources_to_remove", [])
        remove_lines_matching(meson_build, sources_to_remove)

    # --- Gresource changes ---
    gresource_config = config.get("gresource", {})
    if gresource_config:
        print("Applying gresource changes...")
        apply_gresource_changes(gtk_dir, gresource_config)

    # --- Inspector debugging stub ---
    if config.get("stub_inspector_debugging"):
        print("Stubbing inspector debugging...")
        apply_inspector_stub(gtk_dir)


def generate_gtk_source_patch(gtk_dir):
    """Generate a git diff of the changes."""
    run(["git", "add", "-A"], cwd=gtk_dir)
    diff = run(["git", "diff", "--cached"], cwd=gtk_dir)
    return diff.stdout


def generate_vcpkg_portfile_patch(config, gtk_source_patch, work_dir):
    """Generate the vcpkg patch that includes the GTK source patch + portfile changes.

    Creates a temporary vcpkg-like directory structure, modifies the portfile,
    and uses git diff to produce a correct patch.
    """
    meson_options = config.get("meson_options", {})

    # Create a temp vcpkg tree with just the gtk3 port
    vcpkg_temp = os.path.join(work_dir, "vcpkg-patch-gen")
    port_dir = os.path.join(vcpkg_temp, "ports", "gtk3")
    os.makedirs(port_dir)

    # Copy the original portfile.cmake from the vcpkg commit
    # We need to fetch it - use the vcpkg-verify checkout if available, or download
    vcpkg_portfile_url = "https://raw.githubusercontent.com/microsoft/vcpkg/99a97de2cb371449d4fb9dc970f2ac562d689ec2/ports/gtk3/portfile.cmake"
    portfile_path = os.path.join(port_dir, "portfile.cmake")
    print("Downloading original portfile.cmake...")
    urllib.request.urlretrieve(vcpkg_portfile_url, portfile_path)

    # Write the GTK source patch as a new file in the port dir
    gtk_patch_path = os.path.join(port_dir, "0003-debloat.patch")
    with open(gtk_patch_path, 'w') as f:
        f.write(gtk_source_patch)

    # Modify the portfile.cmake
    with open(portfile_path, 'r') as f:
        portfile_content = f.read()

    # Add 0003-debloat.patch to the PATCHES list
    portfile_content = portfile_content.replace(
        "        avoid-multiple-definition.diff\n)",
        "        avoid-multiple-definition.diff\n        0003-debloat.patch\n)"
    )

    # Add meson options
    if "print_backends" in meson_options:
        portfile_content = portfile_content.replace(
            "        -Dcolord=no                 # Build colord support for the CUPS printing backend",
            "        -Dcolord=no                 # Build colord support for the CUPS printing backend\n"
            f"        -Dprint_backends={meson_options['print_backends']}       # Only build the file print backend (cups/lpr/papi are Unix-only)"
        )

    if meson_options.get("b_lto"):
        portfile_content = portfile_content.replace(
            "    OPTIONS_RELEASE\n        ${OPTIONS_RELEASE}",
            "    OPTIONS_RELEASE\n        ${OPTIONS_RELEASE}\n"
            "        -Db_lto=true                # Whole-program optimization (/GL + /LTCG on MSVC) to reduce .text"
        )

    with open(portfile_path, 'w') as f:
        f.write(portfile_content)

    # Init git and diff
    run(["git", "init"], cwd=vcpkg_temp)
    run(["git", "config", "user.email", "debloat@local"], cwd=vcpkg_temp)
    run(["git", "config", "user.name", "Debloat"], cwd=vcpkg_temp)
    run(["git", "add", "-A"], cwd=vcpkg_temp)
    run(["git", "commit", "-m", "vcpkg upstream", "--quiet"], cwd=vcpkg_temp)

    # Now remove the new files, then restore to create the diff
    os.remove(gtk_patch_path)
    # Restore portfile to original
    urllib.request.urlretrieve(vcpkg_portfile_url, portfile_path)
    run(["git", "add", "-A"], cwd=vcpkg_temp)
    run(["git", "commit", "-m", "restore original", "--quiet"], cwd=vcpkg_temp)

    # Now re-apply our changes
    with open(gtk_patch_path, 'w') as f:
        f.write(gtk_source_patch)
    with open(portfile_path, 'w') as f:
        f.write(portfile_content)
    run(["git", "add", "-A"], cwd=vcpkg_temp)

    diff = run(["git", "diff", "--cached"], cwd=vcpkg_temp)
    return diff.stdout


def main():
    # Load config
    with open(JSON_PATH, 'r') as f:
        config = json.load(f)

    gtk_version = config["gtk_version"]

    # Create temp working directory
    work_dir = tempfile.mkdtemp(prefix="gtk3-debloat-")
    print(f"Working directory: {work_dir}")

    try:
        # Download and extract GTK source
        gtk_dir = download_and_extract_gtk(gtk_version, work_dir)

        # Init git repo for diffing
        init_git_repo(gtk_dir)

        # Apply all debloat changes
        apply_debloat(gtk_dir, config)

        # Generate the GTK source patch
        print("Generating GTK source patch...")
        gtk_source_patch = generate_gtk_source_patch(gtk_dir)

        if not gtk_source_patch.strip():
            print("ERROR: No changes generated. Check your configuration.", file=sys.stderr)
            sys.exit(1)

        # Generate the combined vcpkg patch
        print("Generating vcpkg patch...")
        vcpkg_patch = generate_vcpkg_portfile_patch(config, gtk_source_patch, work_dir)

        # Write the output patch
        with open(OUTPUT_PATCH, 'w') as f:
            f.write(vcpkg_patch)

        line_count = vcpkg_patch.count('\n')
        print(f"\nDone! Wrote {OUTPUT_PATCH} ({line_count} lines)")
        print(f"GTK source patch: {gtk_source_patch.count(chr(10))} lines")

    finally:
        # Clean up
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)
            print(f"Cleaned up {work_dir}")


if __name__ == "__main__":
    main()
