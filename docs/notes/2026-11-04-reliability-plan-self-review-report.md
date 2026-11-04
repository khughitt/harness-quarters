# Reliability plan self-review and handoff

Type: review. Owner: hq-c58737 under hq-2dd09b.
Reviewer: codex/gpt-6.1-sol, verified in this turn by a fresh successful
`timeout 2 relay model --harness codex --pretty`.

Reviewed repository hq, frozen commit
`3c29183b042929a43619ab2b780527fad82dd307`,
`docs/plans/2026-11-04-turn-pause-reliability.md`, SHA256
`1c42c62673e79518887bc5a9608a4d8a52bf98456082734c5b753a4bc2fd48e2`.
Verdict: accept for human plan review; no remaining blocking findings.
This is the writing-plans self-review, not an independent review or human
approval. No implementation is authorized before the next human gate.

## Coverage and consistency

- Task 1 owns safe read identities, Bash metadata, literal paths/readlink,
  protected mutations/composition, grace and recovery text. It preserves the
  cheap pre-check and import boundary.
- Task 2 owns default60/warning45, exact60/crossed61 for both harnesses,
  proportional/named budgets, current expectations/docs and frozen replay use.
- Task 3 owns the atomic bounded record, strict parsing, shared interfaces,
  explicit reversible offline migration and activation/rollback runbook.
- Task 4 owns genuine/implicit starts, reset/resume, pause reasons including
  limits-changed, warning/pause deduplication, original-turn notification
  outcomes, retained end/idle history, locks, bounded cleanup and latency proof.
- Task 5 owns read-only CLI/schema/coverage, status compatibility and portable
  hook/task/session evidence fixtures for the separately owned obs consumer.

All five Review Focus items have owning test steps. Neighboring tasks use the
same RootRecord, Store, history and snapshot signatures. State migration and
event generation are staged separately; no partially implemented storage is
activated. Tests exercise observable allowed/refused behavior, atomicity,
coverage and identities rather than asserting only constants or source text.
Commands use the protected focused route, with baseline and mandatory hygiene;
no broad skip is described as green evidence.

Self-review resolved late-outcome resurrection, duplicate initial user turns,
receipts accidentally placed among state files, and post-replace durability
uncertainty before freezing this revision. The existing reader grammar and
counter engine are reused; no dependency, daemon or host-pointer change is added.
Plan length is about2.3 times the design; it records interfaces, tests and
cutover decisions rather than supplying implementation function bodies.

## Decisions to carry into the execution ledger

- Ruling: keep one coordinated plan with five reviewable deliverables. Why:
  hook/allowlist/state interfaces and their tests overlap; splitting documents
  would duplicate those contracts. Cost: a longer combined review, with serial
  execution instead of independently scheduled branches. Revision: the frozen
  plan above, Setup and Task1–5 boundaries.
- Ruling: recommend native inline execution, retaining a fresh whole-branch
  reviewer and corrective re-reviews. Why: the five steps share interfaces and
  one worktree; this limits dispatch/context overhead. Cost: no independent
  per-task code review before the final review; the user can choose delegated
  execution at the plan gate. Revision: plan Execution Setup and Review.
- Ruling: put migration receipts outside source and destination and keep runtime
  parsing single-format. Why: receipt.json would otherwise appear to be a state
  record, and runtime fallback would hide an incomplete cutover. Cost: activation
  needs a separately approved, quiesced operator window. Revision: Task3 Step4–5.

No minor findings were deferred. On execution, copy these decisions into the
external plan ledger and name that ledger from the owner task; none exists yet.

## Verification and current gates

Verified the frozen spec hash and plan bytes, task-heading correspondence,
existing input fixtures, Store/counter/notifier callers and the host-budget
OPS_WORKERS contract. `just check-hygiene` and `git diff --check` passed during
document preparation; runtime tests and latency measurements were not run or
claimed. The execution plan schedules them after human plan approval.

Execution tasks, each parked waiting on plan review: hq-9fc447, hq-5a461d,
hq-cc91d4, hq-e60ecb, hq-f50d9f. The three owning goals remain open, and activation
approval is separate from this plan review. hq-c58737 continues to own the locked
shared worktree and future execution workspace. No new scratch or execution
workspace exists yet; canonical replay evidence remains committed attachments.

Unmerged branch `fix/hq-2dd09b` remains in `.worktrees/hq-2dd09b`; the separately
reviewed `fix/lore-296a0f` remains in lore's `.worktrees/lore-296a0f`. The agent
integrates either only after separate live activation approval. No pushes,
services or host-pointer changes occurred; other task-record changes from main
were merged without changing their content. The task notes hold the final
process observation and exact retained-item checkpoint.
