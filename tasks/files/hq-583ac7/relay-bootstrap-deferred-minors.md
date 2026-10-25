Task 1: minor (deferred): test_decision_scope_survives_expected_pid_exit models no PID exit (tautological first half; rename or drop PID wording; real PID tests are Task 6's).
Task 1: minor (deferred): report's mutation evidence "dropping subject binding: 1 failed" should be 2 (wrong-subject case too) — evidence question, not code.
Task 1: minor (deferred): fault recorder wraps only os.* calls, not builtins.open/shutil/chmod/symlink; writes_since()==[] is weaker than it reads.
Task 1: minor (deferred): _exclusive_write temp unlink after dir fsync — a crash leaves a temp name in decisions/ that blocks all later consumption with no tool path out; runbook must name the cleanup.
Task 1: minor (deferred): state.py:274 TypeError (not Stop) when active.json `window` is non-hashable.
Task 1: minor (deferred): decision record uses a second JSON encoder without allow_nan=False/schema check; share one _encode.
Task 1: minor (deferred): reserved-name check covers only first path component/final suffix (artifact `<window>/claude.original/x.json` or `<window>/hosts/host-b/timers.json`).
Task 1: minor (deferred): read_ledger checks less than register_target (window dir check, artifact inside window, duplicate artifacts) — Task 5 passes these to relay rollback.
Task 1: minor (deferred): future-dated answered_at accepted (lower bound only).
Task 1: minor (deferred): crash after mkdir before window.json yields "window.json: missing" with no reconcile guidance; untested; and _temp unlink failure can mask the original error.
Task 2: minor (deferred): _members requires pgrp==leader and session==leader; setpgid descendants escape cleanup (hosts.py:545).
Task 2: minor (deferred): lost-reply _settle polls every 1 s with new SSH connection and transport log each; never pruned (hosts.py:67, 386-411, 242-247).
Task 2: minor (deferred): helper digest gate also blocks operation-status/cancel on drift (hosts.py:955-957).
Task 2: minor (deferred): signal race windows — after spec.run returns before interrupts.open=False; between _launch and owned.live registration; after client launch in start_request (hosts.py:861, 899-904, 671-675, 278-295).
Task 2: minor (deferred): on host-a _abandon TERM/KILLs the owner itself 5 s after explicit cancel, can orphan children (hosts.py:276, 325-340).
Task 2: minor (deferred): no explicit cwd for host-a client/children; git/npm read controller cwd config (hosts.py:279, 671).
Task 2: minor (deferred): OSError launching git swallowed while blocker points to a private log that was not written (hosts.py:1180-1185).
Task 2: minor (deferred): op directory without start.json after SIGKILL/power loss blocks gate/status/cancel with no named remedy (hosts.py:805, 732).
Task 2: minor (deferred): local refusals raise Refused but remote refusals return status "refused"; undocumented dual contract (hosts.py:257-271 vs 457-492).
Task 2: minor (deferred): process classification misses Claude under node exe (report-only) (hosts.py:1442-1443).
Task 2: minor (deferred): python3 --version not intercepted in inventory tests (test:350, 1009).
Task 3: minor (deferred): parsed-JSON `==` lets true→1 / 2→2.0 non-pick drift pass (inputs.py:337; Codex whole-object too) — Task 4's comparisons are told to use type-exact canonical comparison.
Task 3: minor (deferred): digest-record proof ignores the record's path column (inputs.py:279).
Task 3: minor (deferred): blocked check prints `next: prepare` that _open refuses; recheck's "no window is open" text wrong in Task 4 flow (cli.py:77-78, window.py:413-414, 443).
Task 3: minor (deferred): plain Stop reported as host host-a/step=command; SIGINT between requests in prepare/check prints a traceback (cli.py:117-120).
Task 3: minor (deferred): _call drops the log path on Interrupted/Unsettled/Refused (window.py:115-124).
Task 3: minor (deferred): abort takes no root lock; concurrent aborts rely on compare-then-write (window.py:150-159, 662-680, 710-729).
Task 3: minor (deferred): test gaps — env-node assertion silently skipped without system node; no signal-between-requests test; python-changed never changes the binary.
Task 3: minor (deferred): bootstrap tests import the transport test module for World; inputs.py imports quiesce only for readiness.
Task 3: minor (deferred): test latency — the two new test files take ~190 s and the hooks/tools suite grew from 259 s (baseline) to 470 s; the final review should triage slow fixtures (real waits/sleeps) before more tasks add to them.
Task 3: minor (deferred): cli.py reaches window._root() and window.PREPARED across the module boundary (pre-existing, re-review out-of-scope).
Task 3: minor (deferred): a torn timer record on a host that did stop timers ends abort-incomplete "inspect" by design; rare (record written before any stop).
Task 4: minor (deferred): consent accepts `y` while text says "Type yes" (cli.py:33 vs :119).
Task 4: minor (deferred): handoff names "printed held commands" that run does not print (cli.py:183) — Task 7 adds them.
Task 4: minor (deferred): consent preview caps fields but not the number of surfaces/processes listed (cli.py:105-120).
Task 4: minor (deferred): decision-file check accepts 0644 (cli.py:158).
Task 4: minor (deferred): seal does not require both hosts per Claude target; `found` reused (targets.py:461-478).
Task 4: minor (deferred): npm cache recorded twice (familiar.py:157).
Task 4: minor (deferred): verified[host]["targets"] stores expected digests not observations (window.py:660).
Task 4: minor (deferred): prepare↔window import cycle via function-local import; move consent subject to a lower module (window.py:513, prepare.py:185).
Task 4: minor (deferred): try→_as_failed→_abort_after block repeated 4× in window.py (528/538/544/581); context-manager helper.
Task 4: minor (deferred): familiar.py calls private targets._helper (familiar.py:50, 62).
Task 4: minor (deferred): coverage — no orchestrated host-a dry-run failure; no post-merge target-apply failure with partial ledger (latter is Task 5's area).
Task 4: minor (deferred): Failed.aborted contract — any future caller wrapping a window step must check it, or an abort could run twice.
Task 5: minor (deferred): inspection classified by step, not cause — targets.closed refusal or non-zero restore exit reported as "bytes match no image" (recovery.py:298-300, restoration.py:222-224).
Task 5: minor (deferred): stale earlier-attempt originals/dependencies kept so _summary can over-report; SIGKILLed attempt status falls back to run failure (recovery.py:164-169, 282-293; window.py:754).
Task 5: minor (deferred): interrupted target restore between relay rollback and guard restore untested (fixture fault rollback:<id> unused) — Review Focus 4.
Task 5: minor (deferred): _settle owner-lost cancel branch and this-window running-op blocker untested; recovery.cancelled never asserted.
Task 5: minor (deferred): test_post_resume_pick_drift_refuses_restore mutates class world and must stay last (test-order dependence).
Task 5: minor (deferred): entry["original"] not confined to the window like the artifact path (restoration.py:116 vs 119-122).
Task 5: minor (deferred): RELAY defined twice; target-check payload built twice.
Task 5: minor (deferred): recovery.py:233 function-local `from .cli import command_line` (cycle smell).
Task 6: minor (deferred): TDD order deviation — implementation before tests; tests fail on base for the right reasons and killed 16 mutations.
Task 6: minor (deferred, final review should triage — can strand a window): pending_failure treats protocol/helper-identity `refused` and local never-started `failed` as drift → one-way inspection-required (surfaces.py:645).
Task 6: minor (deferred): recovery preview reports the tool's own journaled forward replacement as an unrecorded process (surfaces.py:192).
Task 6: minor (deferred): duplicated consent check in authorized vs probe, already diverged (probe skips window_id/prepared_sha256) (surfaces.py:494-501, 755-762).
Task 6: minor (deferred): cli builds changes dict 3×; _terminal repeats _ask; _promote re-implements _save.
Task 6: minor (deferred): RUN_ACTION copied from window; bottom-of-module import works around surfaces↔window↔recovery cycle (surfaces.py:49, 784).
Task 6: minor (deferred): recover success text says surfaces restarted even when all hosts were explained absences.
Task 6: minor (deferred): untested — stage-5 failure inside recover; interrupted-at-checkpoint branch (window.py:572); restart-surfaces cancelling own owner-lost surface op.
Task 7: minor (deferred): snapshot:null read as empty registry → absence checks pass vacuously (smoke.py:199-201, 693; finish.py:179).
Task 7: minor (deferred): closure does not require intent present (finish.py:179).
Task 7: minor (deferred): attribution-denial accepts any 0-commit observation incl. one before the denial (smoke.py:737).
Task 7: minor (deferred): `done` bound only by construction (smoke.py:749-759).
Task 7: minor (deferred): handoff catch too broad (KeyError/TypeError) (smoke.py:174).
Task 7: minor (deferred): unhashable receipt host → TypeError traceback (smoke.py:506).
Task 7: minor (deferred): check during an open window prints pre-window CLOSURE guidance (cli.py:477-478); status prints CLOSURE after complete (cli.py:466-467).
Task 7: minor (deferred): --cwd resolved on host-a for --observe host-b (cli.py:528).
Task 7: minor (deferred): status names restored timers as paused after partial finish (window.py:813-821).
Task 7: minor (deferred): receipt placeholder printed quoted (cli.py:91-92).
Task 7: minor (deferred): finish drift → inspection-required tested host-side only (finish.py:216-245).
Task 7: minor (deferred): _Receipt temporal coupling live()↔cases(); smoke.py 935 lines.
Task 7: minor (deferred, final review should triage): surface retry from ready-for-smokes/finishing uses Task 6's exact-bytes recheck, so a saved Claude pick (forbidden) turns a one-step retry into full recovery; finish tolerates picks; plan says live pick changes do not fail hook verification.
Task 7: minor (deferred): validate_smokes bare-indexes consumed_sha256 (pre-fix in-flight windows only).
Task 7: minor (deferred): surfaces.unwell treats unrecognised change lines as retry-everything on that host.
Task 8: minor (deferred): inventory gate failures don't stop the rehearsal before pilot-create/npm (pilot.py:510-515, 902-920).
Task 8: minor (deferred): unknown steps default to the restore gate; host-b disconnect-clone merge maps to source (pilot.py:966).
Task 8: minor (deferred): unexercised list omits host-b's synced-merge wait (pilot.py:73).
Task 8: minor (deferred, final review should triage — strands live commands): an unrun preview can only be closed by running the whole rehearsal; dead "another preparation" branch (pilot.py:380-382, 1023).
Task 8: minor (deferred): "≤5 minutes" not enforced (cli.py:770).
Task 8: minor (deferred): no offline recovery after an Unsettled disconnect install before cleanup deletes it (pilot.py:844-845).
Task 8: minor (deferred): early client exit before durable start waits out the whole deadline (pilot.py:749-753, 701-719).
Task 8: minor (deferred): status reads now fail on unreadable children.json for every record incl. live (hosts.py:790-792).
Task 8: minor (deferred): latched drops not visible in summary (cli.py:849).
Task 8: minor (deferred): full rehearsal test accepts one or two disconnect attempts (test:5359); disconnect test timing-dependent (3 s slow npm).
Task 8: minor (deferred): containment exclusion of all windows/ and active.json too broad (transport test:3633).
Task 8: minor (deferred): helper --root refuses only final-component symlink; --host --root forwarding untested (tools/relay-cutover:131, 306).
Task 8: minor (deferred, final review should triage — strands live commands): orphan scratch root without scratch.json blocks pilot_cleanup and every live command with no named recovery (pilot.py:196-198, 292).
Task 8: minor (deferred): after-freeze fixture walks four dirname levels to find scratch home (fixture-only brittleness).
Task 9: minor (deferred): orphan pilot root criteria describe contents the code never produces (runbook:860-865).
Task 9: minor (deferred): restart-surfaces "What stops it" mixes new-inventory changes with preview-stopping blockers (runbook:535-539).
Task 9: minor (deferred): approval.marker target dir created only in a later block, so the approved touch fails (runbook:968 vs 598-599).
Task 9: minor (deferred): "only writes" overstates prepare/check (held probe home-state bookkeeping, R43); rehearse row omits SSH runtime/probe effects (runbook:111-115, 123-126).
Task 9: minor (deferred): status table after complete shows check/prep guidance (runbook:794; Task 7 minor cli.py:499-500).
Task 9: minor (deferred): attestation prompt is "Type yes to attest", not "approve" (runbook:131).
Task 9: minor (deferred): orphan inspection blocks for host-b are bare local commands (runbook:852-872).
Final review: minor (deferred): M1 _abort_after overwrites next command with run (window.py:446).
Final review: minor (deferred): M2 second SIGHUP cancels the abort's own timer-restore (window.py:401-419).
Final review: minor (deferred): M3 dead SSH link waits full deadline; completed durable response still raises Unsettled; keepalive needs plan amendment (hosts.py:51, 532-533).
Final review: minor (deferred): M4 no type-ahead flush before consent prompt (cli.py:227-229).
Final review: minor (deferred): M5 decision files may claim source.type tty (cli.py:281-293, state.py:421-431).
Final review: minor (deferred): M6 run without terminal allocates then aborts a window (cli.py:320-334).
Final review: minor (deferred): M7 executables/remote ENTRY not isolated from PYTHONPATH/user site; -E -s needs plan amendment.
Final review: minor (deferred): M8 recovery Codex daemon stop refuses when ~/.local/bin/codex no longer resolves (quiesce.py:103-105).
Final review: minor (deferred): T8 unrun pilot preview closable only by rehearsing (a never-run `rehearse --discard` is a cheap later fix).
Final review: minor (deferred): add "host-b's synchronized-merge wait" to pilot UNEXERCISED; runbook line "helper drift mid-window blocks recover until delivered helper bytes are restored" (folded into docs update).
Final review: minor (deferred): spec R47 note inserted mid-paragraph without a blank line, so the following original sentence renders inside the note (spec:456-461).
Final review: minor (deferred): bypass set misses Codex --sandbox/-s danger-full-access and -c approval_policy=never / -c sandbox_mode=danger-full-access; --dangerously-skip-permissions untested (smoke.py:79-84).
Final review: minor (deferred): _agent_ancestor fails open when the chain cannot reach the agent (separate PID namespace); Codex sandbox mode unverified (cli.py:271-303).
Final review: minor (deferred): CLI's 500-character error truncation can cut operator guidance (hold-breach) when home paths are long.
Final review: minor (deferred): runbook §7 says only unset is personal; for Codex, CODEX_HOME=<realpath ~/.codex> is also personal (runbook:712-715).
Final review: minor (deferred): _Held.release restores handlers one by one before re-raise (mid-loop signal leaves stale _note handlers) and collapses multiple held signals into one (hosts.py:215-221).
Familiar drift: minor (deferred): ls-files --others without --directory lists all node_modules (familiar.py:290; spec-literal change needs ruling).
Familiar drift: minor (deferred): outside-tasks equality relies on diff.autoRefreshIndex default (familiar.py:278).
Familiar drift: minor (deferred): familiar-sync "ahead" message blames host-b when a host-a commit after B also yields it; extra familiar-head child can exceed SYNC+CHILD+60 (familiar.py:390-393).
Familiar drift: minor (deferred): classify recomputes T0 via base_problem; a git upgrade changing ort would block recovery (restoration.py:312).
Familiar drift: minor (deferred): titan_head() labels Failed as familiar-verify during install (window.py:168).
Familiar drift: minor (deferred): deadline checked before the re-read — a final AHEAD after the budget (or host-a moving for the whole budget) counts as a host-b commit without re-read (window.py:176-177); fix: always re-read once, non-final "still synchronizing" refusal when the budget is spent.
Familiar drift: minor (deferred): recovery dependency-restore re-read wiring untested (recovery.py:299-312); failed familiar-head read mislabeled as the proof step; finish records the stale host-a HEAD after a re-read; prepare/status readiness uses a stale host-a base read (rerunnable blocker only).
