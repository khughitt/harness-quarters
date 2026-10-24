Reviewer: codex/gpt-6.1-sol, verified by a fresh identity command.

What this change does: Separates the approved v0.1.1 hook expectation from the standalone v0.2.0 CLI pin. The correction resolves the previous Important finding without changing production hooks.

Candidate fingerprint verified: `9fed2f5945a5088ce340ded5851b43de09a9c071`, base `22dcefa`.

**Scoped verdict: accept. Critical: 0. Important: 0. Minor: 0.**

Checked:

- `.worktrees/hq-536849/tools/test_relay_wiring.py` changes only its description, version constant and constant reference. Absolute runtime path validation, argument count, executable, subscriber path, harness, event and timeout expectations retain their existing checks.
- `.worktrees/hq-536849/tools/test_claim_guard_wiring.py` and `.worktrees/hq-536849/tools/test_capture_notice_wiring.py` remain compatible. Native guard counts and hook ordering checks are unchanged.
- Production hook files are unchanged. Standalone pin tests still require v0.2.0 at commit `067c63921602e694682d47bdb2412862359c75ff`.
- RED evidence records 9 failures and 6 passes from the original coupling. GREEN evidence records 19 passes, including pin tests.
- `git diff --check` passed. The latest full-suite log showed 231 agent tests and 1042 hook/tool tests passing; its cutover phase had not finished when inspected.

Review stayed read-only. No files, index, HEAD, task records or host configuration were changed; no background process was launched.

Not checked: final full-suite completion, live installation, merge, service deployment, hook cutover or phone acceptance. The controller owns suite completion and the live approval gate; this scoped acceptance does not authorize rollout.
