#!/usr/bin/env bash

set -euo pipefail

# Minimal PATH
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# Create the release for a tag with the given files, or add them to it if it
# already exists. The PyGTK and themes workflows publish to the same release.
# NOTES_FILE, if set, goes at the top of the release notes.
# Needs GH_TOKEN and GH_REPO.
# Usage: ./create-release.sh <tag> <file>...

usage="usage: $0 <tag> <file>..."
tag="${1:?${usage}}"
shift
if [[ "$#" -eq 0 ]]; then
    echo "${usage}" >&2
    exit 1
fi

created=false
if ! gh release view "${tag}" > /dev/null 2>&1; then
    # The other workflow can still create it first, then upload below
    if gh release create "${tag}" --verify-tag --generate-notes "$@"; then
        created=true
    fi
fi
if [[ "${created}" == false ]]; then
    gh release upload "${tag}" --clobber "$@"
fi

if [[ -n "${NOTES_FILE:-}" ]]; then
    body=$(gh release view "${tag}" --json body --jq .body)
    # A rerun finds the notes already there
    if ! grep -qxF -- "$(head -n 1 "${NOTES_FILE}")" <<< "${body}"; then
        {
            cat -- "${NOTES_FILE}"
            echo
            printf '%s\n' "${body}"
        } |
            gh release edit "${tag}" --notes-file -
    fi
fi
