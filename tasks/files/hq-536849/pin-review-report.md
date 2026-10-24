Reviewer: codex/gpt-6.1-sol
Candidate: base 22dcefa, working tree 7c3ce3dc64c570fe3da67b6b33eca7150a8288eb

What this change does: Updates the standalone relay pin to v0.2.0 at commit `067c63921602e694682d47bdb2412862359c75ff`, using the existing installer and launcher. It documents the approval-gated deployment and durable inbox recovery limits. This is preparation for hq-536849; live deployment remains unapproved.

**Important — fix before approval**

1. **The standalone pin change breaks the hook-image checks**
   Location: `.worktrees/hq-536849/relay/package.json:5`; affected assertion: `.worktrees/hq-536849/tools/test_relay_wiring.py:20`.

   **What this is:** The wiring tests derive `VERSION` from the standalone package pin at line 9. The three committed hook files intentionally retain absolute v0.1.1 runtime paths.

   **Problem:** Changing the standalone pin makes the assertion demand v0.2.0 hook paths. Six test cases consequently fail: `test_claude_relay_events`, both `test_codex_relay_events` cases, and all three `test_native_entries_kept_in_order` cases. The first two functions reach the assertion through `relay_entries`; the third calls `parse_relay_command` directly. These are all callers relying on `VERSION`.

   **Fix:** Give this test an explicit historical hook version, such as `HOOK_VERSION = "v0.1.1"`, and update its introductory description to explain the separation. Preserve its exact path validation. Keep the standalone v0.2.0 checks in `test_relay_pin.py`; do not rewrite installed hook images to satisfy this task.

   **If skipped:** The required suite fails despite correct standalone installation behavior. Updating hook files instead would cross the separately approved hook-cutover boundary.

No Critical or Minor findings.

The remaining change is suitably small. The package specification and lockfile agree; the lock fixes the published release commit. The unchanged launcher selects the versioned installation and explicitly exits 127 when it is missing. The installer retains frozen `npm ci`, disabled lifecycle scripts, and its system npm selection.

I inspected the four-test GREEN log, isolated installation log, public Node 22/26 installation evidence, rehearsal script and output, and packaged CLI, inbox lifecycle and persistence code. They support saved native-answer and presence preservation across the upgrade, detached ask-file and terminal answer, restart persistence, and unchanged repeated take. The disposable-copy downgrade check confirms v0.1.1 quarantines a taken entry while leaving the canonical v0.2.0 entry unchanged. The runbook’s downgrade warning is justified.

Assumed load: one operator using a private local inbox service. No added concurrency or performance concern appeared in this pin-only change.

**Declined to judge**

- Actual PATH launcher behavior after live installation and merge: approval has not occurred.
- Production service deployment: Titan has no configured inbox service; none should be created for this upgrade.
- Hook cutover, home-link changes and real phone acceptance: separately gated work.
- Final full-suite result: the controller owns the running check. I did not start another suite.

Reviewer identity: `codex/gpt-6.1-sol`, verified with a fresh identity command. Review remained read-only.

Verdict: fix 1 and obtain a green full suite before presenting the change for live approval.

Not checked: live installation, merge or service changes. Downgrading an older service against new take/refusal histories remains unsafe.
