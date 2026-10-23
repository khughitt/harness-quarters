#!/usr/bin/env bash
# hq-48c5c6 review round 2 (adds [ ! -d ] for a directory at <path>): probe the guarded content form the revised justification names.
#   src="<src>" && [ "$(git cat-file -t "$src")" = blob ] && [ ! -L "<path>" ] && tmp=$(mktemp) \
#     && git show "$src" > "$tmp" && cp -- "$tmp" "<path>" && rm "$tmp"
set -uo pipefail
for v in $(env | sed -n 's/^\(GIT_[A-Z_]*\)=.*/\1/p'); do unset "$v"; done
SRC_CONFIG=$1
ROOT=$(mktemp -d -p "$WORK_ROOT/hq/hq-48c5c6" run.XXXX)
OUTSIDE=$(mktemp -d -p "$HOME/.cache" hq-48c5c6.XXXX)   # not a writable root
trap 'rm -r -- "$ROOT" "$OUTSIDE"' EXIT INT TERM
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 \
  GIT_AUTHOR_NAME=probe GIT_AUTHOR_EMAIL=probe@example.invalid \
  GIT_COMMITTER_NAME=probe GIT_COMMITTER_EMAIL=probe@example.invalid
export TMPDIR=$ROOT/tmp; mkdir -p "$TMPDIR"
CH=$ROOT/codex-home; mkdir -p "$CH"
{ echo 'default_permissions = "workspace-local"'; echo 'approval_policy = "never"';
  sed -n '/^\[permissions\.workspace-local\]/,/^\[shell_environment_policy\]/p' "$SRC_CONFIG" | sed '$d'; } > "$CH/config.toml"
guard() {
  [ "$(git -C "$1" rev-parse --show-toplevel)" = "$(cd "$1" && pwd -P)" ] || { echo "fixture escaped"; exit 2; }
  case "$(git -C "$1" rev-parse --absolute-git-dir)" in "$(cd "$1" && pwd -P)"/*|"$OUTSIDE"/*) ;; *) echo "gitdir escaped"; exit 2;; esac
}
form() { printf 'src="%s" && [ "$(git cat-file -t "$src")" = blob ] && [ ! -L "%s" ] && [ ! -d "%s" ] && tmp=$(mktemp) && git show "$src" > "$tmp" && cp -- "$tmp" "%s" && rm "$tmp"' "$1" "$2" "$2" "$2"; }
# History: c and sub/c share a name; dir/ with two files; link -> c; x executable; v1 then v2.
mkhist() {
  local d=$1; git init -q -b main "$d"; guard "$d"; mkdir -p "$d/sub" "$d/dir"
  echo top-v1 > "$d/c"; echo sub-v1 > "$d/sub/c"; echo f1-v1 > "$d/dir/f1"; echo f2 > "$d/dir/f2"
  ln -s c "$d/link"; printf '#!/bin/sh\n' > "$d/x"; chmod +x "$d/x"
  git -C "$d" add -A; git -C "$d" commit -qm v1; git -C "$d" tag v1
  echo top-v2 > "$d/c"; echo sub-v2 > "$d/sub/c"; echo f1-v2 > "$d/dir/f1"; git -C "$d" commit -qam v2
  git -C "$d" switch -qc other; echo theirs > "$d/c"; git -C "$d" commit -qam theirs
  git -C "$d" switch -q main; echo ours > "$d/c"; git -C "$d" commit -qam ours
}
st() { git -C "$1" status --porcelain | tr '\n' ';'; }
strays() { find "$1" -name 'tmp.*' -not -path '*/.git/*' | wc -l; }
row() { printf '%-11s | %-34s | rc=%-3s | %s\n' "$1" "$2" "$3" "$4"; }
run() { # where label dir-to-run-in src path
  local d=$1 label=$2 in=$3 src=$4 p=$5
  (cd "$in" && bash -c "$(form "$src" "$p")") >/dev/null 2>&1; echo $?; }

d=$ROOT/a; mkhist "$d"; echo edit > "$d/sub/c"
rc=$(run "$d" x "$d/sub" "v1:./c" "c"); row plain-git "v1:./c from sub/" "$rc" "sub/c=$(cat "$d/sub/c") c=$(cat "$d/c") | $(st "$d") strays=$(strays "$d")"
d=$ROOT/b; mkhist "$d"; echo edit > "$d/dir/f1"
rc=$(run "$d" x "$d" "v1:./dir" "dir"); row plain-git "v1:./dir (a directory)" "$rc" "dir/f1=$(cat "$d/dir/f1") | $(st "$d") strays=$(strays "$d")"
d=$ROOT/c; mkhist "$d"; echo edit > "$d/c"
rc=$(run "$d" x "$d" "v1:./link" "link"); row plain-git "v1:./link (symlink at path)" "$rc" "c=$(cat "$d/c") link=$(readlink "$d/link") | $(st "$d") strays=$(strays "$d")"
d=$ROOT/e; mkhist "$d"; echo edit > "$d/c"
rc=$(run "$d" x "$d" "v1:./missing" "c"); row plain-git "v1:./missing (no such path)" "$rc" "c=$(cat "$d/c") | $(st "$d") strays=$(strays "$d")"
d=$ROOT/f; mkhist "$d"; rm "$d/x"
rc=$(run "$d" x "$d" "v1:./x" "x"); row plain-git "v1:./x (file deleted, was 755)" "$rc" "mode=$(stat -c %a "$d/x") | $(st "$d")"
d=$ROOT/h; mkhist "$d"; rm "$d/c"; mkdir "$d/c"; echo keep > "$d/c/x"
rc=$(run "$d" x "$d" "v1:./c" "c"); row plain-git "v1:./c (directory at path)" "$rc" "c/=$(ls "$d/c" | tr '\n' ' ') | $(st "$d") strays=$(strays "$d")"
d=$ROOT/g; mkhist "$d"; git -C "$d" merge -q other >/dev/null 2>&1
rc=$(run "$d" x "$d" ":3:./c" "c"); row plain-git ":3:./c (merge conflict)" "$rc" "c=$(cat "$d/c") | $(st "$d") strays=$(strays "$d")"

sbx() { env -i PATH="$PATH" HOME="$HOME" CODEX_HOME="$CH" TMPDIR="$TMPDIR" GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 \
  codex sandbox -P workspace-local -C "$1" -- bash -c "$2" 2>&1 | grep -v '^WARNING: proceeding' | head -3; return "${PIPESTATUS[0]}"; }
m=$OUTSIDE/m1; w=$ROOT/w1; mkhist "$m"; git -C "$m" worktree add -q "$w" -b w1 >/dev/null 2>&1; guard "$w"; echo edit > "$w/sub/c"
out=$(sbx "$w/sub" "$(form "v1:./c" "c")"); rc=$?
row sandbox-wt "v1:./c from sub/" "$rc" "sub/c=$(cat "$w/sub/c") | $(st "$w") ${out:+| $out}"
m=$OUTSIDE/m2; w=$ROOT/w2; mkhist "$m"; git -C "$m" worktree add -q "$w" -b w2 >/dev/null 2>&1; guard "$w"; git -C "$w" merge -q other >/dev/null 2>&1
out=$(sbx "$w" "$(form ":3:./c" "c")"); rc=$?
row sandbox-wt ":3:./c (merge conflict)" "$rc" "c=$(cat "$w/c") | $(st "$w") ${out:+| $out}"
out=$(sbx "$w" "$(form "v1:./dir" "dir")"); rc=$?
row sandbox-wt "v1:./dir (a directory)" "$rc" "$(st "$w") strays=$(strays "$w") ${out:+| $out}"
