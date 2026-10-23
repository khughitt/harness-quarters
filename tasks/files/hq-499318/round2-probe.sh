#!/usr/bin/env bash
# hq-499318 review round 1: git rm --cached on tracked files; conflict form from a subdirectory; stage-number form.
set -uo pipefail
for v in $(env | sed -n 's/^\(GIT_[A-Z_]*\)=.*/\1/p'); do unset "$v"; done
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_AUTHOR_NAME=p GIT_AUTHOR_EMAIL=p@x.invalid GIT_COMMITTER_NAME=p GIT_COMMITTER_EMAIL=p@x.invalid
R=$(mktemp -d -p "$WORK_ROOT/hq/hq-499318" r2.XXXX); trap 'rm -r -- "$R"' EXIT
fixture() { local d=$1; git init -q -b main "$d"
  [ "$(git -C "$d" rev-parse --show-toplevel)" = "$(cd "$d" && pwd -P)" ] || exit 2
  case "$(git -C "$d" rev-parse --absolute-git-dir)" in "$(cd "$d" && pwd -P)"/*) ;; *) exit 2;; esac
  echo base > "$d/t"; git -C "$d" add t; git -C "$d" commit -qm base; }
echo "## git rm --cached -- on a tracked file"
for case in staged-edit unstaged-edit; do d=$R/rm-$case; fixture "$d"
  echo edit >> "$d/t"; [ $case = staged-edit ] && git -C "$d" add t
  (cd "$d" && git rm --cached -q -- t >/dev/null 2>&1); rc=$?
  printf '%-14s | git rm --cached -- t | rc=%s | index: %s\n' $case $rc "$(git -C "$d" status --porcelain t | tr '\n' ';')"
  d=$R/rs-$case; fixture "$d"; echo edit >> "$d/t"; [ $case = staged-edit ] && git -C "$d" add t
  (cd "$d" && git reset -q -- t >/dev/null 2>&1); rc=$?
  printf '%-14s | git reset -q -- t    | rc=%s | index: %s\n' $case $rc "$(git -C "$d" status --porcelain t | tr '\n' ';')"
done
echo "## conflict side from a subdirectory (conflict on sub/c; top-level c also exists)"
conflict() { local d=$1; git init -q -b main "$d"
  [ "$(git -C "$d" rev-parse --show-toplevel)" = "$(cd "$d" && pwd -P)" ] || exit 2
  mkdir "$d/sub"; echo topbase > "$d/c"; echo subbase > "$d/sub/c"; printf 'x\n' > "$d/sub/m"; chmod +x "$d/sub/m"
  git -C "$d" add -A; git -C "$d" commit -qm base
  git -C "$d" switch -qc other; echo topTHEIRS > "$d/c"; echo subTHEIRS > "$d/sub/c"; printf 'theirs\n' > "$d/sub/m"; git -C "$d" commit -qam theirs
  git -C "$d" switch -q main; echo subOURS > "$d/sub/c"; printf 'ours\n' > "$d/sub/m"; git -C "$d" commit -qam ours
  git -C "$d" merge -q other >/dev/null 2>&1; }
i=0
for form in \
  'tmp=$(mktemp) && git show MERGE_HEAD:c > "$tmp" && cp "$tmp" c && rm "$tmp"' \
  'tmp=$(mktemp) && git show MERGE_HEAD:./c > "$tmp" && cp "$tmp" c && rm "$tmp"' \
  'tmp=$(mktemp) && git show :3:./c > "$tmp" && cp "$tmp" "c" && rm "$tmp"' \
  'tmp=$(mktemp) && git show :2:./c > "$tmp" && cp "$tmp" "c" && rm "$tmp"' \
  'tmp=$(mktemp) && git show :3:./missing > "$tmp" && cp "$tmp" "c" && rm "$tmp"' \
  'tmp=$(mktemp) && git show :3:./m > "$tmp" && cp "$tmp" "m" && rm "$tmp"'; do
  i=$((i+1)); d=$R/cf$i; conflict "$d"
  (cd "$d/sub" && bash -c "$form" >/dev/null 2>&1); rc=$?
  printf '%-80s | rc=%s | sub/c=%s | sub/m=%s mode=%s\n' "$form" $rc "$(tr '\n' ' ' < "$d/sub/c" | cut -c1-24)" "$(tr '\n' ' ' < "$d/sub/m")" "$(stat -c %a "$d/sub/m")"
done
echo "## stage form during a rebase conflict"
d=$R/rb; conflict "$d"; git -C "$d" merge --abort; git -C "$d" switch -q other; git -C "$d" rebase -q main >/dev/null 2>&1
(cd "$d/sub" && bash -c 'tmp=$(mktemp) && git show :3:./c > "$tmp" && cp "$tmp" "c" && rm "$tmp"' >/dev/null 2>&1); rc=$?
printf 'rebase other onto main, :3:./c from sub | rc=%s | sub/c=%s\n' $rc "$(tr '\n' ' ' < "$d/sub/c")"
git --version
