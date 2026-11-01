---
id: hq-4c1dfb
title: Close remaining traceback and reporting gaps in harness-state hooks
status: todo
priority: 2
size: s
complexity: low
process: direct
created: 2026-11-01T19:26:16Z
updated: 2026-11-01T19:26:16Z
depends: []
tags: [hooks]
origin: agent
---

Deferred from hq-2eba07's reviews (ledger attached there). On the live hook surface, under filter.harness-state.required = true: (1) .githooks/harness-state-clean main() reads stdin outside its error handling, so a non-UTF-8 config still ends in a traceback instead of 'harness-state-clean: <path>: <problem>'. (2) .githooks/pre-commit staged_checks() runs facts_check(tree) or manifest_check(...), so a facts failure hides every manifest/filter problem until the next commit attempt; run both and combine. (3) pre-commit's export-failure message embeds the checkout-index command, including the temporary --prefix path, on stderr. Each needs a focused test asserting the named message and no Traceback.

## Notes

- 2026-11-01T19:26:16Z (add): created
  provenance: {"harness_session":"claude-code:fdf3b32f-5e63-4593-bba2-4e994bcdf1eb","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
