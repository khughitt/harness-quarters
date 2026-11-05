---
id: hq-53e9ea
title: Detect drift between the records-hook test fixture and the records repository's pre-commit hook
status: shelved
priority: 4
defer: 2026-12-05
created: 2026-11-02T20:00:59Z
updated: 2026-11-05T14:23:33Z
depends: []
tags: [rename-cutover]
source: hq-5300fd
agent: claude-code
origin: agent
---

tools/fixtures/records-hook/pre-commit is a byte copy of the records repository's .githooks/pre-commit, so the rename-cutover tests meet the live refusal. Tests cannot read the live file, and its README asks whoever changes the hook to re-copy it, which nothing enforces. Possible routes: a records-repository hook or check that compares the two when both checkouts are present, or an hq check run on a host with the records repository. Source: hq-5300fd Task 1.

## Notes

- 2026-11-02T20:00:59Z (add): created
  provenance: {"harness_session":"claude-code:7104a322-b727-4975-8f34-3d210db837b3","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
- 2026-11-05T14:23:31Z (main): shelved: Revisit when the records repository's pre-commit hook or hq's copied records-hook fixture changes, when an actual mismatch is reported, or at the 2026-12-05 checkpoint. As of this review the hooks match byte-for-byte with mode 0755; the fixture README's manual recopy contract remains in force. Choose an automation owner and invocation route only if new evidence warrants it. The user's 2026-11-02 keep-rename-cutover-for-now decision remains intact.
- 2026-11-05T14:23:33Z (main): scope: shelved; no current drift: tools/fixtures/records-hook/pre-commit equals the records repository .githooks/pre-commit byte-for-byte, both mode 0755; fixture landed d0c200ef and live hook last changed c52f497803; tools/test_rename_cutover.py copies the fixture into isolated sandbox hooks, never reads the live hook; retain the documented recopy contract and revisit hook/fixture changes or checkpoint 2026-12-05 instead of adding a new cross-checkout check without an observed mismatch; hq-ca01cf excludes rename-cutover after the user said keep for now; origin: stage 1 matched — claude-code:7104a322-b727-4975-8f34-3d210db837b3 L563 filing call, full created results L564/L566 at 2026-11-02T20:00:59Z are two captures of the same call, not two filing candidates; human L541 asked for follow-ups, agent proposed this specific automation, origin agent retained; later human L582 retains rename-cutover; stage 2 not applicable (no origin_session). Scope pass only: just check-hygiene passed; no behavior tests, code worktree, scratch, host pointer or background process created; no branch left unmerged by this pass, nothing pushed, existing agy/settings.json edit untouched.
  provenance: {"harness_session":"codex:01a1ac0c-d4f7-7752-a39c-f5c101746768","harness_session_source":"CODEX_THREAD_ID"}
