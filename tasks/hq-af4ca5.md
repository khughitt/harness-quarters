---
id: hq-af4ca5
title: executing-plans task-done records runner configuration instead of the passing test summary when a composite check ends with Vitest finding no tests.
status: shelved
priority: "2"
created: 2026-10-02T12:37:32Z
updated: 2026-10-02T14:39:12Z
depends: []
tags: [feedback, friction, "from:beliefs"]
agent: codex
---

task-done fills the ledger's result field with the last non-blank line of the test log (`agents/vendor/superpowers/skills/executing-plans/scripts/task-done:48`). A composite check whose last step is a Vitest run that finds no tests ends with Vitest's runner-configuration output, so the ledger records that instead of the earlier passing summary. The exit-status gate is unaffected; only the evidence in the ledger line is wrong.

This is upstream code (obra/superpowers). Upstream issue #2342 reports the same class for `node --test` (the ledger records `# duration_ms`), and open PR #2348 fixes it by parsing TAP summary counts only, falling back to the last line otherwise. That does not cover Vitest or composite checks.

Local workaround until upstream changes: pass task-done the focused test command rather than a composite check, or end the command with an explicit summary line.

## Open questions

- Report the composite/Vitest case upstream as a comment on #2342 or PR #2348 (the last-line fallback is the general defect, not TAP specifically)? That posts publicly from your GitHub account. If not, shelve until #2348 lands and re-check.

## Notes

- 2026-10-02T14:30:57Z (main): scope: question; body rewritten with cause (task-done:48 last-line heuristic), upstream #2342/PR #2348 (TAP-only fix), workaround, and one open question: post the Vitest/composite case upstream
- 2026-10-02T14:39:11Z (main): Reported upstream as a comment on obra/superpowers#2342 (https://github.com/obra/superpowers/issues/2342#issuecomment-5954814790), reproduced on v6.4.1 with Vitest 5.0.3 --passWithNoTests
- 2026-10-02T14:39:11Z (main): shelved: upstream changes task-done's last-line fallback (PR #2348 or a follow-up to the #2342 comment) in a release — then bump agents/vendor/superpowers and re-check a composite check ending in Vitest
