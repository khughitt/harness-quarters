# Strict consumer plan self-check

Reviewer: codex/gpt-6.1-sol (self-review), verified in the review turn by
`timeout 2 relay model --harness codex --pretty`.

Frozen plan: hq 50282b9, docs/plans/2026-09-30-session-archive.md, revision 2.
Approved design: hq cfaed41, docs/specs/2026-09-30-session-archive-design.md,
revision 3. Verdict: accept; findings: none. This is the writing-plans self-check,
not an independent review or human plan approval.

- Spec coverage: Task 18 owns the versioned boundary, exact path keys, duplicates,
  all field shapes and contradictory-ready rejection, unknown harness/reason
  handling, fresh device/inode and full-span digest checks, Codex identity and
  ancestry, partial-tail removal, all affected constructors/helpers and README.
  Its tests cover the real loader-to-facts path, replaced inodes with preserved
  bytes/stat, same-stat rewritten bytes with a current mirror, whole-unit retention
  and malformed-later-row preflight. Task 19 owns actual producer output against a
  committed strict reader, its necessary obs probe adapter and retained evidence.
  Task 17 remains rollout-owned; no live action is authorized.
- Step scan: baseline/caller inventory, RED cases, production changes, focused
  GREEN, full gate and commits are ordered explicitly. New subprocess RED cases
  have safe temporary environments first. Expected-failure environment inspection
  uses a synthetic parent mapping so assertion output cannot expose real secrets.
- Type consistency: ObsFile and FileFacts additions/removal are specified once;
  _read_file returns two values and every unpacking caller is included. Capture's
  Stat and the production _facts/Context signatures remain stable. The external
  probe calls that shared existing interface in both pinned reader revisions;
  there is no runtime compatibility shim or producer policy change.
- Review focus: all five strict-revision risks point to named tests or the paired
  probe. The old inline build snippets are marked historical; current constraints
  and Tasks 18–19 supersede their unversioned reader and partial-tail behavior.
- Proportion: two execution tasks; no generic schema framework, new dependencies,
  extra source, or second consumer. Shared interfaces change atomically in hq.
  Coordinated obs code is reviewed alongside the hq branch before integration.

Verification observed: hq just test passed 231 + 1051 + 391 + 1 = 1674 tests;
tasks check and git diff --check passed. These checks cover unchanged runtime and
document/task consistency. No strict-consumer implementation or paired acceptance
run exists yet. No independent plan review was dispatched.
