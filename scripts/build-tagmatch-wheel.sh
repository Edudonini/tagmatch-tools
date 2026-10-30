#!/usr/bin/env bash
# Rebuild vendor/tagmatch-*.whl from a commit of the private TagMatch repo.
# Usage: scripts/build-tagmatch-wheel.sh <commit> [path-to-TagMatch-clone]
# The wheel is gitignored (this repo is public) but shipped with `vercel --prod`,
# so builds need no GitHub credential.
set -euo pipefail
# strip CR/whitespace: `$(cat vendor/TAGMATCH_COMMIT)` may carry a CRLF on Windows
commit="$(printf %s "${1:?usage: $0 <commit> [path-to-TagMatch-clone]}" | tr -d '\r\n[:space:]')"
repo="${2:-../TagMatch}"
root="$(cd "$(dirname "$0")/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
git -C "$repo" archive "$commit" | tar -x -C "$work"
python -m pip wheel --no-deps -q -w "$work/dist" "$work"
rm -f "$root"/vendor/tagmatch-*.whl
cp "$work"/dist/tagmatch-*.whl "$root/vendor/"
git -C "$repo" rev-parse "$commit" > "$root/vendor/TAGMATCH_COMMIT"
echo "vendor/$(basename "$work"/dist/tagmatch-*.whl) built from $(cat "$root/vendor/TAGMATCH_COMMIT")"
