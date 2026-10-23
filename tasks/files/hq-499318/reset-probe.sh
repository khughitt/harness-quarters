#!/usr/bin/env bash
set -uo pipefail
for v in $(env | sed -n 's/^\(GIT_[A-Z_]*\)=.*/\1/p'); do unset "$v"; done
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_AUTHOR_NAME=p GIT_AUTHOR_EMAIL=p@x.invalid GIT_COMMITTER_NAME=p GIT_COMMITTER_EMAIL=p@x.invalid
R=$(mktemp -d -p "$WORK_ROOT/hq/hq-499318" reset.XXXX); trap 'rm -r -- "$R"' EXIT
for kind in with-head unborn; do
  for form in 'git reset -q -- f' 'git rm --cached -- f' 'git rm --cached -f -- f'; do
    d=$R/$kind-$RANDOM; git init -q -b main "$d"
    [ "$kind" = with-head ] && { echo b > "$d/b"; git -C "$d" add b; git -C "$d" commit -qm b; }
    echo staged > "$d/f"; git -C "$d" add f; echo uncommitted >> "$d/f"
    (cd "$d" && bash -c "$form" >/dev/null 2>&1); rc=$?
    printf '%-9s | %-24s | rc=%s | index: %-8s | f=%s\n' "$kind" "$form" "$rc" "$(git -C "$d" status --porcelain f | tr '\n' ';')" "$(tr '\n' ' ' < "$d/f")"
  done
done
git --version
