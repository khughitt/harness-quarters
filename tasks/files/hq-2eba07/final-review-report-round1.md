# Final whole-branch review (round 1)

Reviewer: claude-code/claude-opus-5-5 (agent a4aebe69b72aa971e), dispatched by the controller; range 7f21b455..88450204; saved verbatim from its final message.

Reviewer: claude-code/claude-opus-5-5

Review passes, in order:
1. Read the frozen constraints, the five Review Focus items, the ledger and the spec.
2. Read `harness_state.py`, `harnesses.toml`, `.gitattributes`, `live-picks`, `harness-state-clean`, `harness-state-refresh`, `pre-commit`, and the diffs of `codex-trust`, `justfile`, `tools/harness-facts` and `facts/capabilities.toml`.
3. Test hygiene: went through every added subprocess or env line in the changed tests.
4. Docs and integration: read the README, AGENTS, runbook §3, §4, §7 and the checklist, `tools/harness_stores`, and the ops `claim-guard` consumers of `harness-facts`.
5. Ran three isolated probes in my scratchpad (env built key by key, `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1`, inherited `GIT_*` unset, toplevel asserted): a required filter failing mid-merge, `load_manifest` given a list-valued `format`, and `live-picks`/`codex-trust`/`harness-state-clean` run against that manifest.

I did not run the full suite. `task-6-verify.log` shows agents/bin at 268 passed; the `.githooks tools` run was still in progress at about 20%.

### Strengths
- The design follows the spec closely. One loader and validator owns every invariant: segment-bounded single-`*` globs, a pairwise overlap check that implements the spec's prefix/suffix rule exactly, the partition invariant, and clean-only defaults. Every consumer imports it, and no `runpy` imports remain between hooks.
- The load ordering is right. `live-picks` and `codex-trust` check argument shape, then linked worktree, then rebase, then load the manifest, then take the lock. The hook path's `except SystemExit` covers manifest failures. `harness-state-refresh` drains stdin before anything else.
- Rollback compatibility (risk c) holds. `write_record` serializes the same way as before (`indent=2, ensure_ascii=False`). Unit iteration order matches the old `JSON_GROUPS`. The shared `local/live-picks.json` keeps claude before codex, because `claude-code` comes before `codex` in the manifest, as it did in the old `OWNED`. A single-unit codex `merged_lines` returns `held` unchanged.
- `pre-commit` exports the staged tree once and runs the staged checker. It reads filter config through `--git-dir`, so a linked worktree reads the shared `commondir` config (Review Focus 3). `check_clean_tree` covers the already-leaked blob (Review Focus 1).
- Multi-unit TOML (Review Focus 2) is handled with care. `lines_parse` refuses duplicate keys, quoted keys and lines that don't round-trip. `merged_lines` and `missing` iterate units in declaration order. `without_pick` removes only `pick_keys`, so `unrestored_keys` survive `forget`.
- `tools/harness-facts` keeps its positional API and its `"schema": 1` view, and stays standalone with only the standard library. The ops `claim-guard` real-reader tests copy the registered checkout's own `facts/capabilities.toml`, so removing the `harnesses` line does not break them.
- Test hygiene (risk d) is good in the new code. New helpers (`isolated_env`, `child_env`, `tool_env`, `pinned_blob`, and the `repo`/`world` fixtures) build env key by key and assert toplevel and absolute git-dir before writing. Where a fixture calls `monkeypatch.delenv` on every key and then sets a key-by-key dict, the resulting env is fully rebuilt, not inherited.
- No host paths or host names appear in changed tracked files (risk e). The one "Dropbox" hit is a word in a docstring that already existed.

### Issues

#### Critical (Must Fix)
None.

#### Important (Should Fix)

1. **A wrong-typed `format` crashes every manifest reader with a traceback, and `post-checkout` then exits 1.**
   - Where: `.githooks/harness_state.py:272-275`. `fmt not in ALLOWED_KEYS` raises `TypeError` when `format` is a list or table (for example `format = ["json"]`).
   - Reproduced: with the shipped manifest and only that change, `live-picks hook post-checkout` and `codex-trust hook post-checkout` both exit 1 with a Python traceback, and `harness-state-clean` does the same.
   - Why it matters: `load_manifest_or_exit` catches only `ManifestError`, so the hook's `except SystemExit` never runs. A `post-checkout` exit status becomes `git switch`/`git checkout`'s exit status, so a completed checkout reports failure. This breaks Review Focus 4 and the spec's failure-handling table (§5.3) on the live hook surface (risk b).
   - Fix:
     - Use `if not isinstance(fmt, str) or fmt not in ALLOWED_KEYS:`.
     - Add a `format = ["json"]` case to `VIOLATIONS`.
     - Make the parametrized validation test assert the expected message, which is deferred minor T1-1. That weakness is why a type hole like this can pass unnoticed.
   - I checked the rest of the validator for other unhashable or wrong-type escapes and found none.

2. **`required = true` makes `harness-state-clean`'s uncaught exceptions fatal to git, with a traceback instead of `harness-state-clean: <path>: <problem>`.**
   - Where: `.githooks/harness-state-clean:25` and `:47`.
   - Two triggers:
     - A live JSON config that fails to parse, such as a hand edit with a trailing comma, or JSONC. `clean_json` raises `JSONDecodeError`, which `main` does not catch. This is deferred minor T4-4, which I am re-grading.
     - A `.githooks/harness_state.py` that will not import, such as conflict markers left by a merge. The clean filter used to be self-contained; it now imports this module.
   - Probe result (isolated repo, failing required clean, during a merge conflict): `git status` dies (exit 128) once a filtered file is stat-dirty at the same size, and so do `git diff` and `git stash`. `git merge --abort` still works. In main, the live configs change at every pick, so this state is likely there.
   - Before this branch, git warned and staged raw content. Now it fails closed, which is the intent, but the person sees a Python traceback. The traceback's last line does not name the file, and nothing gives a recovery route.
   - The documented recovery also fails mid-merge: `git checkout -- harnesses.toml` gives "error: path 'harnesses.toml' is unmerged".
   - Fix:
     - In `main`, catch `ValueError` around `clean_for_spec` and exit with `harness-state-clean: {path}: {error}; fix the file, then retry`.
     - Wrap `import harness_state` in `except (ImportError, SyntaxError)` and exit with `harness-state-clean: cannot load .githooks/harness_state.py: …; resolve or restore it`.
     - In README.md (broken-manifest paragraph) and runbook §3.3 "Failure and recovery", add that during a merge you resolve the conflict or run `git merge --abort`.

#### Minor (Nice to Have)
1. **Stale slug references left by the merge.**
   - Where: `docs/runbooks/adding-a-harness.md:779-780` (`slug` "(the key in `facts/capabilities.toml`)") and `tools/harness_stores/model.py:35` (comment `(facts/capabilities.toml)`).
   - Since this branch, slugs are declared in `harnesses.toml`. Update both lines here.
   - A test that every `ADAPTERS` slug is declared in `harnesses.toml` belongs in a follow-up.
2. **`pre-commit` stops at the first failing staged check.** `.githooks/pre-commit:157` `facts_check(tree) or manifest_check(...)` hides the manifest checker's problems whenever facts fail. Running both and OR-ing the results would report everything in one pass. This is related to deferred T2-8.
3. **Inconsistent output normalization.** `check_filter_config` (`harness_state.py:464` vs `:474`) uses `strip()` for clean and `rstrip("\n")` for smudge. It is harmless; pick one for consistency.

### Deferred-minor triage
- T1: parametrized validation cases assert only that `ManifestError` is raised (`test_harness_manifest.py`). **Fix before merge**, together with Important 1: the weak assertion is what let the `format` type hole through. Effect if left: an invariant can break unnoticed while another one still fires.
- T1: unused imports. **Already resolved.** `Iterable`/`Sequence` are gone from `harness_state.py`, and `json` is used in the test file.
- T1: `TREE_SKIP` applies at any depth. **Can stay deferred.** It matters only for a future `filter_glob` that contains a `local`, `.venv` or `node_modules` segment. Amend spec §5.2, which names only `.git`.
- T1: `check_gitattributes` does not flag a bare `filter` or `filter=`. **Can stay deferred.** It is not a leak path, since such a line routes nothing to this filter.
- T1: `clean_json` now raises `ValueError`. **Can stay deferred.** The Task 4 review confirmed no caller depends on the old exception types. Important 2 uses `ValueError` as the catch point.
- T2: `_load` errors don't name the failing file. **Already resolved.** The message is now `not valid TOML: <name>: …`, and the `OSError` message carries the path.
- T2: test `run()` silently appends `--manifest`. **Can stay deferred.** Test-only.
- T2: a manifest failure returns before `capabilities.toml` is read. **Can stay deferred.** The person fixes and reruns.
- T3: the CLI broken-manifest test doesn't prove the lock was never taken. **Can stay deferred.** The rollback test (fixed by its re-grade) guards ordering.
- T3: `missing()` repeats the unit filter per format. **Can stay deferred.** Style only.
- T3: the clean-only test lacked a `.gitattributes` line. **Already resolved** in fix round 1.
- T3: `field(spec)` vs the spec's `spec_field(spec)`. **Can stay deferred.** Naming is left to the builder. Amend the spec, or leave it.
- T4: the clean-only refresh test asserts that no file named "extra" exists. **Can stay deferred.**
- T4: the runpy test splits the manifest on a literal header string. **Can stay deferred.** Brittle only to reordering, and it fails loudly.
- T4: `CODEX_SPEC = None` global. **Can stay deferred.** Every path loads first.
- T4: `harness-state-clean` tracebacks on invalid JSON. **Fix before merge**, as Important 2: with `required = true`, git status, diff, add, stash and switch die with a traceback on a hand-edited config.
- T5: pre-commit-level tests cover `required` unset but not `false`. **Can stay deferred.** Unit and CLI tests cover `false`.
- T5: the refresh test name now also covers smudge cases. **Can stay deferred.**
- T5: the pre-pi rollback fixture keeps `required = true` while the documented rollback unsets both keys. **Can stay deferred.** It models the stricter case that other worktrees actually see.
- T5: the racy-clean quirk is undocumented. **Can stay deferred.** It could go in the same doc fix as Important 2.
- T5: the export-failure message embeds the temporary directory path. **Can stay deferred.** It existed before this branch and appears only on stderr.
- T5: `pre-commit` hardcodes `smudge=cat`. **Can stay deferred.** A cross-reference comment would do.
- T5: "after pulling a change to it" is ambiguous. **Can stay deferred.** AGENTS.md now says "to the recipe"; `justfile:1` still says "to it".
- T5: flasgger warning. **Can stay deferred.** Unrelated.
- T5: the old helpers `test_live_picks.py:39` `git()` and `tools/test_harness_links.py:44` `run()` inherit env. **Can stay deferred, with a follow-up task filed.** This branch adds `git config` writes through `git()` (`required`, `smudge`) in a fixture that asserts no toplevel. If an inherited `GIT_DIR` were present, they would write to the real repository, though only the values `just setup` writes. No new helper of this kind was added.
- T5: the `pre_pi_hooks` fixture runs `git show` with no `env=`. **Can stay deferred.** Read-only; same follow-up.

### Rulings assessment
- **Ruling 1** (assert that an unconfigured `.toml` routed through the filter fails `git add`): **sound.** The spec's §5.6 test list binds.
- **Ruling 2** (identity `smudge = cat`, checked by `check_filter_config`, forced in the `pre-commit` export): **sound.** A required filter with no smudge fails every checkout. `cat` changes no content. Forcing it only in `checkout-index` lets `manifest_check` still report the real config.
- **Ruling 3** (merge main before the final review): **sound.** The merge reads coherently. It left the two stale slug references in Minor 1.
- **Re-grade, T1 minor 6** (env inherited via `monkeypatch.setenv`): **sound.** The user's binding test rule.
- **Re-grade, T1 minor 1** (`AttributeError` on a non-object JSON blob): **sound.** The same class of hole remains in `harness-state-clean`'s own path (Important 2).
- **Re-grade, T2** (the vacuous non-table test): **sound.**
- **Re-grade, T3** (the rollback test must unlink `harnesses.toml`): **sound.** That test is what pins the load-before-lock contract.
- **Re-grade, T5** (deleted-manifest fail-closed case): **sound.**

### Named risks
- **(a) Integration with main.** README and runbook read coherently after the merge. §3.2–3.6 and §4.1 fit main's new §7, apart from Minor 1. `tools/harness_stores` is the kind of separate surface the spec keeps apart. Its non-goals exclude session-discovery adapters and transcript archiving, and its anti-goal rules out a generic DSL. Each adapter is behaviour code keyed by slug, not a second copy of `live_state` data. The only overlap is the slug strings. On this branch, fix the stale comments; the slug parity test is a follow-up.
- **(b) Live hook surface.** Important 1 and Important 2. Otherwise the fail-closed paths print `<tool>: <problem>`, and `git merge --abort` stays usable.
- **(c) Rollback.** Holds; see Strengths.
- **(d) Test hygiene.** New helpers comply. The old inheriting helpers have extended use; see triage.
- **(e) Host paths.** Clean.

### Spec text the code contradicts (for the Task 6 amendment)
- **§5.5.1:** "`harness-state` defines a `clean` filter (no `smudge` filter)". It now has smudge `cat` (Ruling 2).
- **Ruling 2 not reflected:** §2 Goals, §3.1, §5.2 (`check_filter_config`), §5.3.1 (`just setup`), §5.3.6 and §6 call 2 name only `clean` and `required`. They lack `EXPECTED_SMUDGE_FILTER`, the smudge check, and the forced `-c filter.harness-state.smudge=cat` in the export.
- **§5.2:** `check_clean_tree` "excluding `.git`". The code also skips `.worktrees`, `.venv`, `node_modules` and `local` at any depth.
- **§5.3.4:** names `spec_field(spec)`; the code has `field(spec)`.
- **§5.3.5:** `codex-trust` also refuses when the codex entry's `config` is not `codex/config.toml`. This is a sensible addition the spec doesn't list.
- **§5.6:** `test_pre_commit.py` uses the real `harness_state.py` rather than a stub. That is better than the spec; no conflict.

### Declined to judge
- Quoted TOML keys such as `"model" = …` are not stripped by `clean_toml`. The `TOML_KEY` group includes the quotes. This behaviour predates the branch; `live-picks` refuses such keys as Review Focus 2 requires.
- `check_gitattributes` reads only the root `.gitattributes`. Nested `.gitattributes` and `.git/info/attributes` are outside what the spec defines.
- `picks_record` may name `local/harness-state.lock`. The spec's `local/<filename>` rule allows it, and nobody would write that.
- Checking out very old commits whose filter config never had a working clean script, now under `required = true`. That history is outside the plan's rollback target (`6b434eb`).
- Exceptions from `re.compile` other than `re.error` on pathological manifest regexes, such as recursion limits. Not a plausible input.
- Other repositories that load `harness-facts` with fixtures carrying `harnesses = [...]`. I searched only hq's `agy/hook` and ops' `claim-guard` and its tests.
- How long `check_clean_tree` takes to walk the staged export. Small tree; no requirement in the spec.

### Recommendations
- Fix Important 1 and 2 and the T1-1 assertion tightening in one corrective round. Each is a few lines plus focused tests: a manifest-violation case, a `harness-state-clean` invalid-JSON CLI case asserting a `harness-state-clean:` prefix and no `Traceback`, and an unimportable-`harness_state.py` case.
- Fix Minor 1 on this branch, and file the `ADAPTERS`-slug parity test and the inherited-env helper cleanup as follow-ups.
- Fold the spec amendments above into Task 6's Status update.

### Assessment
**Ready to merge?** With fixes

**Reasoning:** The implementation meets the spec and all five Review Focus items on the inputs they name, and rollback, linked-worktree and leaked-blob behaviour are sound. Two narrow but real paths on the live hook surface still end in a traceback instead of `<tool>: <problem>`; one of them makes `git checkout` report failure. Both are small fixes.
