# SDD ledger — plan: docs/plans/2026-11-01-session-store-adapters.md

Spec: docs/specs/2026-11-01-session-store-adapters-design.md (reachable). Starting HEAD 5d1b013.
Baseline: `just test` in worktree, started 2026-11-01 (result below).

## Pre-flight scan
| Pair / task | Produces vs consumes | Finding |
|---|---|---|
| T1 / T2 | T1 sets Adapter.archive_sources -> (); T2 fills it, adds harness_stores.archive_sources | consistent |
| T2 / T3 | Source gains required/append_only/descend/select in T2; T3 consumes them | consistent |
| T3 / T5 | check_sources/capture_run skipped; T5 agy rows | consistent |
| T1 / T4 | registry, colour, hq.toml; T4 appends agy | consistent |
| T1,T4 / T6 | episode_env/episode_root fields declared in T1 Adapter | consistent |
| T4,T5,T6 / T7 | facts from findings | consistent |
| T1 own text | tests only cover registry; hq_cli behaviour covered by existing test_hq_sessions | ok |
| T2 own text | test_sources_table says "five rows" ok | ok |
| T3 own text | ok | ok |
| T4 own text | ok | ok |
| T5 own text | ok | ok |
| T6 own text | big task; test list 16 cases | ok, use capable model |
| T7 own text | ok | ok |
No conflicts found; no rulings needed.
Baseline: just test -> 391 passed (4m21s) + 1 relay cutover test; HEAD 5d1b013
Task 1: complete (commits fbe7d2f..5b5ee92, review clean)
  minor (deferred -> Task 4 must handle): cli.py/launch.py index s.cwd as str though Session.cwd may be None; launch.environment keys env[adapter.home_variable] with None for work home of home_variable=None adapter; no direct tests of here_filter(None)/by_alias KeyError/homes() order.
Task 2: complete (commits 5b5ee92..ca14cbc, review clean)
  minor (deferred): duplicate/misordered imports in 3 test files; archive_sources annotated bare `tuple`; codex.py unpacks homes() by order; readiness test inline conditional.
Task 3 review round 1: Important: capture_file rotation lacks promote's hash verification (capture.py:84-90). Fix loop round 1.
Task 3: fix round 1/5 (1 addressed, 0 open — rotation hash guards; commits d4fff5c..1b57a52)
Task 3: complete (commits ca14cbc..1b57a52, review clean after 1 round)
  minor (deferred): damaged-mirror under non-append source wedges (error message says "run capture to repair" which cannot work); crash window between manifest.put(old) and os.replace leaves no mirror row; no CLI-level test for Review Focus 4 (Task 5 covers it); CapturedSources untested; cmd_capture left COMMANDS (special-cased in main).
  note: full `just test` had 1 transient failure (test_unindexed_is_kept_with_reason, /proc fd race); passes alone (17 passed).
Task 4: complete (commits 1b57a52..ef7511b, review clean)
  minor (deferred): agy.read_agy unused `archived` param; archive_sources bare `tuple` annotation + vague comment; NULL title/preview untested (reader rejects non-strings: a live NULL title fails whole listing -- verify at final review against live db); no test for `--harness agy` on host without agy home.
Task 5: complete (commits ef7511b..8df6e8b, review clean)
  minor (deferred): redundant len(parts) check in descend_brain (agy.py:84-88); weak status assertion in summaries-rewrite test; no fixture for stray file under brain/ or nested .system_generated.
Task 6: complete (commits 8df6e8b..e13df65, review clean)
  minor (deferred): USER_EXPLICIT input lacking <USER_REQUEST> silently yields no human turn (fail-early inconsistency vs bad run_command; consider at final review); partial last line in a live transcript stops whole `--harness agy` extract (record for readout); READERS tuples indexed by position; test helper re-imports; sys.path.insert(0, tools).
  observation: 31/32 live agy starts are outside-grammar (agy chains with &&); grammar is shared with Claude, a readout decision, not this plan.
Task 7: complete (commits e13df65..f1e3974, review clean)
  minor (deferred): runbook §7 archive step 3 may still mention claude/codex branches in inputs/decide/prune (verify); README long parenthetical; double blank lines in capabilities.toml. Open gap: agy session-metadata-marks-headless left `unknown` (probe not run: needs OAuth copy).
All 7 tasks complete. Next: final whole-branch review (references/final-review.md).
Final review: verdict With fixes. Important: runbook §7 stale (archive step 2 abort rule; step 3 claude/codex branches) -> fix wave. Minor folded in: transcript-self-describing agy note says episodes reads summaries db (wrong); capture.py:156 repair message misleading.
Ruling: deferred minors from final review stay deferred (NULL title rejection is schema-correct; USER_EXPLICIT without tag; partial last line; damaged-mirror wedge (message only fixed); prune silent about agy; lexists change; layering color import; unused param/annotations etc.) — consequence none for user today; costs a follow-up if agy joins default set before 2027-02-16 readout or a summaries mirror is damaged.
Ruling: listing with linked-but-never-run agy home fails `hq sessions` (final review minor 3) left as spec'd — mirrors .claude-work/.codex-work behaviour; costs one `--harness claude` on a fresh host.
Final: fix wave edc9186d, scoped re-review Approved. Branch feat/agy-transcripts at edc9186d, unmerged.
