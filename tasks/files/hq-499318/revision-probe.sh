#!/usr/bin/env bash
# hq-499318: check the review's two data-loss cases and the revised forms.
set -uo pipefail
for v in $(env | sed -n 's/^\(GIT_[A-Z_]*\)=.*/\1/p'); do unset "$v"; done
SRC_CONFIG=$1
ROOT=$(mktemp -d -p "$WORK_ROOT/hq/hq-499318" run.XXXX)
OUTSIDE=$(mktemp -d -p "$HOME/.cache" hq-499318.XXXX)   # not a writable root
trap 'rm -r -- "$ROOT" "$OUTSIDE"' EXIT INT TERM
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 \
  GIT_AUTHOR_NAME=probe GIT_AUTHOR_EMAIL=probe@example.invalid \
  GIT_COMMITTER_NAME=probe GIT_COMMITTER_EMAIL=probe@example.invalid
CH=$ROOT/codex-home; mkdir -p "$CH"
{ echo 'default_permissions = "workspace-local"'; echo 'approval_policy = "never"';
  sed -n '/^\[permissions\.workspace-local\]/,/^\[shell_environment_policy\]/p' "$SRC_CONFIG" | sed '$d'; } > "$CH/config.toml"
mkrepo() {
  local d=$1; git init -q -b main "$d"
  [ "$(git -C "$d" rev-parse --show-toplevel)" = "$(cd "$d" && pwd -P)" ] || { echo "fixture escaped"; exit 2; }
  case "$(git -C "$d" rev-parse --absolute-git-dir)" in "$(cd "$d" && pwd -P)"/*) ;; *) echo "gitdir escaped"; exit 2;; esac
  echo base > "$d/c"; git -C "$d" add c; git -C "$d" commit -qm base
  git -C "$d" switch -qc other; echo theirs > "$d/c"; git -C "$d" commit -qam theirs
  git -C "$d" switch -q main; echo ours > "$d/c"; git -C "$d" commit -qam ours
}
prep() { git -C "$1" merge -q other >/dev/null 2>&1; echo staged > "$1/f"; git -C "$1" add f; echo uncommitted >> "$1/f"; }
show() { printf '%-26s | %-95s | rc=%s | index: %s | f=%s | c=%s\n' "$1" "$2" "$3" \
  "$(git -C "$4" status --porcelain | tr '\n' ';')" "$( [ -e "$4/f" ] && tr '\n' ' ' < "$4/f" || echo MISSING)" "$(head -c 20 "$4/c" | tr '\n' ' ')"; }
plain_run() { # plain git, no sandbox: the data-loss cases themselves
  local i=$1 form=$2 d=$ROOT/p$1; mkrepo "$d" >/dev/null; prep "$d"
  (cd "$d" && bash -c "$form" >/dev/null 2>&1); show plain-git "$form" $? "$d"; }
sandbox_run() { # codex sandbox in a linked worktree whose admin dir is outside writable roots
  local i=$1 form=$2 tmpdir=$3 m=$OUTSIDE/m$1 w=$ROOT/w$1
  mkrepo "$m" >/dev/null; git -C "$m" worktree add -q "$w" -b w$1 >/dev/null 2>&1; prep "$w"
  local envtmp=(); [ -n "$tmpdir" ] && envtmp=(TMPDIR="$tmpdir")
  out=$(env -i PATH="$PATH" HOME="$HOME" CODEX_HOME="$CH" "${envtmp[@]}" GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 \
    codex sandbox -P workspace-local -C "$w" -- bash -c "$form" 2>&1); rc=$?
  show "sandbox-wt TMPDIR=${tmpdir:-unset}" "$form" $rc "$w"
  echo "$out" | grep -v '^WARNING: proceeding' | sed 's/^/    /' | head -3; }
SAFE='tmp=$(mktemp) && git show :3:./c > "$tmp" && cp "$tmp" "c" && rm "$tmp"'
MISS='tmp=$(mktemp) && git show :3:./missing > "$tmp" && cp "$tmp" "c" && rm "$tmp"'
plain_run 1 'git rm --cached --no-cached -f -- f'
plain_run 2 'git rm --cached -- f'
plain_run 3 'git rm --cached -- --no-cached -f f'
plain_run 4 'git show MERGE_HEAD:missing > c'
plain_run 5 "$SAFE"
plain_run 6 "$MISS"
sandbox_run 7 "$SAFE" ""
sandbox_run 8 "$SAFE" "${TMPDIR:-/tmp}"
sandbox_run 9 "$MISS" "${TMPDIR:-/tmp}"
