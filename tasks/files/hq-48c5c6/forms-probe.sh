#!/usr/bin/env bash
# hq-48c5c6: probe the two forms the git restore justification gains.
#   restore-from-commit: tmp=$(mktemp) && git show "<rev>:./<path>" > "$tmp" && cp -- "$tmp" "<path>" && rm "$tmp"
#   take a deletion:     git rm --cached -- <path>   (allow rule, skips the sandbox), then rm -- <path>
# Plain git for the outcome; codex sandbox in a linked worktree for the parts that run sandboxed.
set -uo pipefail
for v in $(env | sed -n 's/^\(GIT_[A-Z_]*\)=.*/\1/p'); do unset "$v"; done
SRC_CONFIG=$1
ROOT=$(mktemp -d -p "$WORK_ROOT/hq/hq-48c5c6" run.XXXX)
OUTSIDE=$(mktemp -d -p "$HOME/.cache" hq-48c5c6.XXXX)   # not a writable root
trap 'rm -r -- "$ROOT" "$OUTSIDE"' EXIT INT TERM
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 \
  GIT_AUTHOR_NAME=probe GIT_AUTHOR_EMAIL=probe@example.invalid \
  GIT_COMMITTER_NAME=probe GIT_COMMITTER_EMAIL=probe@example.invalid
CH=$ROOT/codex-home; mkdir -p "$CH"
{ echo 'default_permissions = "workspace-local"'; echo 'approval_policy = "never"';
  sed -n '/^\[permissions\.workspace-local\]/,/^\[shell_environment_policy\]/p' "$SRC_CONFIG" | sed '$d'; } > "$CH/config.toml"
guard() {
  [ "$(git -C "$1" rev-parse --show-toplevel)" = "$(cd "$1" && pwd -P)" ] || { echo "fixture escaped"; exit 2; }
  case "$(git -C "$1" rev-parse --absolute-git-dir)" in "$(cd "$1" && pwd -P)"/*|"$OUTSIDE"/*) ;; *) echo "gitdir escaped"; exit 2;; esac
}
# History: top-level c and sub/c share a name; v1 then v2; c edited, uncommitted, after v2.
mkhist() {
  local d=$1; git init -q -b main "$d"; guard "$d"; mkdir -p "$d/sub"
  echo top-v1 > "$d/c"; echo sub-v1 > "$d/sub/c"; printf '#!/bin/sh\n' > "$d/sub/x"; chmod +x "$d/sub/x"
  git -C "$d" add -A; git -C "$d" commit -qm v1; git -C "$d" tag v1
  echo top-v2 > "$d/c"; echo sub-v2 > "$d/sub/c"; echo 'echo v2' >> "$d/sub/x"; git -C "$d" commit -qam v2
}
# Modify/delete conflict: other deletes d, main edits it.
mkdel() {
  local d=$1; git init -q -b main "$d"; guard "$d"
  echo base > "$d/d"; echo keep > "$d/k"; git -C "$d" add -A; git -C "$d" commit -qm base
  git -C "$d" switch -qc other; git -C "$d" rm -q d; git -C "$d" commit -qm del
  git -C "$d" switch -q main; echo ours > "$d/d"; git -C "$d" commit -qam ours
  git -C "$d" merge -q other >/dev/null 2>&1
}
st() { git -C "$1" status --porcelain | tr '\n' ';'; }
row() { printf '%-22s | %-82s | rc=%s | %s\n' "$1" "$2" "$3" "$4"; }
FROM='tmp=$(mktemp) && git show "v1:./c" > "$tmp" && cp -- "$tmp" "c" && rm "$tmp"'
FROMX='tmp=$(mktemp) && git show "v1:./x" > "$tmp" && cp -- "$tmp" "x" && rm "$tmp"'
MISS='tmp=$(mktemp) && git show "v1:./missing" > "$tmp" && cp -- "$tmp" "c" && rm "$tmp"'

d=$ROOT/p1; mkhist "$d"; echo uncommitted > "$d/c"
(cd "$d/sub" && bash -c "$FROM") >/dev/null 2>&1; rc=$?
row plain-git "(in sub/) $FROM" $rc "sub/c=$(cat "$d/sub/c") c=$(cat "$d/c") | $(st "$d")"
(cd "$d/sub" && git add -- "c"); row plain-git "(in sub/) git add -- \"c\"" $? "$(st "$d")"

d=$ROOT/p2; mkhist "$d"
(cd "$d/sub" && bash -c "$FROMX") >/dev/null 2>&1; rc=$?
row plain-git "(in sub/) $FROMX" $rc "x=$(tr '\n' ' ' < "$d/sub/x") mode=$(stat -c %a "$d/sub/x") | $(st "$d")"

d=$ROOT/p3; mkhist "$d"; echo uncommitted > "$d/sub/c"
(cd "$d/sub" && bash -c "$MISS") >/dev/null 2>&1; rc=$?
row plain-git "(in sub/) $MISS" $rc "sub/c=$(cat "$d/sub/c") leftover-tmp=n/a | $(st "$d")"

d=$ROOT/p4; mkdel "$d"; before=$(st "$d")
(cd "$d" && git rm --cached -- d) >/dev/null 2>&1; r1=$?
(cd "$d" && rm -- d); r2=$?
row plain-git "git rm --cached -- d; rm -- d   (modify/delete conflict)" "$r1/$r2" "before: $before after: $(st "$d") d=$([ -e "$d/d" ] && echo present || echo gone)"
(cd "$d" && git commit -qm merge) >/dev/null 2>&1
row plain-git "git commit" $? "d in HEAD: $(git -C "$d" ls-tree --name-only HEAD | tr '\n' ' ')"

sbx() { env -i PATH="$PATH" HOME="$HOME" CODEX_HOME="$CH" GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 \
  codex sandbox -P workspace-local -C "$1" -- bash -c "$2" 2>&1 | grep -v '^WARNING: proceeding' | head -3; return "${PIPESTATUS[0]}"; }

m=$OUTSIDE/m5; w=$ROOT/w5; mkhist "$m"; git -C "$m" worktree add -q "$w" -b w5 >/dev/null 2>&1; guard "$w"; echo uncommitted > "$w/c"
out=$(sbx "$w/sub" "$FROM"); rc=$?
row sandbox-wt "(in sub/) $FROM" $rc "sub/c=$(cat "$w/sub/c") c=$(cat "$w/c") | $(st "$w") ${out:+| $out}"
out=$(sbx "$w/sub" 'git add -- "c"'); rc=$?
row sandbox-wt "(in sub/) git add -- \"c\" sandboxed (an allow rule skips this)" $rc "${out:-ok}"

m=$OUTSIDE/m6; w=$ROOT/w6; mkdel "$m"; git -C "$m" merge --abort; git -C "$m" worktree add -q "$w" -b w6 >/dev/null 2>&1; guard "$w"
git -C "$w" merge -q other >/dev/null 2>&1; before=$(st "$w")
git -C "$w" rm --cached -- d >/dev/null 2>&1; r1=$?   # allow rule: skips the sandbox
out=$(sbx "$w" 'rm -- d'); r2=$?
row sandbox-wt "git rm --cached -- d (unsandboxed); rm -- d (sandboxed)" "$r1/$r2" "before: $before after: $(st "$w") d=$([ -e "$w/d" ] && echo present || echo gone) ${out:+| $out}"
