#!/usr/bin/env bash
# hq-48c5c6: build the fixture for the live Codex turn. Main checkout under ~/.cache
# (outside the sandbox's writable roots), linked worktree under the task directory.
# In the worktree: f staged with unstaged edits on top, c conflicted mid-merge.
# Prints the worktree path. Remove with: git -C <main> worktree remove --force <wt>; rm -r <main> <wt-parent>
set -euo pipefail
for v in $(env | sed -n 's/^\(GIT_[A-Z_]*\)=.*/\1/p'); do unset "$v"; done
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 \
  GIT_AUTHOR_NAME=probe GIT_AUTHOR_EMAIL=probe@example.invalid \
  GIT_COMMITTER_NAME=probe GIT_COMMITTER_EMAIL=probe@example.invalid
M=$(mktemp -d -p "$HOME/.cache" hq-48c5c6-live.XXXX)
W=$(mktemp -d -p "$WORK_ROOT/hq/hq-48c5c6" live.XXXX)/wt
git init -q -b main "$M"
[ "$(git -C "$M" rev-parse --show-toplevel)" = "$(cd "$M" && pwd -P)" ] || { echo "fixture escaped" >&2; exit 2; }
case "$(git -C "$M" rev-parse --absolute-git-dir)" in "$(cd "$M" && pwd -P)"/*) ;; *) echo "gitdir escaped" >&2; exit 2;; esac
echo base > "$M/c"; echo readme > "$M/README"; git -C "$M" add -A; git -C "$M" commit -qm base
git -C "$M" switch -qc other; echo theirs > "$M/c"; git -C "$M" commit -qam theirs
git -C "$M" switch -qc wt main; echo ours > "$M/c"; git -C "$M" commit -qam ours
git -C "$M" switch -q main
git -C "$M" worktree add -q "$W" wt
git -C "$W" merge -q other >/dev/null 2>&1 || true
echo staged > "$W/f"; git -C "$W" add f; echo unstaged-edit >> "$W/f"
echo "main=$M"
echo "wt=$W"
git -C "$W" status --short
