#!/usr/bin/env bash
# Probe: what tasks rename does to a detached project's records repository.
# Run with bash; it touches only a fresh mktemp sandbox (HOME, XDG dirs, git config).
set -euo pipefail
T=$(mktemp -d)
for v in $(env | grep -o '^GIT_[A-Z_]*'); do unset "$v"; done
export HOME=$T/home XDG_CONFIG_HOME=$T/cfg XDG_STATE_HOME=$T/state GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
unset WORK_ROOT TASKS_SESSION
mkdir -p "$HOME" "$XDG_CONFIG_HOME" "$XDG_STATE_HOME" "$T/sync/code" "$T/sync/records" "$T/x"
R=$T/sync/records C=$T/sync/code
git -C "$R" init -q -b main; git -C "$R" commit -q --allow-empty -m init
git -C "$C" init -q -b main; echo x > "$C/f"; git -C "$C" add -A; git -C "$C" commit -qm init
cd "$C"; tasks init --prefix ai --records "$R"; git -C "$R" add -A; git -C "$R" commit -qm config
echo "--- records after init"; git -C "$R" status --short; git -C "$R" log --oneline; cat "$R/ai/tasks/.config.toml"
id=$(tasks add one --process direct | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d.get("id") or d["task"]["id"])')
echo hi > "$T/x/a.png"; tasks attach "$id" "$T/x/a.png" >/dev/null
echo "--- records after add+attach"; git -C "$R" log --oneline; git -C "$R" status --short
echo "=== rename"; tasks rename ai tack; echo "rc=$?"
echo "--- records after rename"; git -C "$R" log --oneline; git -C "$R" status --short
(cd "$R" && find . -path ./.git -prune -o -type f -print)
cat "$XDG_CONFIG_HOME/tasks/projects.toml"
echo "--- code"; git -C "$C" status --short
tasks projects | python3 -c 'import json,sys;[print(r) for r in json.load(sys.stdin)["projects"]]'
echo "=== where from records dir"; tasks where "$R/tack/tasks"
echo "=== check from code"; tasks check; echo "check rc=$?"
echo "=== init --force --records after moving checkout"
mv "$C" "$T/sync/code2"; cd "$T/sync/code2"; tasks init --prefix tack --force --records "$R" || echo "init rc=$? (expected: refuses to relink)"
cat "$XDG_CONFIG_HOME/tasks/projects.toml"
echo "=== resolve old id"; tasks resolve "ai-${id#ai-}" "$C"
echo "T=$T"
