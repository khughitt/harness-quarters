# SDD ledger — plan: docs/plans/2026-11-01-harness-manifest.md

Plan frozen: 5a2e525bda1101c9300586efade030f0a1ebbeb3:docs/plans/2026-11-01-harness-manifest.md (sha256 ddc8f0c55cc3b0dbdc31acf1a6cc6c723bb0f89949dd345b7ae9fc484387b553, verified at start)
Spec: docs/specs/2026-11-01-harness-manifest-design.md (read)
Branch: feat/hq-2eba07-harness-manifest; worktree .worktrees/hq-2eba07; controller session claude-code/claude-opus-5-5
Task: hq-2eba07; arm flow-trial-1 flow off; test policy: no .tt.toml -> enabled (full suite gates)
Step children: T1 hq-e8f2db, T2 hq-bfef03, T3 hq-f5ccb6, T4 hq-1a6bba, T5 hq-d2b9cb, T6 hq-746f05
Main divergence at start: HEAD..main has only chore(tasks) commits; none touch .githooks/live-picks (hq-ece26a not landed).

## Pre-flight scan

| Pair / task | Produces vs consumes | Finding |
| --- | --- | --- |
| T1 -> T2 | harnesses.toml (T1) read by tools/harness-facts, test_agy_hooks write_facts_fixture, test_pre_commit_facts fixture (T2) | consistent; harness-facts stays stdlib, no .githooks import |
| T1 -> T3 | TOML_HEADER, TOML_KEY, load_manifest, load_manifest_or_exit, clean_for_spec, LiveStateSpec.pick_keys/pick_units/unrestored_keys/picks_record/format | consistent |
| T1 -> T4 | clean_json, 3-arg clean_toml, TomlKeyRule, filter_re, filter_glob, trust_table | consistent |
| T1 -> T5 | check_filter_config, check_clean_tree, `harness_state.py check --git-dir --staged-tree` | consistent; T1 CLI already supports both flags |
| T3 -> T4 | live-picks drops runpy of harness-state-clean before T4 removes legacy globals | consistent ordering (bisect safety) |
| T3/T4/T5 shared fixtures | test_live_picks, test_codex_trust, test_harness_state_refresh, test_agy_hooks, test_harness_links repo fixtures | sequential only; T3 copies harnesses.toml, T5 adds required=true |
| T4 -> T5 | harness-state-refresh loads manifest (T4), adds check_filter_config (T5) | consistent with spec 5.3.3 split |
| T3 broken-manifest git switch vs T4/T5 | T3 test corrupts harnesses.toml then `git switch`; from T4 harness-state-clean fails on a broken manifest and from T5 required=true makes any filter invocation fatal | risk: test must keep filtered files stat-clean during the switch or it breaks in T4/T5; carried into T3 brief |
| T5 vs spec 5.6 | spec's end-to-end fail-closed test also names routing an unconfigured .toml path through filter=harness-state | plan T5 test omits that case; see Ruling 1 |
| T1 self | tests vs Step 3 code | agrees |
| T2 self | REFUSALS rewrite vs validate signature | agrees |
| T3 self | tests vs Step 3 (usage, load_specs, multi-unit TOML) | agrees |
| T4 self | CLAUDE_JSON_KEYS binding test vs Step 3 | agrees |
| T5 self | Step 4 `just setup` writes shared repo config (outside worktree) | disclosed in Global Constraints, approved with plan; note at the moment per plan |
| T6 self | merge needs user approval | gate kept |
| Global | `just test` takes >10 min on this host | implementers must run it via background Bash with timeout >= 30 min; carried into every dispatch |
| Global | `tasks` commands commit on the branch (chore(tasks)) | BASE recorded after controller's tasks commands; review packages may contain chore(tasks) commits |

Ruling 1: Task 5's test_required_filter_fails_closed_on_broken_manifest_without_leaking_picks also asserts that routing an unconfigured `.toml` path through `filter=harness-state` makes `git add` fail without staging it — Why: spec 5.6 lists that case in the end-to-end fail-closed test and the spec binds over the plan — Cost: one extra assertion block if unnecessary.

## Progress
Setup: baseline just test exit 0 at 19c3366b (1243 + 391 + 1 passed; agents/bin count not captured); noted on hq-2eba07.
Task 1: started; child hq-e8f2db; BASE 079d09b4; implementer sonnet agent af6d9b8f161cdbacc
Task 1: implementer DONE 254ad152 (44 new tests; just test 247+1287+391+1 passed); task review dispatched sonnet agent ac33ba2e90a1da08d on review-079d09b4..254ad152.diff
Task 1: review round 1 (sonnet ac33ba2e90a1da08d): spec ✅, quality Approved; 0 Critical, 0 Important, 6 Minor. Noted on hq-e8f2db.
Ruling: re-grade Task 1 minor 6 (test_check_filter_config_and_cli_check uses monkeypatch.setenv over the inherited environment, so check_filter_config's git subprocess runs with the full inherited env) to Important — Why: the user's global Tests rule requires every test-spawned subprocess env built key by key, never inherited or edited from os.environ, so a failure cannot print a credential — Cost: one small test refactor if wrong.
Ruling: re-grade Task 1 minor 1 (check_clean_tree lets AttributeError escape for a non-object JSON blob such as [], printing a traceback from pre-commit) to Important — Why: the spec's tool contract is `harness-state: <problem>` lines with exit 2 and Review Focus 4 forbids tracebacks; a staged `[]` settings file is a plausible input — Cost: a few lines if wrong.
Task 1: minor (deferred): test_manifest_validation parametrized cases assert only that ManifestError is raised, not which invariant fired (test_harness_manifest.py:715-719)
Task 1: minor (deferred): unused imports Iterable/Sequence in harness_state.py:37 and json in test_harness_manifest.py:542
Task 1: minor (deferred): TREE_SKIP applies at any depth while spec 5.2 names only .git (harness_state.py:54)
Task 1: minor (deferred): check_gitattributes does not flag a bare `filter` / `filter=` without value (harness_state.py:403-410)
Task 1: fix round 1 dispatched to implementer af6d9b8f161cdbacc (FIX_BASE 254ad152): findings env-inheritance in check_filter_config test; AttributeError traceback on non-object JSON
Task 1: fix round 1/5 (2 addressed, 0 open — env isolation in check_filter_config test; non-object JSON refusal; commits 254ad152..b8cf2b71); re-review haiku af2c341e8c9b44e17 clean
Task 1: minor (deferred): clean_json now raises ValueError (was TypeError/AttributeError) for non-object JSON; confirm callers in Task 4 re-export path
Task 1: complete (commits 079d09b4..b8cf2b71, review clean)
Task 2: started; child hq-bfef03; BASE 03586903; implementer sonnet agent a43b591f8be88fb8a
Task 2: implementer DONE 54953664 (focused 110 passed; just test 247+1301+391+1); list/get byte-identical
Task 2: review round 1 (sonnet a9eb4812b0fb83595): spec ✅; 2 Important (run() HOME is the checkout, not a test-owned temp dir — test_harness_facts.py:412; test_the_default_file_is_found_through_a_link subprocess inherits env — :712), 4 Minor. Noted on hq-bfef03.
Ruling: re-grade Task 2 minor "non-table [harnesses.codex] case is vacuous (test_harness_facts.py:482: expects only 'manifest: ' and its replace chain builds a different document)" to Important — Why: the brief lists that refusal explicitly and the test does not pin it, so a listed requirement is untested — Cost: one test edit if wrong.
Task 2: minor (deferred): _load errors do not name which file failed (not valid TOML for manifest vs capabilities) — tools/harness-facts:181-190
Task 2: minor (deferred): run() silently appends --manifest when a sibling harnesses.toml exists — test_harness_facts.py:406-411
Task 2: minor (deferred): manifest failure returns before capabilities.toml is read, so combined problems are not reported together — tools/harness-facts:200-205
Task 2: fix round 1 dispatched to implementer a43b591f8be88fb8a (FIX_BASE 54953664)
Task 2: fix round 1/5 (3 addressed, 0 open — temp HOME in run(); env for link test; specific non-table refusal; commits 54953664..fa6ff5f6); re-review haiku a79b263bb3b6a393f clean
Task 2: complete (commits 03586903..fa6ff5f6, review clean)
Task 3: started; child hq-f5ccb6; BASE 4a5f1fe8; HEAD..main touches no .githooks/live-picks (hq-ece26a not landed); implementer opus agent ae38192d932f3ca37 (judgment-heavy, large file)
Task 3: implementer DONE ee7ce1c9 (test_live_picks 182 passed; just test 247+1314+391+1); concerns: multi-unit test lacks git status asserts until T4; usage order follows manifest; linked-worktree forget bogus reports worktree refusal
Task 3: review round 1 (opus ab6b6081cd292809f): spec ✅, quality Approved; 0 Critical, 0 Important, 5 Minor. Noted on hq-f5ccb6.
Ruling: re-grade Task 3 minor 1 (test_inflight_pi_capture_remains_safe_after_rollback leaves harnesses.toml in place on rollback, so moving load_specs() inside the lock would not be caught — test_live_picks.py:1610-1651) to Important — Why: spec §3 item 1 names that test as the guard of the load-before-lock contract, and without the unlink it pins nothing about it — Cost: one line plus a just test run if wrong.
Task 3: minor (deferred): CLI broken-manifest test does not prove the lock was never taken (test_live_picks.py:961-979)
Task 3: minor (deferred): missing() repeats unit filter per format (live-picks:449-456)
Task 3: minor (deferred): clean-only live_state test adds manifest entry without matching .gitattributes line (test_live_picks.py:1135-1140) — watch in Task 4/5
Task 3: minor (deferred): accessor named field(spec) vs spec's spec_field(spec) (live-picks:188)
Task 3: fix round 1 dispatched to implementer ae38192d932f3ca37 (FIX_BASE ee7ce1c9)
Task 3: fix round 1/5 (2 addressed, 0 open — rollback test unlinks harnesses.toml (RED/GREEN shown); clean-only .gitattributes line; commits ee7ce1c9..7bcba063); re-review haiku a28b00e89ea66dcb2 clean
Task 3: complete (commits 4a5f1fe8..7bcba063, review clean)
Task 4: started; child hq-1a6bba; BASE f1c29773; implementer sonnet agent a8df6d6524ce63493
Task 4: implementer DONE d725843f (focused 733 passed; just test 247+1321+391+1, rc=0); task review dispatched on review-f1c29773..d725843f.diff (sonnet agent a2ad62f948ab13efd)
Task 4: review round 1 (sonnet a2ad62f948ab13efd, claude-sonnet-5-5): spec ✅, quality Approved; 0 Critical, 0 Important, 3 Minor; risks checked: CLAUDE_JSON_KEYS tuple binding holds (relay_cutover inputs.py), no caller relies on clean_json's old exception types. Noted on hq-1a6bba.
Task 4: minor (deferred): clean-only refresh test asserts no live-picks file named "extra" rather than an unchanged local/live-picks* set (test_harness_state_refresh.py, end of clean-only test)
Task 4: minor (deferred): runpy test builds scratch manifest by splitting on a literal header string; brittle to manifest reordering (test_harness_state_clean.py diff lines 505-509)
Task 4: minor (deferred): codex-trust CODEX_SPEC = None module global would AttributeError if used before load_codex_spec() (codex-trust:56); all current paths load first
Task 4: minor (deferred): harness-state-clean still tracebacks on invalid JSON input (unchanged from before; report concern)
Task 4: complete (commits f1c29773..d725843f, review clean)
Task 5: started; child hq-d2b9cb (trial-arm flow off); BASE f88175db; implementer opus agent aebaa47fdf1722fec (multi-file hooks + docs + shared-config write); dispatch carries Ruling 1 and the just-setup note text
Task 5: implementer BLOCKED (no commits): filter.harness-state.required = true with no smudge command makes every checkout of a filtered file fail (git exits 128 "smudge filter harness-state failed"); WIP saved as task-5-wip.patch, worktree restored to HEAD; shared config untouched (required unset). Controller reproduced in an isolated scratch repo on git 2.56.0: no smudge -> checkout rc=128; smudge=cat -> rc=0.
Ruling 2: Task 5's `just setup` also writes `git config filter.harness-state.smudge cat` (identity smudge) right after `required true`; `check_filter_config()` (Task 1 code, amended within Task 5) also requires `filter.harness-state.smudge == "cat"` and names `just setup` when it is missing or different; every scratch fixture that sets `required = true` also sets `smudge cat`; `test_branch_switch_across_pre_manifest_and_post_manifest_commits_with_required_filter` makes the filtered settings blobs differ between the two branches so the switch actually runs the filter; the shared-config note names both keys and a rollback that unsets both; README/AGENTS/runbook name both keys — Why: git treats a required filter's missing smudge as fatal on checkout, so spec §5.3's required=true alone would break checkout/switch/merge/reset and pre-commit's checkout-index export on main and every worktree on this host; an identity smudge keeps the spec's fail-closed clean intent and changes no content; the spec text is amended to match in Task 6's status update — Cost: one config key, one check and its tests to remove if wrong; the approved shared-config write grows by one identity key, disclosed to the user.
Task 5: resumed under Ruling 2; implementer DONE_WITH_CONCERNS dd7fd099 (just test 1977 passed, rc=0; hygiene checks rc=0; smudge check RED 2 failed -> GREEN); just setup wrote required=true + smudge=cat to shared config, host-change note on hq-2eba07 (f9e5f315). Concerns: pre-commit checkout-index export forced -c filter.harness-state.smudge=cat (same root cause); facts fixture back-dates tracked configs to avoid racy-clean refilter (flaky ~1/3); pre-pi rollback test restores 6b434eb .gitattributes; fresh_clone copies working justfile; two older test helpers still inherit env (pre-existing, not touched); spec §5.3/§5.5 amendment owed in Task 6.
Observed (not ours): main's agy/settings.json modified at 12:32 by a live agy session (statusLine.enabled true -> false); left untouched. main's codex/config.toml untouched.
Task 5: task review dispatched opus agent ab39d14d296bcbd4f on review-f88175db..dd7fd099.diff (named risks: forced smudge in export vs manifest_check; fixture changes; inherited-env helpers; docs paths/recovery)
Task 5: review round 1 (opus ab39d14d296bcbd4f, claude-opus-5-5): spec ✅, quality Needs fixes; 0 Critical, 2 Important (new inherited-env subprocess at test_live_picks.py:1608-1610 reading 6b434eb:.gitattributes; README.md:26-27 claims git config is not shared between hosts), 9 Minor. Named risk (a) holds: forced smudge=cat reaches only checkout-index; harness_state.py check reads the real shared config.
Controller check of Important 2: main's .git carries user.com.dropbox.attrs (synced, not ignored); second host's hq checkout already shows filter.harness-state.required true and smudge cat (read-only ssh). The shared-config write therefore reached the second host via Dropbox; corrective note on hq-2eba07. Main's current filter works under required=true (git status/diff on main ran it without error).
Ruling: re-grade Task 5 minor 1 (spec §5.6's end-to-end fail-closed case names "corrupting or deleting harnesses.toml"; the test only corrupts) to Important — Why: a case the spec lists explicitly is untested, same standard as Task 2's re-grade — Cost: one assertion block if wrong.
Task 5: minor (deferred): pre-commit-level tests cover required unset, not required=false (covered by unit and CLI tests) — test_pre_commit.py:202, test_pre_commit_facts.py:256
Task 5: minor (deferred): test_refresh_refuses_when_filter_required_is_unset_or_false name now also covers smudge cases — test_harness_state_refresh.py:240
Task 5: minor (deferred): pre-pi rollback fixture's .gitattributes restore applies to all 4 params and models a rollback that keeps required=true while the documented rollback unsets both keys — test_live_picks.py diff 686-690
Task 5: minor (deferred): racy-clean quirk (unrelated git add within ~1s of an index write can fail while harnesses.toml is broken) undocumented — README.md:53-55
Task 5: minor (deferred): export-failure message embeds error.cmd incl. --prefix=<tmpdir>, leaking temp path on that path (pre-existing) — .githooks/pre-commit:103
Task 5: minor (deferred): pre-commit hardcodes filter.harness-state.smudge=cat duplicating EXPECTED_SMUDGE_FILTER; add cross-reference comment — .githooks/pre-commit:92, harness_state.py:31
Task 5: minor (deferred): "after pulling a change to it" ambiguous — AGENTS.md:11
Task 5: minor (deferred): flasgger-not-installed WARNING in agents/bin run of just test (pre-existing, unrelated) — task-5-just-test.log:3
Task 5: minor (deferred): pre-existing helpers test_live_picks.py:39 git() and tools/test_harness_links.py:44 run() inherit the process env; this diff extends their use (2 config calls, 2 config reads) — follow-up debt
Task 5: fix round 1 dispatched to implementer aebaa47fdf1722fec (FIX_BASE 8b8aeb2a; review saw dd7fd099)
Task 5: fix round 1/5 (3 addressed, 0 open — isolated pinned .gitattributes read via pinned_blob(); README/AGENTS/runbook say repo git config is shared through the synced checkout; deleted-manifest fail-closed case (characterisation, passed first run, no RED); commits dd7fd099..43dcb486; covering 230 passed; just test 247+1338+391+1, rc=0); re-review haiku a683c3302843d4692 (claude-haiku-5-5) clean
Task 5: minor (deferred): pre_pi_hooks module fixture runs `git -C ... show` with no env= (inherits process env) — .githooks/test_live_picks.py:1497-1501 (re-review out-of-scope observation; same pattern as fixed finding 1)
Task 5: complete (commits f88175db..43dcb486, review clean)
Task 6: started; child hq-746f05 (trial-arm flow off)
Ruling 3: merge main into feat/hq-2eba07-harness-manifest (88450204) before Task 6's verification and final review, rather than reviewing the pre-merge branch — Why: main gained the hq-57d68e session-store-adapters merge (186f8164), which touches three files this branch also changes (README.md, docs/runbooks/adding-a-harness.md, facts/capabilities.toml, the last validated by this branch's harness-facts against harnesses.toml) and adds tools/harness_stores (a per-harness registry), so the review and suite must see the integrated tree; merge-tree was clean and harness-facts/harness_state/ops-docs checks pass after merge — Cost: one merge commit on the branch; history not rewritten. The first Task 6 verification run (pre-merge) was stopped before completion and does not count.
Observed (not ours): another session is running just test in .worktrees/hq-8af61d concurrently; left alone.
Task 6: Step 1 verification running on merged HEAD 88450204 (task-6-verify.log); final whole-branch review dispatched opus agent a4aebe69b72aa971e on review-7f21b455..88450204.diff (named risks: main integration incl. tools/harness_stores, live hook surface failure modes, 6b434eb rollback compat, test env hygiene, host literals; deferred-minor triage and rulings assessment requested)
Final review round 1 (opus a4aebe69b72aa971e, claude-opus-5-5; saved final-review-report.md): Ready to merge: With fixes; 0 Critical, 2 Important (I1: wrong-typed manifest `format` raises TypeError past load_manifest_or_exit -> traceback, post-checkout exits 1 — harness_state.py:272-275; I2: harness-state-clean uncaught JSONDecodeError / unimportable harness_state.py become fatal tracebacks under required=true with no recovery route, and documented recovery fails mid-merge — harness-state-clean:25,47, README, runbook §3.3), 3 Minor. All rulings assessed sound. Noted on hq-2eba07.
Ruling: confirm final-review re-grade of Task 1 minor "test_manifest_validation parametrized cases assert only that ManifestError is raised" to Important — Why: the weak assertion is what let the `format` type hole (I1) pass; a person editing the manifest could break one invariant unnoticed while another still fires — Cost: tightening ~20 parametrized asserts if wrong.
Ruling: confirm final-review re-grade of Task 4 minor "harness-state-clean still tracebacks on invalid JSON input" to Important (merged into I2) — Why: under required=true a hand-edited live config makes git status/diff/add/stash/switch die with a traceback naming no file and no recovery route — Cost: a few lines and one CLI test if wrong.
Ruling: re-grade final-review Minor 1 (stale slug references left by the Ruling 3 merge: docs/runbooks/adding-a-harness.md:779-780 and tools/harness_stores/model.py:35 say slugs are keyed in facts/capabilities.toml) to Important — Why: the runbook would send a person adding a harness to the wrong file, the exact duplication this branch removes, and the stale text entered through my merge — Cost: two lines if wrong.
Final review: minor (deferred): pre-commit stops at the first failing staged check (`facts_check(tree) or manifest_check(...)`), hiding manifest problems when facts fail — .githooks/pre-commit:157
Final review: minor (deferred): check_filter_config normalizes clean with strip() but smudge with rstrip("\n") — harness_state.py:464 vs :474
Final review: minor (deferred): justfile:1 still says "after pulling a change to it" (AGENTS.md fixed)
Final review: follow-up (to file): test that every tools/harness_stores ADAPTERS slug is declared in harnesses.toml
Final review: follow-up (to file): replace inherited-env helpers test_live_picks.py git(), tools/test_harness_links.py run(), and pre_pi_hooks fixture's bare git show with key-by-key envs
Final review: spec amendments owed in Task 6 Status update: §5.5.1 "no smudge filter"; Ruling 2 smudge in §2, §3.1, §5.2, §5.3.1, §5.3.6, §6 call 2; §5.2 TREE_SKIP set; §5.3.4 field vs spec_field; §5.3.5 codex-trust config-path refusal
Final review: corrective round 1 dispatched to fresh sonnet fix agent a2f8795da327c0f96 (FIX_BASE 88450204 + record commits); findings I1, I1b, I2, I3 + spec amendments; reopens hq-e8f2db, hq-1a6bba, hq-d2b9cb
Task 6: Step 1 verification run on 88450204 exited 0 (agents/bin 268, .githooks+tools 1394, relay cutover 391, signal 1 passed; ops-check, ops-docs, harness-facts, harness_state, tasks check rc=0; ignored: __pycache__ dirs, .pytest_cache, .superpowers only). Limitation: the corrective-round fix agent began editing the same tree while this suite ran (its edits appear in the run's final porcelain), so this is not clean evidence for 88450204 alone; the fix agent's just test on the fixed HEAD is the authoritative branch-wide run.
Final review: corrective round 1 fix DONE (5e82bced fix(hooks), fa7fc63b docs(specs); just test 268+1412+391+1 rc=0; hygiene rc=0; children hq-e8f2db, hq-1a6bba, hq-d2b9cb reopened and re-closed); scoped re-review dispatched sonnet agent a3617281c2e25ec8a on review-88450204..6470e118.diff
Final review: corrective round 1/5 (4 addressed, 0 open — I1 format type guard; I1b per-case message assertions with EXPECTED/VIOLATIONS parity test; I2 named harness-state-clean errors on ValueError and unimportable harness_state.py, import guards in live-picks/codex-trust/harness-state-refresh keeping their exit contracts, mid-merge recovery docs; I3 slug references point at harnesses.toml; spec amendments marked; commits 88450204..6470e118); scoped re-review sonnet a3617281c2e25ec8a (claude-sonnet-5-5) clean. Noted on hq-2eba07 as impl round 2 accept.
Final review: minor (deferred): harness-state-clean main() reads sys.stdin outside the new try, so non-UTF-8 input still tracebacks (pre-existing path) — .githooks/harness-state-clean main
Final review: minor (deferred): AGENTS.md Rules and spec §5.5.1 recovery line still name only `git checkout -- harnesses.toml` without the mid-merge caveat (README and runbook have it)
Final review: minor (deferred): linked-worktree live-picks/codex-trust hook mode now prints the load message when harness_state.py is unimportable (was silent); judged acceptable by re-review
Task 6: Status lines updated (f9cde332); ops-check, ops-docs, harness-facts, harness_state check rc=0; just test not rerun for this Status-line-only docs commit — last full run final-fix1-just-test.log on the identical code tree (6470e118) rc=0
Final review: follow-ups filed — hq-5adbfd (harness_stores ADAPTERS slug parity test), hq-0e5941 (inherited-env git helpers in hook/links tests); both depend on hq-2eba07
Task 6: final review accepted (impl round 2 accept); hq-2eba07 to be parked for user merge approval
