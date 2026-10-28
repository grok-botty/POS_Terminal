#!/usr/bin/env bash
# Exercises publish-windows-release.sh against a local origin and a fake gh.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
SCRIPT="$ROOT/.github/scripts/publish-windows-release.sh"
ORIGINAL_PATH="$PATH"
TIP='Double-click CashMachine.exe. On first launch the app migrates SQLite under %LOCALAPPDATA%\CashMachine\ and opens the register.'

TEST_TMP=""
ORIGIN=""
REPO=""
GH_FAKE_LOG=""
GH_FAKE_STATE=""

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  if [[ -n "${GH_FAKE_LOG:-}" && -f "$GH_FAKE_LOG" ]]; then
    printf '--- gh log ---\n' >&2
    cat "$GH_FAKE_LOG" >&2
  fi
  exit 1
}

cleanup() {
  if [[ -n "$TEST_TMP" && -d "$TEST_TMP" ]]; then
    rm -rf "$TEST_TMP"
  fi
}
trap cleanup EXIT

assert_file_contains() {
  local file="$1" needle="$2"
  if [[ ! -f "$file" ]] || ! grep -F -q -- "$needle" "$file"; then
    printf 'FAIL: %q not in %s\n' "$needle" "$file" >&2
    if [[ -f "$file" ]]; then
      cat "$file" >&2
    fi
    fail "missing text in $file"
  fi
}

assert_file_excludes() {
  local file="$1" needle="$2"
  if [[ -f "$file" ]] && grep -F -q -- "$needle" "$file"; then
    cat "$file" >&2
    fail "unexpected text ${needle} in $file"
  fi
}

remote_tag_sha() {
  local tag="$1"
  git ls-remote "$ORIGIN" "refs/tags/${tag}" | awk '{print $1}'
}

assert_only_deletes_latest() {
  local line
  [[ -f "$GH_FAKE_LOG" ]] || return 0
  while IFS= read -r line; do
    if [[ "$line" == *"release delete"* && "$line" != *"release delete latest "* ]]; then
      fail "deleted a non-latest release: $line"
    fi
  done < "$GH_FAKE_LOG"
}

seed_release() {
  local tag="$1"
  local asset="${2:-CashMachine.exe}"
  : > "$GH_FAKE_STATE/$tag.release"
  printf '%s\n' "$asset" > "$GH_FAKE_STATE/$tag.assets"
}

sync_sha() {
  GITHUB_SHA=$(git -C "$REPO" rev-parse HEAD)
  export GITHUB_SHA
}

run_publish() {
  local expect="${1:-ok}" status
  if (cd "$REPO" && bash "$SCRIPT"); then
    status=0
  else
    status=$?
  fi
  if [[ "$expect" == ok && "$status" -ne 0 ]]; then
    fail "publish exited ${status}"
  fi
  if [[ "$expect" == fail && "$status" -eq 0 ]]; then
    fail "publish succeeded unexpectedly"
  fi
}

new_test_repo() {
  cleanup
  TEST_TMP=$(mktemp -d)
  ORIGIN="$TEST_TMP/origin.git"
  REPO="$TEST_TMP/repo"
  local fake_bin="$TEST_TMP/bin"
  GH_FAKE_LOG="$TEST_TMP/gh.log"
  GH_FAKE_STATE="$TEST_TMP/gh-state"
  mkdir -p "$fake_bin" "$GH_FAKE_STATE"
  export GH_FAKE_LOG GH_FAKE_STATE
  export GH_FAKE_REPO="$REPO"
  export PATH="$fake_bin:$ORIGINAL_PATH"
  cat > "$fake_bin/gh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
log="${GH_FAKE_LOG:?}"
state="${GH_FAKE_STATE:?}"
mkdir -p "$state"
{
  printf '%q ' "$@"
  printf '\n'
} >> "$log"

[[ "${1:-}" == "release" ]] || { echo "unexpected gh command: $*" >&2; exit 1; }
sub="${2:-}"
shift 2

tag=""
notes_file=""
target=""
json=0
args=("$@")
i=0
while [[ $i -lt ${#args[@]} ]]; do
  a="${args[$i]}"
  case "$a" in
    --json)
      json=1
      i=$((i + 2))
      ;;
    --notes-file)
      notes_file="${args[$((i + 1))]}"
      i=$((i + 2))
      ;;
    --target)
      target="${args[$((i + 1))]}"
      i=$((i + 2))
      ;;
    --title|--jq)
      i=$((i + 2))
      ;;
    --latest=*|--yes|--cleanup-tag|--verify-tag|--clobber|--latest)
      i=$((i + 1))
      ;;
    --*)
      echo "unhandled flag $a" >&2
      exit 1
      ;;
    *)
      if [[ -z "$tag" ]]; then
        tag="$a"
      fi
      i=$((i + 1))
      ;;
  esac
done

case "$sub" in
  view)
    [[ -f "$state/$tag.release" ]] || exit 1
    if [[ "$json" -eq 1 && -f "$state/$tag.assets" ]]; then
      cat "$state/$tag.assets"
    fi
    ;;
  delete)
    [[ "$tag" == "latest" ]] || { echo "REFUSING to delete $tag" >&2; exit 99; }
    rm -f "$state/$tag.release" "$state/$tag.assets" "$state/$tag.notes"
    ;;
  create)
    if [[ -f "$state/$tag.release" ]]; then
      echo "release $tag exists" >&2
      exit 1
    fi
    : > "$state/$tag.release"
    printf '%s\n' "CashMachine.exe" > "$state/$tag.assets"
    if [[ -n "$notes_file" ]]; then
      cp "$notes_file" "$state/$tag.notes"
    fi
    if [[ "$tag" == "latest" && -n "${GH_FAKE_REPO:-}" && -n "$target" ]]; then
      git -C "$GH_FAKE_REPO" tag -f latest "$target" >/dev/null
      git -C "$GH_FAKE_REPO" push origin refs/tags/latest --force >/dev/null
    fi
    ;;
  upload)
    [[ -f "$state/$tag.release" ]] || { echo "upload: no release $tag" >&2; exit 1; }
    printf '%s\n' "CashMachine.exe" > "$state/$tag.assets"
    ;;
  edit)
    [[ -f "$state/$tag.release" ]] || { echo "edit: no release $tag" >&2; exit 1; }
    if [[ -n "$notes_file" ]]; then
      cp "$notes_file" "$state/$tag.notes"
    fi
    ;;
  *)
    echo "unhandled subcommand $sub" >&2
    exit 1
    ;;
esac
EOF
  chmod +x "$fake_bin/gh"

  git init -b main "$REPO" >/dev/null
  git -C "$REPO" config user.email "t@example.com"
  git -C "$REPO" config user.name "Test"
  echo init > "$REPO/README"
  git -C "$REPO" add README
  git -C "$REPO" commit -m "init" >/dev/null
  git -c init.defaultBranch=main init --bare "$ORIGIN" >/dev/null
  git -C "$ORIGIN" symbolic-ref HEAD refs/heads/main
  git -C "$REPO" remote add origin "$ORIGIN"
  git -C "$REPO" push -u origin main >/dev/null
  git -C "$REPO" tag latest
  git -C "$REPO" push origin refs/tags/latest >/dev/null
  mkdir -p "$REPO/dist"
  printf 'exe\n' > "$REPO/dist/CashMachine.exe"

  export EXE_PATH="$REPO/dist/CashMachine.exe"
  export GITHUB_REF="refs/heads/main"
  export GITHUB_REF_NAME="main"
  export GITHUB_REPOSITORY="grok-botty/POS_Terminal"
  export GITHUB_SERVER_URL="https://github.com"
  export GITHUB_RUN_ID="12345"
  export GITHUB_STEP_SUMMARY="$TEST_TMP/summary.md"
  : > "$GITHUB_STEP_SUMMARY"
  sync_sha
  seed_release latest
}

assert_version_release_shape() {
  local tag="$1"
  local line
  line=$(grep -F "release create ${tag} " "$GH_FAKE_LOG" || true)
  [[ -n "$line" ]] || fail "no release create for ${tag}"
  [[ "$line" == *"--verify-tag"* ]] || fail "${tag} create did not require an existing tag"
  [[ "$line" == *"--latest"* ]] || fail "${tag} was not marked latest"
  [[ "$line" != *"--latest=false"* ]] || fail "${tag} was explicitly not latest"
  [[ "$line" == *"$GITHUB_SHA"* ]] || fail "${tag} was not targeted at the built commit"
  local latest_line
  latest_line=$(grep -F "release create latest " "$GH_FAKE_LOG")
  [[ "$latest_line" == *"--latest=false"* ]] || fail "floating latest stole the Latest badge"
  [[ "$latest_line" == *"$GITHUB_SHA"* ]] || fail "floating latest was not targeted at the built commit"
  assert_only_deletes_latest
  [[ "$(remote_tag_sha latest)" == "$GITHUB_SHA" ]] || fail "remote latest tag does not point at the built commit"
  [[ "$(git -C "$REPO" rev-parse "${tag}^{}")" == "$GITHUB_SHA" ]] || fail "${tag} does not point at the built commit"
  [[ "$(git -C "$REPO" cat-file -t "$tag")" == "tag" ]] || fail "${tag} is not annotated"
  [[ "$(remote_tag_sha "$tag")" == "$(git -C "$REPO" rev-parse "refs/tags/${tag}")" ]] || fail "${tag} was not pushed"
  assert_file_contains "$GH_FAKE_STATE/${tag}.notes" "$TIP"
  assert_file_contains "$GH_FAKE_STATE/${tag}.notes" "$GITHUB_SHA"
  assert_file_contains "$GH_FAKE_STATE/${tag}.notes" "/actions/runs/12345"
  assert_file_contains "$GH_FAKE_STATE/latest.notes" "Tracks the newest versioned Windows build (\`${tag}\`)."
  assert_file_contains "$GH_FAKE_STATE/latest.notes" "$TIP"
  assert_file_contains "$GITHUB_STEP_SUMMARY" "releases/download/latest/CashMachine.exe"
  assert_file_contains "$GITHUB_STEP_SUMMARY" "releases/tag/${tag}"
}

test_bump_versions() {
  bash -c '
    set -euo pipefail
    source "$1"
    [[ "$(bump_version v1.9)" == "v1.10" ]]
    [[ "$(bump_version v1.08)" == "v1.9" ]]
    [[ "$(bump_version v2.0)" == "v2.1" ]]
    [[ "$(bump_version v1.1)" == "v1.2" ]]
  ' bash "$SCRIPT"
  echo "ok: bump versions"
}

test_first_release_tags_built_sha_not_head() {
  new_test_repo
  local built="$GITHUB_SHA"
  git -C "$REPO" commit --allow-empty -m "main moved during the build" >/dev/null
  git -C "$REPO" push origin main >/dev/null
  export GITHUB_SHA="$built"
  run_publish ok
  assert_version_release_shape v1.1
  assert_file_contains "$GH_FAKE_STATE/v1.1.notes" "First versioned Windows build at this commit."
  assert_file_excludes "$GH_FAKE_STATE/v1.1.notes" "main moved during the build"
  [[ "$(git -C "$REPO" rev-parse HEAD)" != "$built" ]] || fail "fixture did not move HEAD"
  [[ "$(git -C "$REPO" rev-parse 'v1.1^{}')" == "$built" ]] || fail "v1.1 followed HEAD"
  echo "ok: first release is v1.1 on the built commit"
}

test_bump_v1_9_to_v1_10() {
  new_test_repo
  git -C "$REPO" tag v1.9
  git -C "$REPO" push origin v1.9 >/dev/null
  seed_release v1.9
  run_publish ok
  assert_version_release_shape v1.10
  [[ -z "$(git -C "$REPO" tag -l v1.91)" ]] || fail "minor bump became v1.91"
  echo "ok: v1.9 bumps to v1.10"
}

test_highest_is_numeric_across_majors() {
  new_test_repo
  git -C "$REPO" tag v1.9
  git -C "$REPO" tag v1.10
  git -C "$REPO" tag v2.0
  git -C "$REPO" tag v1.2.3
  git -C "$REPO" push origin --tags >/dev/null
  seed_release v2.0
  run_publish ok
  assert_version_release_shape v2.1
  [[ -n "$(git -C "$REPO" tag -l v1.10)" ]] || fail "v1.10 disappeared"
  [[ -n "$(git -C "$REPO" tag -l v1.2.3)" ]] || fail "unrelated tag disappeared"
  echo "ok: highest version is numeric and ignores patch and latest tags"
}

test_changelog_since_previous_tag() {
  new_test_repo
  git -C "$REPO" tag v1.1
  git -C "$REPO" push origin v1.1 >/dev/null
  seed_release v1.1
  git -C "$REPO" checkout -b feature >/dev/null
  git -C "$REPO" commit --allow-empty -m "feat: real change" >/dev/null
  git -C "$REPO" checkout main >/dev/null
  git -C "$REPO" merge --no-ff feature -m "Merge pull request #4 from example/feature" >/dev/null
  git -C "$REPO" commit --allow-empty -m "Касса: оплата (#10)" >/dev/null
  git -C "$REPO" commit --allow-empty -m "fix: 100% syrop" >/dev/null
  git -C "$REPO" push origin main >/dev/null
  sync_sha
  run_publish ok
  assert_version_release_shape v1.2
  local notes="$GH_FAKE_STATE/v1.2.notes"
  assert_file_contains "$notes" "Changes since \`v1.1\`:"
  assert_file_contains "$notes" "- feat: real change"
  assert_file_contains "$notes" "- Касса: оплата (#10)"
  assert_file_contains "$notes" "- fix: 100% syrop"
  assert_file_excludes "$notes" "Merge pull request #4"
  assert_file_excludes "$notes" "init"
  assert_file_excludes "$notes" "First versioned Windows build"
  local feat_line kassa_line pct_line
  feat_line=$(grep -n -F "feat: real change" "$notes" | head -n 1 | cut -d: -f1)
  kassa_line=$(grep -n -F "Касса: оплата (#10)" "$notes" | head -n 1 | cut -d: -f1)
  pct_line=$(grep -n -F "100% syrop" "$notes" | head -n 1 | cut -d: -f1)
  [[ "$feat_line" -lt "$kassa_line" && "$kassa_line" -lt "$pct_line" ]] || fail "changelog is not chronological"
  echo "ok: changelog lists non-merge subjects since the previous tag"
}

test_reuse_incomplete_release_on_same_commit() {
  new_test_repo
  git -C "$REPO" tag -a v1.1 -m "CashMachine v1.1"
  git -C "$REPO" push origin v1.1 >/dev/null
  local before
  before=$(git -C "$REPO" rev-parse v1.1)
  run_publish ok
  [[ -z "$(git -C "$REPO" tag -l v1.2)" ]] || fail "incomplete v1.1 was skipped for v1.2"
  [[ "$(git -C "$REPO" rev-parse v1.1)" == "$before" ]] || fail "existing v1.1 tag object changed"
  [[ "$(git -C "$REPO" cat-file -t v1.1)" == "tag" ]] || fail "v1.1 lost its annotation"
  grep -F -q "release create v1.1 " "$GH_FAKE_LOG" || fail "did not create the missing v1.1 release"
  if grep -F -q "release create v1.2 " "$GH_FAKE_LOG"; then
    fail "created v1.2 while v1.1 had no exe"
  fi
  assert_file_contains "$GH_FAKE_STATE/v1.1.notes" "First versioned Windows build at this commit."
  assert_only_deletes_latest
  echo "ok: retry finishes the version tag that has no exe"
}

test_bump_again_when_same_commit_already_published() {
  new_test_repo
  git -C "$REPO" tag -a v1.1 -m "CashMachine v1.1"
  git -C "$REPO" push origin v1.1 >/dev/null
  seed_release v1.1
  run_publish ok
  assert_version_release_shape v1.2
  [[ -n "$(git -C "$REPO" tag -l v1.1)" ]] || fail "previous version tag was removed"
  assert_file_contains "$GH_FAKE_STATE/v1.2.notes" "No non-merge commits since \`v1.1\`."
  assert_file_excludes "$GH_FAKE_STATE/v1.2.notes" "First versioned Windows build"
  echo "ok: a finished release on this commit still bumps"
}

test_existing_version_tag_does_not_bump() {
  new_test_repo
  git -C "$REPO" tag v1.1
  git -C "$REPO" push origin v1.1 >/dev/null
  seed_release v1.1
  git -C "$REPO" commit --allow-empty -m "feat: from a pushed tag" >/dev/null
  git -C "$REPO" tag v1.2
  git -C "$REPO" push origin main v1.2 >/dev/null
  sync_sha
  export GITHUB_REF="refs/tags/v1.2"
  export GITHUB_REF_NAME="v1.2"
  local kind_before
  kind_before=$(git -C "$REPO" cat-file -t v1.2)
  run_publish ok
  [[ "$kind_before" == "commit" ]] || fail "fixture tag should be lightweight"
  [[ "$(git -C "$REPO" cat-file -t v1.2)" == "commit" ]] || fail "tag push rewrote v1.2 as an annotated tag"
  [[ -z "$(git -C "$REPO" tag -l v1.3)" ]] || fail "tag push allocated v1.3"
  assert_file_contains "$GH_FAKE_STATE/v1.2.notes" "Changes since \`v1.1\`:"
  assert_file_contains "$GH_FAKE_STATE/v1.2.notes" "- feat: from a pushed tag"
  grep -F -q "release create v1.2 " "$GH_FAKE_LOG" || fail "did not publish the pushed tag"
  if grep -F -q "release create v1.3 " "$GH_FAKE_LOG"; then
    fail "created a bumped release for an existing tag"
  fi
  [[ "$(remote_tag_sha latest)" == "$GITHUB_SHA" ]] || fail "latest was not refreshed from the tag push"
  assert_only_deletes_latest
  echo "ok: pushing v1.2 does not invent v1.3"
}

test_reject_patch_tag() {
  new_test_repo
  git -C "$REPO" tag v1.2.3
  git -C "$REPO" push origin v1.2.3 >/dev/null
  export GITHUB_REF="refs/tags/v1.2.3"
  export GITHUB_REF_NAME="v1.2.3"
  sync_sha
  run_publish fail
  [[ ! -s "$GH_FAKE_LOG" ]] || fail "patch tag talked to gh"
  [[ -n "$(remote_tag_sha latest)" ]] || fail "patch tag removed latest"
  echo "ok: patch tags are rejected"
}

test_reject_non_main_branch() {
  new_test_repo
  export GITHUB_REF="refs/heads/develop"
  export GITHUB_REF_NAME="develop"
  run_publish fail
  [[ ! -s "$GH_FAKE_LOG" ]] || fail "non-main ref talked to gh"
  [[ -n "$(remote_tag_sha latest)" ]] || fail "non-main ref removed latest"
  [[ -z "$(git -C "$REPO" tag -l 'v[0-9]*')" ]] || fail "non-main ref created a version tag"
  echo "ok: only main and version tags publish"
}

test_missing_exe_does_not_publish() {
  new_test_repo
  rm -f "$REPO/dist/CashMachine.exe"
  run_publish fail
  [[ ! -s "$GH_FAKE_LOG" ]] || fail "missing exe talked to gh"
  [[ -n "$(remote_tag_sha latest)" ]] || fail "missing exe removed latest"
  echo "ok: missing exe does not publish"
}

test_wrong_exe_name() {
  new_test_repo
  export EXE_PATH="$REPO/dist/CashMachine-setup.exe"
  printf 'exe\n' > "$EXE_PATH"
  run_publish fail
  [[ -n "$(remote_tag_sha latest)" ]] || fail "renamed exe removed latest"
  [[ -z "$(git -C "$REPO" tag -l 'v[0-9]*')" ]] || fail "renamed exe created a version tag"
  echo "ok: exe filename must stay CashMachine.exe"
}

test_refuse_to_move_existing_version_tag() {
  new_test_repo
  local old="$GITHUB_SHA"
  git -C "$REPO" commit --allow-empty -m "newer" >/dev/null
  git -C "$REPO" tag v1.2 "$old"
  git -C "$REPO" push origin v1.2 >/dev/null
  sync_sha
  local status=0
  bash -c '
    set -euo pipefail
    source "$1"
    cd "$2"
    export GITHUB_SHA="'"$GITHUB_SHA"'"
    ensure_annotated_tag v1.2
  ' bash "$SCRIPT" "$REPO" || status=$?
  [[ "$status" -ne 0 ]] || fail "moved a version tag onto a different commit"
  [[ "$(git -C "$REPO" rev-parse 'v1.2^{}')" == "$old" ]] || fail "v1.2 no longer points at the original commit"
  echo "ok: version tags are not moved"
}

test_tag_sha_mismatch_does_not_delete_latest() {
  new_test_repo
  local old="$GITHUB_SHA"
  git -C "$REPO" tag v1.2 "$old"
  git -C "$REPO" push origin v1.2 >/dev/null
  git -C "$REPO" commit --allow-empty -m "newer" >/dev/null
  git -C "$REPO" push origin main >/dev/null
  sync_sha
  export GITHUB_REF="refs/tags/v1.2"
  export GITHUB_REF_NAME="v1.2"
  run_publish fail
  [[ ! -s "$GH_FAKE_LOG" ]] || fail "mismatched tag talked to gh"
  [[ -n "$(remote_tag_sha latest)" ]] || fail "mismatched tag removed latest"
  echo "ok: a tag that does not match the workflow SHA is left alone"
}

test_bump_versions
test_first_release_tags_built_sha_not_head
test_bump_v1_9_to_v1_10
test_highest_is_numeric_across_majors
test_changelog_since_previous_tag
test_reuse_incomplete_release_on_same_commit
test_bump_again_when_same_commit_already_published
test_existing_version_tag_does_not_bump
test_reject_patch_tag
test_reject_non_main_branch
test_missing_exe_does_not_publish
test_wrong_exe_name
test_refuse_to_move_existing_version_tag
test_tag_sha_mismatch_does_not_delete_latest

echo "all publish-script tests passed"
