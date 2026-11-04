# Turn-pause delivery and review handoff

Type: handoff. Owner: hq-2dd09b. Status: design review and separate live
activation approval remain with the user; no planned implementation has begun.

## Prepared and verified

hq-51209b and hq-5dc59c are implemented in hq at
f7259d9098f66ed2e60fa14f9aeb22824f2ba53d. Warnings explicitly permit authorized
continuation; human-facing counters name root calls, tree spawns and root
compactions; goal pauses require an explicit user request. Thresholds,
machine-readable units and cancellation permissions are preserved.

Focused baseline: 119 passed. Warning RED: 13 failed, 91 passed; GREEN: 121 passed.
Goal instruction RED: 2 failed, 1 passed; GREEN hook/allowlist/CLI: 374 passed.
Mandatory hygiene and whitespace checks passed. The independent whole-branch
review accepted with no findings and independently ran 31 focused cases (360
deselected). Full report: [warnings and goals review](2026-11-04-warnings-goals-r1-report.md).
Automatic broad tests were deliberately omitted under validated policy; no remote
evidence was obtained. Optional flasgger warnings did not affect results.

lore-296a0f prepares the matching global guidance in its own isolated worktree.
Its rule refresh and generated artifact/manifest preserve provenance without
claiming exact-current human adoption. Its task record owns final review,
validation and activation accounting. The direct fixes remain open across the
activation gate, retaining their owners and branches.

## Design awaiting the user

Frozen revision: repository hq, commit
95773e6eb742a3a4884126de9b93538be3676d84,
`docs/specs/2026-11-04-turn-pause-reliability-design.md`.
It is shared by hq-c58737, hq-704fe5 and hq-e10b76. The fresh builder check accepted
with no unanswered important questions; [full review](2026-11-04-reliability-design-r1-report.md).

The proposed choices are safe-reader exemptions using the existing shell grammar,
a default hard spawn cap of 60, and bounded co-located atomic state/history with
a read-only CLI handoff for obs. The cap recommendation is measured but remains
a policy judgment; larger healthy plans can still stop at61. History latency,+migration and activation remain future implementation obligations.

The declared replay used the six audited roots plus the known runaway control:
217 files, eight snapshots, 5.63 seconds, no converter problems. All candidates
retain the control's first refusal at root call501 and9.8567 active hours.
hq-704fe5 holds the committed script, pilot and full result. Mutable scratch was
removed only after each retained attachment was verified against committed bytes;
no off-tree scratch remains. This was a targeted pass, not a population study.

The next human action is review of the frozen design. On approval, the agent
uses writing-plans to prepare the implementation plan for its separate review.
Approval of the design alone does not activate the direct fixes or global
guidance. obs-1450e7 remains dependent on the future history producer; its report
and correlation scope is preserved. hq-b9d356 remains independently due November11.

## Controller scope rulings

There is no implementation plan or plan ledger yet. These rulings dispose of the
implementation review's four explicit scope exclusions at reviewed revision
f7259d9098f66ed2e60fa14f9aeb22824f2ba53d. No minor findings were deferred.

- Ruling: accept exclusion of spawn recalibration from the two direct fixes;
  hq-704fe5 owns it in the shared design. Why: choosing policy needs the separately
  requested measurement and review. Cost: live default30 remains until approved
  implementation and activation.
- Ruling: accept exclusion of history, self-stop reporting and broader alarms;
  hq-e10b76/obs-1450e7 own event history, while obs-59789b retains broader alarms.
  Why: neither direct fix claims these capabilities. Cost: reliable historical
  reporting remains unavailable until those tasks land.
- Ruling: accept exclusion of protected-path diagnostics from the direct fixes;
  hq-c58737 owns it. Why: the read/mutation boundary has a separate security
  design and approval gate. Cost: current safe diagnostic refusals persist until
  that work is activated.
- Ruling: accept exclusion of live hook/global activation from the code review.
  Why: the goal expressly requires separate user approval. Cost: reviewed wording
  does not affect live sessions while approval is pending.

## Integration and resources

No pushes, PRs, services or host-pointer changes were made. No task is being
declared done by this handoff. Both worktrees remain locked and both branches
remain unmerged. The hq tree is `.worktrees/hq-2dd09b`, branch `fix/hq-2dd09b`;
hq-c58737 owns its retention across review. Lore's tree is
`lore:.worktrees/lore-296a0f`, branch `fix/lore-296a0f`, owned by lore-296a0f.
The agent integrates each only after the user's separate live activation
approval, using `git merge fix/hq-2dd09b` in hq main and
`git merge fix/lore-296a0f` in lore main after refreshing base/checks.

The hq ignored entries are regenerable pytest/Python caches. Lore's ignored
environment is setup-generated and regenerable; its initialized submodule remains
part of that worktree. Neither worktree has a `.superpowers/sdd` workspace or an
external plan-execution mapping from this work. Other pre-existing worktrees and
record configuration drafts were inspected only and left to their existing
owners. Final host/process observations and exact retained-item checkpoints are
recorded on the tasks immediately before park.
