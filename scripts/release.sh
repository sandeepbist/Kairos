#!/usr/bin/env bash
# Kairos release cutter.
#
# Usage:
#   scripts/release.sh <patch|minor|major>     bump backend/VERSION
#   scripts/release.sh <version>               cut an explicit version (e.g. 0.2.0)
#   scripts/release.sh <mode> --dry-run        print what would happen, change nothing
#
# What it does (full run):
#   1. verify: clean git tree, on branch main
#   2. read backend/VERSION (single source of truth)
#   3. bump it (or set the explicit version), mirror into
#      frontend/package.json via `npm pkg set`
#   4. move CHANGELOG.md [Unreleased] entries under the new version
#      heading and open a fresh [Unreleased]
#   5. commit "chore(release): vX.Y.Z", tag -a "vX.Y.Z"
#   6. print push instructions — the GitHub workflows take over from there
#
# Pushing the tag triggers: publish.yml (vX.Y.Z/stable/latest images on
# ghcr.io) and release.yml (GitHub Release, after verifying the tag
# matches backend/VERSION).

set -euo pipefail

VERSION_FILE="backend/VERSION"
PACKAGE_JSON="frontend/package.json"
CHANGELOG="CHANGELOG.md"

DRY_RUN="false"
ARG=""

usage() {
  cat <<EOF
Usage: scripts/release.sh <patch|minor|major|X.Y.Z> [--dry-run]

  patch    0.1.0 -> 0.1.1
  minor    0.1.0 -> 0.2.0
  major    0.1.0 -> 1.0.0
  X.Y.Z    cut this exact version

--dry-run prints every action without modifying anything.
EOF
}

die() { echo "error: $*" >&2; exit 1; }
log()  { echo "==> $*"; }
note() { echo "    $*"; }

semver_regex='^[0-9]+\.[0-9]+\.[0-9]+$'

# ---------------------------------------------------------------- args
for a in "$@"; do
  case "$a" in
    --dry-run) DRY_RUN="true" ;;
    -h|--help) usage; exit 0 ;;
    *) if [[ -n "$ARG" ]]; then usage; die "unexpected argument: $a"; else ARG="$a"; fi ;;
  esac
done
[[ -n "$ARG" ]] || { usage; die "missing <patch|minor|major|X.Y.Z>"; }

# ---------------------------------------------------------------- preconditions
cd "$(dirname "$0")/.."

[[ -f "$VERSION_FILE" ]] || die "$VERSION_FILE not found (run from repo root)"
[[ -f "$CHANGELOG" ]]    || die "$CHANGELOG not found (run from repo root)"
[[ -f "$PACKAGE_JSON" ]] || die "$PACKAGE_JSON not found (run from repo root)"

branch="$(git rev-parse --abbrev-ref HEAD)"
[[ "$branch" == "main" ]] || die "not on branch main (you are on '$branch') — releases cut from main only"

# A clean tree matters only for a real cut; --dry-run changes nothing, so
# it runs regardless (handy for previewing a release mid-work).
if [[ "$DRY_RUN" != "true" ]] && [[ -n "$(git status --porcelain)" ]]; then
  git status --short
  die "working tree is not clean — commit or stash first"
fi

current="$(tr -d ' \t\r\n' < "$VERSION_FILE")"
[[ "$current" =~ $semver_regex ]] || die "backend/VERSION ($current) is not valid semver X.Y.Z"

# ---------------------------------------------------------------- next version
bump() {
  local which="$1" IFS='.'
  read -r major minor patch <<<"$2"
  case "$which" in
    patch) echo "$major.$minor.$((patch + 1))" ;;
    minor) echo "$major.$((minor + 1)).0" ;;
    major) echo "$((major + 1)).0.0" ;;
  esac
}

case "$ARG" in
  patch|minor|major) next="$(bump "$ARG" "$current")"; mode="$ARG bump" ;;
  *)
    if [[ "$ARG" =~ $semver_regex ]]; then
      next="$ARG"; mode="explicit"
    else
      usage; die "invalid version or mode: $ARG"
    fi
    ;;
esac

# a downgrade or a same-version re-cut is almost always a mistake
if [[ "$mode" == "explicit" && "$next" == "$current" ]]; then
  die "backend/VERSION is already $current — use patch/minor/major to bump"
fi

today="$(date +%Y-%m-%d)"

log "current version: $current"
log "next version:     $next   ($mode)"
echo

# ---------------------------------------------------------------- changelog
# Verify the changelog shape before touching anything.
grep -q '^## \[Unreleased\]' "$CHANGELOG" \
  || die "CHANGELOG.md has no '## [Unreleased]' section to cut"
grep -q "^## \[$current\]" "$CHANGELOG" \
  || note "warning: CHANGELOG.md has no '## [$current]' entry (first release?)"

cut_changelog() {
  # Split the changelog at the first '## [' heading boundary:
  #   - header  = everything before '## [Unreleased]'
  #   - body    = the Unreleased section's content (up to the next '## [')
  #   - rest    = everything from the next '## [' heading on
  # The body moves under the new version heading (empty placeholder note
  # is dropped); a fresh Unreleased with the placeholder note opens on top.
  python3 - "$CHANGELOG" "$next" "$today" <<'PY'
import sys
path, version, today = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(path).read()

marker = "## [Unreleased]"
head, sep, tail = text.partition(marker)
if not sep:
    sys.exit("changelog: no [Unreleased] heading found")

# body = content of Unreleased up to the next version heading
body, sep2, rest = tail.partition("\n## [")
if sep2:
    rest = "\n## [" + rest
else:
    rest = ""  # no released versions yet; body ran to end of file

placeholder = "Tracked in commit history; curated here at release time."
lines = [l for l in body.strip("\n").splitlines() if l.strip()]
if not lines or (len(lines) == 1 and lines[0].strip() == placeholder):
    body = ""  # nothing real was collected for this release
else:
    body = "\n".join(lines)

fresh = (
    head
    + marker + "\n"
    + placeholder + "\n\n"
    + f"## [{version}] — {today}\n"
    + (body + "\n" if body else "")
    + ("\n" if body else "")
    + rest
)
open(path, "w").write(fresh.rstrip("\n") + "\n")
PY
}

# ---------------------------------------------------------------- act
if [[ "$DRY_RUN" == "true" ]]; then
  log "DRY RUN — nothing will be modified. Actions that would run:"
  note "write '$next' to $VERSION_FILE"
  note "run 'npm pkg set version=$next' in frontend/ (updates $PACKAGE_JSON)"
  note "cut CHANGELOG.md: [Unreleased] entries move under '## [$next] — $today', fresh [Unreleased] opens"
  note "git add $VERSION_FILE $PACKAGE_JSON $CHANGELOG"
  note "git commit -m 'chore(release): v$next'"
  note "git tag -a 'v$next' -m 'Kairos v$next'"
  echo
  log "then: git push origin main --follow-tags"
  note "publish.yml builds ghcr.io/<owner>/kairos-{backend,frontend}:{v$next,stable,latest}"
  note "release.yml verifies tag == backend/VERSION and creates the GitHub Release"
  exit 0
fi

log "writing $VERSION_FILE"
printf '%s\n' "$next" > "$VERSION_FILE"

log "updating $PACKAGE_JSON version (npm pkg set)"
( cd frontend && npm pkg set "version=$next" >/dev/null 2>&1 ) \
  || die "npm pkg set version failed"
python3 -c "import json; json.load(open('$PACKAGE_JSON'))" \
  || die "$PACKAGE_JSON is not valid JSON after the version bump — fix manually"

log "cutting CHANGELOG.md"
cut_changelog

log "committing"
git add "$VERSION_FILE" "$PACKAGE_JSON" "$CHANGELOG"
git commit -m "chore(release): v$next"

log "tagging"
git tag -a "v$next" -m "Kairos v$next"

echo
log "done: v$current -> v$next"
echo "Next steps:"
note "git push origin main --follow-tags"
note "pushing the tag v$next triggers:"
note "  publish.yml — ghcr.io images tagged v$next, stable, latest"
note "  release.yml  — GitHub Release (verifies tag == backend/VERSION first)"
note "docker-compose.ghcr.yml users on KAIROS_VERSION=edge follow main automatically;"
note "stable users move when you tell them to (README → Deployment & releases)."
