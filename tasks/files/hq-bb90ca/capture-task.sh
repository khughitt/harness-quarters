#!/usr/bin/env bash
# Capture a real `tasks show --json` document over an isolated scratch zz project.
set -euo pipefail
S=$1
rm -rf "$S"; mkdir -p "$S/home" "$S/cfg" "$S/state" "$S/data" "$S/w/zz"
run() {
  env -i PATH="$PATH" HOME="$S/home" XDG_CONFIG_HOME="$S/cfg" XDG_STATE_HOME="$S/state" \
    XDG_DATA_HOME="$S/data" USER=fixture GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 \
    GIT_AUTHOR_NAME=f GIT_AUTHOR_EMAIL=f@f.invalid GIT_COMMITTER_NAME=f GIT_COMMITTER_EMAIL=f@f.invalid \
    CLAUDE_CODE_SESSION_ID=c0000000-0000-4000-8000-000000000022 "$@"
}
cd "$S/w/zz"
run git init -q .
[ "$(run git rev-parse --show-toplevel)" = "$S/w/zz" ]
case "$(run git rev-parse --absolute-git-dir)" in "$S"/*) ;; *) echo "git dir escaped" >&2; exit 1;; esac
run tasks init --prefix zz
run tasks add "Synthetic fixture task" >"$S/add.json"
cat "$S/add.json"
# Give the task the fixture id, stamp a note as session CT1, then set synthetic times.
T="$S/w/zz/tasks"
id=$(sed -n 's/.*"id":"\(zz-[0-9a-f]*\)".*/\1/p' "$S/add.json")
sed "s/^id: $id$/id: zz-000021/" "$T/$id.md" >"$T/zz-000021.md"; rm "$T/$id.md"
run tasks note zz-000021 started --stamp >/dev/null
sed -i -e 's/^created: .*/created: 2026-10-12T11:30:00Z/' -e 's/^updated: .*/updated: 2026-10-12T12:00:30Z/' \
  -e 's/[0-9]\{4\}-[0-9][0-9]-[0-9][0-9]T[0-9:]*Z/2026-10-12T12:00:30Z/g' "$T/zz-000021.md"
sed -i 's/^created: 2026-10-12T12:00:30Z/created: 2026-10-12T11:30:00Z/' "$T/zz-000021.md"
cat "$T/zz-000021.md"
run tasks show zz-000021 --json >"$S/show.json"
