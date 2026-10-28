#!/usr/bin/env bash
# Publish dist/CashMachine.exe as a permanent vMAJOR.MINOR GitHub Release
# and point the floating tag `latest` at the same commit.
#
# main (and workflow_dispatch on main):
#   next tag is v1.1 if no vX.Y tags exist, otherwise highest minor + 1
#   (v1.9 -> v1.10, v2.0 stays above v1.10). Annotated tag is created on
#   GITHUB_SHA — never on HEAD, which may have moved during the exe build.
# refs/tags/vX.Y:
#   attach the exe to that tag. Do not allocate another version.
#
# Only the release named exactly `latest` is deleted. v* releases stay.
# Test: bash .github/scripts/publish-windows-release.test.sh

set -euo pipefail

ASSET_NAME="CashMachine.exe"

log() {
  printf 'publish: %s\n' "$*" >&2
}

die() {
  printf 'publish: %s\n' "$*" >&2
  exit 1
}

double_click_tip() {
  printf '%s\n' 'Double-click CashMachine.exe. On first launch the app migrates SQLite under %LOCALAPPDATA%\CashMachine\ and opens the register.'
}

# vMAJOR.MINOR tags, oldest first. Ignores `latest`, patch tags, and anything else.
list_version_tags() {
  local tag major minor
  local lines=()
  while IFS= read -r tag; do
    [[ -z "$tag" ]] && continue
    if [[ "$tag" =~ ^v([0-9]+)\.([0-9]+)$ ]]; then
      major=$((10#${BASH_REMATCH[1]}))
      minor=$((10#${BASH_REMATCH[2]}))
      lines+=("$(printf '%08d %08d %s' "$major" "$minor" "$tag")")
    fi
  done < <(git tag -l 'v*')
  if [[ ${#lines[@]} -eq 0 ]]; then
    return 0
  fi
  printf '%s\n' "${lines[@]}" | sort | awk '{print $3}'
}

bump_version() {
  local tag="$1" major minor
  if [[ ! "$tag" =~ ^v([0-9]+)\.([0-9]+)$ ]]; then
    die "cannot bump '${tag}'"
  fi
  major=$((10#${BASH_REMATCH[1]}))
  minor=$((10#${BASH_REMATCH[2]} + 1))
  printf '%s\n' "v${major}.${minor}"
}

previous_tag() {
  local current="$1" tag best="" major minor cur_major cur_minor
  if [[ ! "$current" =~ ^v([0-9]+)\.([0-9]+)$ ]]; then
    return 0
  fi
  cur_major=$((10#${BASH_REMATCH[1]}))
  cur_minor=$((10#${BASH_REMATCH[2]}))
  while IFS= read -r tag; do
    [[ -z "$tag" ]] && continue
    [[ "$tag" =~ ^v([0-9]+)\.([0-9]+)$ ]] || continue
    major=$((10#${BASH_REMATCH[1]}))
    minor=$((10#${BASH_REMATCH[2]}))
    if (( major < cur_major || (major == cur_major && minor < cur_minor) )); then
      best="$tag"
    fi
  done < <(list_version_tags)
  if [[ -n "$best" ]]; then
    printf '%s\n' "$best"
  fi
}

release_exists() {
  gh release view "$1" >/dev/null 2>&1
}

release_has_asset() {
  local tag="$1"
  local asset="$2"
  local names
  names=$(gh release view "$tag" --json assets --jq '.assets[].name' 2>/dev/null) || return 1
  printf '%s\n' "$names" | grep -Fxq -- "$asset"
}

choose_version_for_main() {
  local tags highest sha
  tags=$(list_version_tags)
  if [[ -z "$tags" ]]; then
    printf '%s\n' "v1.1"
    return 0
  fi
  highest=$(printf '%s\n' "$tags" | tail -n 1)
  sha=$(git rev-parse "${highest}^{}")
  # A retry after the tag push succeeded and the upload did not: finish this
  # version. A finished release on the same commit (manual re-run) bumps.
  if [[ "$sha" == "$GITHUB_SHA" ]] && ! release_has_asset "$highest" "$ASSET_NAME"; then
    log "Reusing ${highest}: it points at this commit but ${ASSET_NAME} is not on the release."
    printf '%s\n' "$highest"
    return 0
  fi
  bump_version "$highest"
}

ensure_annotated_tag() {
  local tag="$1"
  local have
  if git rev-parse -q --verify "refs/tags/${tag}" >/dev/null; then
    have=$(git rev-parse "${tag}^{}")
    if [[ "$have" != "$GITHUB_SHA" ]]; then
      die "tag ${tag} already exists at ${have}, not ${GITHUB_SHA}; refusing to move a version tag"
    fi
    log "Tag ${tag} already points at ${GITHUB_SHA}."
    git push origin "refs/tags/${tag}"
    return 0
  fi
  git config user.name "github-actions[bot]"
  git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
  git tag -a "$tag" "$GITHUB_SHA" -m "CashMachine ${tag}"
  git push origin "refs/tags/${tag}"
  log "Created annotated tag ${tag} at ${GITHUB_SHA}."
}

append_footer() {
  local dest="$1"
  {
    printf '\n%s\n' "### Build"
    printf '%s\n' "- Commit: \`${GITHUB_SHA}\`"
    printf '%s\n' "- Run: ${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}"
    printf '\n'
    double_click_tip
  } >> "$dest"
}

write_version_notes() {
  local tag="$1"
  local prev="$2"
  local dest="$3"
  local log=""
  {
    printf '%s\n\n' "### Changes"
    if [[ -z "$prev" ]]; then
      printf '%s\n' "First versioned Windows build at this commit."
    else
      printf '%s\n\n' "Changes since \`${prev}\`:"
      log=$(git log "${prev}..${GITHUB_SHA}" --no-merges --pretty=format:'- %s' --reverse)
      if [[ -z "$log" ]]; then
        printf '%s\n' "- No non-merge commits since \`${prev}\`."
      else
        printf '%s\n' "$log"
      fi
    fi
  } > "$dest"
  append_footer "$dest"
}

write_latest_notes() {
  local tag="$1"
  local dest="$2"
  {
    printf '%s\n\n' "Tracks the newest versioned Windows build (\`${tag}\`)."
    printf '%s\n' "Permanent releases (\`v1.1\`, \`v1.2\`, …) stay on the Releases page with changelogs. This \`latest\` tag is only the stable download URL."
  } > "$dest"
  append_footer "$dest"
}

publish_version_release() {
  local tag="$1"
  local notes="$2"
  local exe="$3"
  local title="CashMachine ${tag}"
  if release_exists "$tag"; then
    log "Updating release ${tag}."
    gh release upload "$tag" "$exe" --clobber
    gh release edit "$tag" --title "$title" --notes-file "$notes" --latest
  else
    log "Creating release ${tag}."
    gh release create "$tag" "$exe" \
      --verify-tag \
      --target "$GITHUB_SHA" \
      --title "$title" \
      --notes-file "$notes" \
      --latest
  fi
}

# Delete and recreate only the floating release. The tag name is a constant
# so this cannot be pointed at a v* release.
refresh_floating_latest() {
  local notes="$1"
  local exe="$2"
  if release_exists latest; then
    gh release delete latest --yes --cleanup-tag
  else
    log "No previous latest release to replace."
  fi
  # cleanup-tag usually removes the remote tag. Delete again in case the
  # release was already gone, then point `latest` at the built commit.
  git push origin ":refs/tags/latest" || log "No remote latest tag to delete."
  git tag -f latest "$GITHUB_SHA"
  git push origin "refs/tags/latest" --force
  if ! gh release create latest "$exe" \
    --verify-tag \
    --target "$GITHUB_SHA" \
    --title "CashMachine (latest Windows build)" \
    --notes-file "$notes" \
    --latest=false; then
    log "Create failed; uploading over the existing latest release."
    gh release upload latest "$exe" --clobber
    gh release edit latest \
      --title "CashMachine (latest Windows build)" \
      --notes-file "$notes"
  fi
}

write_summary() {
  local tag="$1"
  if [[ -z "${GITHUB_STEP_SUMMARY:-}" ]]; then
    return 0
  fi
  cat >> "$GITHUB_STEP_SUMMARY" <<EOF
### CashMachine.exe

- Version: \`${tag}\`
- Versioned release: ${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/releases/tag/${tag}
- Stable download: ${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/releases/download/latest/CashMachine.exe
EOF
}

main() {
  local exe base tag prev notes latest_notes have
  : "${GITHUB_SHA:?GITHUB_SHA is required}"
  : "${GITHUB_REF:?GITHUB_REF is required}"
  : "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"
  : "${GITHUB_SERVER_URL:?GITHUB_SERVER_URL is required}"
  : "${GITHUB_RUN_ID:?GITHUB_RUN_ID is required}"
  if [[ ! "$GITHUB_SHA" =~ ^[0-9a-f]{40}$ ]]; then
    die "GITHUB_SHA must be the full 40-character commit id"
  fi

  exe="${EXE_PATH:-dist/CashMachine.exe}"
  base=$(basename "$exe")
  if [[ "$base" != "$ASSET_NAME" ]]; then
    die "exe must be named ${ASSET_NAME} so the latest download URL stays stable (got ${base})"
  fi
  if [[ ! -f "$exe" ]]; then
    die "missing exe at ${exe}"
  fi

  git rev-parse --is-inside-work-tree >/dev/null
  if [[ "${PUBLISH_SKIP_FETCH:-}" != "1" ]]; then
    git fetch origin --tags --force --prune
  fi

  case "$GITHUB_REF" in
    refs/tags/*)
      tag="${GITHUB_REF_NAME:?GITHUB_REF_NAME is required for a tag ref}"
      if [[ ! "$tag" =~ ^v[0-9]+\.[0-9]+$ ]]; then
        die "refusing to publish ${tag}: version tags must look like vMAJOR.MINOR"
      fi
      have=$(git rev-parse "${tag}^{}")
      if [[ "$have" != "$GITHUB_SHA" ]]; then
        die "tag ${tag} points at ${have}, workflow SHA is ${GITHUB_SHA}"
      fi
      log "Publishing existing tag ${tag} without bumping."
      ;;
    refs/heads/main)
      tag=$(choose_version_for_main)
      log "Version for ${GITHUB_SHA} is ${tag}."
      ensure_annotated_tag "$tag"
      ;;
    *)
      die "refusing to publish from ${GITHUB_REF}; expected refs/heads/main or refs/tags/vMAJOR.MINOR"
      ;;
  esac

  prev=$(previous_tag "$tag")
  notes=$(mktemp)
  latest_notes=$(mktemp)
  write_version_notes "$tag" "$prev" "$notes"
  write_latest_notes "$tag" "$latest_notes"
  publish_version_release "$tag" "$notes" "$exe"
  refresh_floating_latest "$latest_notes" "$exe"
  # The floating release is created with --latest=false. Mark the version
  # again so the GitHub Latest badge stays on vX.Y even if the API races.
  gh release edit "$tag" --latest
  write_summary "$tag"
  log "Published ${tag} and moved latest."
  rm -f "$notes" "$latest_notes"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  export LANG="${LANG:-C.UTF-8}"
  export GIT_TERMINAL_PROMPT=0
  main "$@"
fi
