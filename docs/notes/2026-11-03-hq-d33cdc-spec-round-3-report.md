# hq test policy design: spec round 3

Verdict: accept — nothing important left.

Reviewed repository: hq. Frozen commit:
`da5e8ace1327c4eea5ce77c8e1a6355eb65d31af`, path
`docs/specs/2026-11-03-test-execution-policy-design.md`.

Reviewer identity: `codex/gpt-6.1-sol`, verified by the reviewer with a fresh
`timeout 2 relay model --harness codex --pretty` invocation in this review turn.

Actionable findings: none. All four prior findings are addressed:

- Hosted hygiene now uses existing local_layer, docs_check and staged_checks
  validations without registry-dependent ops-check. Full local hygiene remains
  mandatory, and the hosted coverage limitation is explicit.
- test and ci-test are both broad targets. Only the workflow supplies force,
  preserving local policy-off skips and hosted missing-force refusal.
- The static module count is correctly 57.
- Caller-owned evidence must survive tt cleanup, preserve distinct partition
  reports and support failure-path reconciliation.

These boundaries match the existing hook functions and tt decision/cleanup
implementation. Remaining factoring, tool pins and report transport choices are
sufficiently bounded for planning.

No report file was written by the reviewer because no plan workspace exists;
this full review was returned for controller persistence. No files or task records
were changed by the reviewer. The controller saved the report in the authorized
in-tree document destination; no file-handoff savings are claimed.

Skipped suites, baseline tests and hosted execution as instructed; actual hosted
feasibility and coverage remain unverified.
