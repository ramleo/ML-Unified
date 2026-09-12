#!/usr/bin/env bash
#
# Fails when a tracked source file grows past the project's 400-line limit.
#
# Why this exists: the limit was a rule people (and assistants) had to remember,
# and on 2026-08-29 globals.css was allowed to reach 833 lines across seven
# commits in a single session, with the limit noticed only afterwards. A rule
# that depends on someone recalling it at the right moment fails silently and
# in one direction — whenever following it is inconvenient. This makes it fail
# loudly instead.
#
# Two modes of failure:
#   1. A file not in the baseline exceeds LIMIT      -> new violation
#   2. A file in the baseline exceeds its pinned size -> existing debt growing
#
# The baseline is not an exemption list. Each entry pins a file at the size it
# was when the gate went in, so known-oversized files can shrink or hold but
# never grow. Shrinking one below the limit is reported so the entry can be
# dropped.
#
# Usage:
#   scripts/check-file-length.sh            # check (exit 1 on violation)
#   scripts/check-file-length.sh --update   # rewrite the baseline from disk
#
# Deliberately avoids bash 4 associative arrays so it runs on macOS's bash 3.2
# as well as CI.

set -euo pipefail

LIMIT=400
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASELINE="$REPO_ROOT/.file-length-baseline"

# Extensions worth gating. Generated output, lockfiles and vendored code are
# excluded for free by using `git ls-files` rather than a filesystem walk.
EXTENSIONS=('*.py' '*.ts' '*.tsx' '*.js' '*.jsx' '*.mjs' '*.css' '*.html')

cd "$REPO_ROOT"

list_files() {
  git ls-files -- "${EXTENSIONS[@]}" | sort
}

count_lines() {
  wc -l < "$1" | tr -d '[:space:]'
}

pinned_size_for() {
  # Prints the pinned line count for $1, or nothing if it is not baselined.
  [ -f "$BASELINE" ] || return 0
  awk -v target="$1" '$1 !~ /^#/ && $2 == target { print $1; exit }' "$BASELINE"
}

if [ "${1:-}" = "--update" ]; then
  {
    echo "# Files already over the ${LIMIT}-line limit when this gate was added."
    echo "#"
    echo "# Each line pins a file at its current size: it may shrink or hold, but"
    echo "# CI fails if it grows. This is a debt register, not a set of exemptions —"
    echo "# once a file drops to ${LIMIT} lines or fewer, delete its line here so the"
    echo "# normal limit applies again."
    echo "#"
    echo "# Regenerate with: scripts/check-file-length.sh --update"
    echo "# format: <max-lines> <path>"
    list_files | while IFS= read -r file; do
      [ -f "$file" ] || continue
      lines="$(count_lines "$file")"
      [ "$lines" -gt "$LIMIT" ] && printf '%s %s\n' "$lines" "$file"
    done
  } > "$BASELINE"
  echo "Wrote $(grep -cv '^#' "$BASELINE" || true) entries to $BASELINE"
  exit 0
fi

new_violations=""
grown=""
shrunk=""
checked=0

while IFS= read -r file; do
  [ -f "$file" ] || continue
  checked=$((checked + 1))
  lines="$(count_lines "$file")"
  pinned="$(pinned_size_for "$file")"

  if [ -n "$pinned" ]; then
    if [ "$lines" -gt "$pinned" ]; then
      grown="${grown}  ${file}: ${lines} lines, pinned at ${pinned} (+$((lines - pinned)))
"
    elif [ "$lines" -le "$LIMIT" ]; then
      shrunk="${shrunk}  ${file}: now ${lines} lines — remove its baseline entry
"
    fi
  elif [ "$lines" -gt "$LIMIT" ]; then
    new_violations="${new_violations}  ${file}: ${lines} lines (limit ${LIMIT})
"
  fi
done < <(list_files)

status=0

if [ -n "$new_violations" ]; then
  echo "FAIL: file(s) over the ${LIMIT}-line limit:"
  printf '%s' "$new_violations"
  echo
  echo "Split the file before adding to it. If the work genuinely cannot be"
  echo "split now, that is a decision to raise explicitly — not to skip quietly."
  status=1
fi

if [ -n "$grown" ]; then
  echo "FAIL: known-oversized file(s) grew:"
  printf '%s' "$grown"
  echo
  echo "These are already over the limit and pinned so they cannot get worse."
  echo "Shrink the file, or split it, rather than raising the pin."
  status=1
fi

if [ -n "$shrunk" ]; then
  echo "NOTE: baselined file(s) are now within the limit:"
  printf '%s' "$shrunk"
  echo
fi

if [ "$status" -eq 0 ]; then
  echo "OK: ${checked} tracked source files checked, none over ${LIMIT} lines except pinned debt."
fi

exit "$status"
