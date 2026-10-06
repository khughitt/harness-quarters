# Sourced at the top of every shell block of docs/plans/2026-10-06-rename-to-hq-preparation.md.
# Shell state does not carry from one block to the next; this file is the state.
TACK="$(tasks root tack-8b7a28 --pretty)"
[ -n "$TACK" ] || { echo "REFUSE: tack's root did not resolve"; return 1; }
WT="$TACK/.worktrees/tack-8b7a28"; BRANCH=feat/rename-hq
STEP1=tack-7f60b2; STEP2=tack-0affe4; STEP3=tack-9d44fd; STEP4=tack-358811; STEP5=tack-e5439a
STEP6=tack-d22937; STEP7=tack-421a85
# Values a later block needs (the second host's name, the commits Task 3 merges, the
# host scripts, the last command's log). git ignores the directory through the user's
# global ignore file, not through this repository's; it never syncs to another host.
STATE="$WT/.superpowers/sdd/2026-10-06-rename-to-hq-preparation"; mkdir -p "$STATE"
SECOND="$(cat "$STATE/second-host" 2>/dev/null)"
TASK1_COMMIT="$(cat "$STATE/task1-commit" 2>/dev/null)"; TASK2_COMMIT="$(cat "$STATE/task2-commit" 2>/dev/null)"
# t CMD…: run it, print its last line, keep its exit status; a failure names the full log.
T_LOG="$STATE/last.log"
t() { "$@" > "$T_LOG" 2>&1; local rc=$?; tail -n 1 "$T_LOG"; [ "$rc" = 0 ] || echo "FAILED ($rc): full output in $T_LOG"; return $rc; }
# need NAME…: refuse when a named variable is empty.
need() { local name; for name in "$@"; do eval "[ -n \"\${$name}\" ]" || { echo "REFUSE: $name is not set"; return 1; }; done; }
