#!/usr/bin/env bash
# hq-748431: run git unstaging and conflict-side forms under Codex's sandbox
# (workspace-local profile copied into a temporary CODEX_HOME). No model, no auth.
set -uo pipefail
for v in $(env | sed -n 's/^\(GIT_[A-Z_]*\)=.*/\1/p'); do unset "$v"; done
SRC_CONFIG=$1
ROOT=$(mktemp -d -p "$WORK_ROOT/hq/hq-748431" run.XXXX)
OUTSIDE=$(mktemp -d -p "$HOME/.cache" hq-748431.XXXX)   # not a writable root
trap 'rm -r -- "$ROOT" "$OUTSIDE"' EXIT INT TERM
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 \
  GIT_AUTHOR_NAME=probe GIT_AUTHOR_EMAIL=probe@example.invalid \
  GIT_COMMITTER_NAME=probe GIT_COMMITTER_EMAIL=probe@example.invalid
CH=$ROOT/codex-home; mkdir -p "$CH"
{ echo 'default_permissions = "workspace-local"'; echo 'approval_policy = "never"';
  sed -n '/^\[permissions\.workspace-local\]/,/^\[shell_environment_policy\]/p' "$SRC_CONFIG" | sed '$d'; } > "$CH/config.toml"

mkrepo() { # $1 dir: repo with staged f and a conflicted merge on c
  local d=$1; git init -q -b main "$d"
  [ "$(git -C "$d" rev-parse --show-toplevel)" = "$(cd "$d" && pwd -P)" ] || { echo "fixture escaped"; exit 2; }
  case "$(git -C "$d" rev-parse --absolute-git-dir)" in "$(cd "$d" && pwd -P)"/*) ;; *) echo "gitdir escaped"; exit 2;; esac
  echo base > "$d/c"; git -C "$d" add c; git -C "$d" commit -qm base
  git -C "$d" switch -qc other; echo theirs > "$d/c"; git -C "$d" commit -qam theirs
  git -C "$d" switch -q main; echo ours > "$d/c"; git -C "$d" commit -qam ours
}
prep() { # $1 worktree dir: conflicted merge + staged new file f
  git -C "$1" merge -q other >/dev/null 2>&1
  echo new > "$1/f"; git -C "$1" add f
}
FORMS=(
  "git restore --staged -- f"
  "git reset -q -- f"
  "git rm --cached -q f"
  "git checkout MERGE_HEAD -- c"
  "git show MERGE_HEAD:c > c && git add c"
  "git show MERGE_HEAD:c > c"
  "git restore --source=MERGE_HEAD --staged --worktree c"
)
run_case() { # $1 label, $2 setup fn
  local i=0
  for form in "${FORMS[@]}"; do
    i=$((i+1)); local d; d=$($2 "$i")
    prep "$d"
    out=$(env -i PATH="$PATH" HOME="$HOME" CODEX_HOME="$CH" TMPDIR="$ROOT" \
      GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 \
      codex sandbox -P workspace-local -C "$d" -- bash -c "$form" 2>&1); rc=$?
    printf '%s | %-55s | rc=%s | index: %s | c=%s | %s\n' "$1" "$form" "$rc" \
      "$(git -C "$d" status --porcelain | tr '\n' ';')" "$(head -c 20 "$d/c" | tr '\n' ' ')" "$(echo "$out" | grep -v '^WARNING: proceeding' | tr '\n' ' ' | cut -c1-160)"
  done
}
plain() { local d=$ROOT/plain$1; mkrepo "$d" >/dev/null; echo "$d"; }
plain_outside() { local d=$OUTSIDE/plain$1; mkrepo "$d" >/dev/null; echo "$d"; }
linked_outside() { # as on this host: main checkout and its .git/worktrees admin dir outside writable roots, worktree on writable storage
  local m=$OUTSIDE/main$1 w=$ROOT/wt$1
  mkrepo "$m" >/dev/null; git -C "$m" worktree add -q "$w" -b wt$1 >/dev/null 2>&1; echo "$w"; }
run_case main-in-workroot plain
run_case main-outside-roots plain_outside
run_case worktree-admin-outside linked_outside
