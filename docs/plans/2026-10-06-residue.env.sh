# Sourced at the top of every shell block of docs/plans/2026-10-06-residue.md.
# Shell state does not carry from one block to the next; this file is the state.
TACK="$(tasks root tack-dcb11a --pretty)"; OPS="$(tasks root ops-cb9749 --pretty)"; LORE="$(tasks root lore-d6acd5 --pretty)"
[ -n "$TACK" ] && [ -n "$OPS" ] && [ -n "$LORE" ] || { echo "REFUSE: a project root did not resolve (tack, ops or lore)"; return 1; }
WT="$TACK/.worktrees/tack-dcb11a"; OPS_WT="$OPS/.worktrees/facts-mirror"; LORE_WT="$LORE/.worktrees/archive-intake"
STEP1=tack-83c9a5; STEP2=tack-c920fa; STEP3=tack-3464bc; STEP4=tack-e5e905; STEP5=tack-ad1552; STEP6=tack-88d917
STEP7=tack-09055e; STEP8=tack-f548ee; STEP9=tack-23abd5; STEP10=tack-8c30c0; STEP11=tack-595dc5
# Values a later block needs (the ids of tasks filed in ops and lore, the audit script,
# the list of files edited at the archive's intake, the last command's log). git ignores
# the directory through the user's global ignore file, not through this repository's.
STATE="$WT/.superpowers/sdd/2026-10-06-residue"; mkdir -p "$STATE"
OPS_TASK="$(cat "$STATE/ops-task" 2>/dev/null)"; LORE_TASK="$(cat "$STATE/lore-task" 2>/dev/null)"
# t CMD…: run it, print its last line, keep its exit status; a failure names the full log.
T_LOG="$STATE/last.log"
t() { "$@" > "$T_LOG" 2>&1; local rc=$?; tail -n 1 "$T_LOG"; [ "$rc" = 0 ] || echo "FAILED ($rc): full output in $T_LOG"; return $rc; }
# need NAME…: refuse when a named variable is empty.
need() { local name; for name in "$@"; do eval "[ -n \"\${$name}\" ]" || { echo "REFUSE: $name is not set"; return 1; }; done; }
