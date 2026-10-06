# Sourced at the top of every shell block of docs/plans/2026-10-06-rename-to-hq-cutover.md
# in Tasks 1 to 9 Step 2; Task 9 Step 2 copies the helpers below into the host-local
# $CUT/env.sh, which every later block sources. Shell state does not carry between blocks.
TACK="$(tasks root tack-8b7a28 --pretty)"
[ -n "$TACK" ] || { echo "REFUSE: tack's root did not resolve"; return 1; }
WT="$TACK/.worktrees/rename-hq-cutover"; BRANCH=feat/rename-hq-cutover; BRANCH8=feat/rename-hq-trial-join
STEP1=tack-13bd17; STEP2=tack-deb33c; STEP3=tack-7df85f; STEP4=tack-bd1eaa; STEP5=tack-89a685
STEP6=tack-4ea672; STEP7=tack-0c2a33; STEP8=tack-7a0161; STEP9=tack-5cd144; STEP10=tack-c9410f
STEP11=tack-39ea31
# Ignored scratch in the worktree (the user's global ignore file covers .superpowers/);
# it never syncs, and it goes with the worktree.
STATE="$WT/.superpowers/sdd/2026-10-06-rename-to-hq-cutover"; [ -d "$WT" ] && mkdir -p "$STATE"
T_LOG="$STATE/last.log"
# The cutover's host-local directory (Tasks 9 to 11): outside every checkout and every
# tasks directory, never synced. The second host keeps its own at the same path.
CUT="$HOME/.local/state/rename-hq"
# --- helpers (copied into $CUT/env.sh by Task 9 Step 2)
# t CMD…: run it, print its last line, keep its exit status; a failure names the full log.
t() { "$@" > "$T_LOG" 2>&1; local rc=$?; tail -n 1 "$T_LOG"; [ "$rc" = 0 ] || echo "FAILED ($rc): full output in $T_LOG"; return $rc; }
# need NAME…: refuse when a named variable is empty.
need() { local name; for name in "$@"; do eval "[ -n \"\${$name}\" ]" || { echo "REFUSE: $name is not set"; return 1; }; done; }
# root_of PREFIX: the project's registered root, through tasks resolve.
root_of() { tasks resolve "$1" --json | python3 -c 'import json,sys; r=json.load(sys.stdin)["results"][0]; sys.exit(1) if r["status"] != "resolved" else print(r["root"])'; }
# on_second SCRIPT: run SCRIPT on the second host with its user PATH.
SECOND="$(cat "$CUT/second-host" 2>/dev/null)"
on_second() { ssh -4 -o BatchMode=yes "$SECOND" "export PATH=\"\$HOME/.cargo/bin:\$HOME/.local/bin:\$HOME/bin:\$PATH\"; $1"; }
# list_timers: each loaded user timer, with what its service runs.
list_timers() { systemctl --user list-timers --all --no-legend | awk '{print $(NF-1)}' | while read -r timer; do svc="$(systemctl --user show -p Unit --value "$timer")"; printf '%s\t%s\n' "$timer" "$(systemctl --user show -p ExecStart -p ExecStartPost --value "$svc" | sed -n 's/.*argv\[\]=\([^;]*\) ;.*/\1/p' | tr '\n' ' ')"; done; }
# carry_memory OLD_ROOT NEW_ROOT: copy each Claude home's project memory to the new root's
# key. A copy an earlier attempt left identical is accepted; a changed one is moved aside,
# never overwritten, and named for reconciliation.
carry_memory() { local home old new aside; for home in "$HOME/.claude" "$HOME/.claude-work"; do
  old="$home/projects/$(printf %s "$1" | tr / -)/memory"; new="$home/projects/$(printf %s "$2" | tr / -)/memory"
  [ -d "$old" ] || continue
  if [ -e "$new" ]; then
    if diff -rq "$old" "$new" >/dev/null; then echo "memory already carried in $home"; continue; fi
    aside="$new.kept-$(date -u +%Y%m%dT%H%M%SZ)"; mv "$new" "$aside" || return 1; echo "KEPT FOR RECONCILIATION: $aside"
  fi
  mkdir -p "$(dirname "$new")" && cp -a "$old" "$new" && echo "memory carried in $home" || return 1
done; }
