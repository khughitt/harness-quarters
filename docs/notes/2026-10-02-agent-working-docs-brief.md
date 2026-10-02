# Brief: where agent working docs live

Goal: tack-d7b5b2. Idea: tack-fed9db (source: mindful thought af11b654, "tack / move scoping docs into
mindful?", 2026-09-29).

## 1. Problem

Project repositories carry a growing layer of agent working material: task records,
scoping briefs, handoffs, implementation plans, design specs. The idea is to move some
of it into a shared agent thought collection beside the user's mindful corpus, so a
repository holds code and the docs a developer or user needs, while the working layer
stays easy to reach.

## 2. Current behaviour and evidence

Counts across the 21 tracked checkouts under `~/d` on 2026-10-02: about 2,770 task
records (`tasks/*.md`), 73 briefs (`docs/notes/`), 300 plans (`docs/plans/`), and 148
specs (`docs/specs/`). Task records dominate; beliefs, ops, and tasks alone hold about
1,260.

What depends on the in-repository location today:

- **Task records travel with the code.** The flow skill: "the task's record lives in the
  worktree it works in … because the record lands with the code"
  (`agents/skills/flow/SKILL.md`, "Where the record lives"). The tasks CLI refuses a
  write from a copy behind another checkout (`stale_copy`, tasks 7054f6f), which assumes
  records are versioned with branches.
- **Design-doc policy is a profile field.** `ops-profile explain` resolves
  `design_docs: commit` for personal; the staging hook enforces it, and the
  repository's own instructions can override it.
- **Records link to docs by repository path.** `--spec`, `--plan`, and brief sources
  (this brief included) are repository-relative paths.
- **obs indexes task records** for outcome measures (`obs/index.py`, `outcome_tasks`),
  and the review and concerns notes it reads live in those records.
- **mindful** stores thoughts with authorship (`createdBy.kind: human`), tags, and
  relations, and can search and walk the corpus. Whether it models an agent author and
  a separate collection has not been checked.

## 3. Constraints

- The flow trial (flow-trial-1) enrolls tasks from 2026-10-05 to 2027-01-10; moving task
  records during it changes the measured environment.
- Specs and plans keep their human review gates wherever they live.
- obs's outcome measures read task notes; any move keeps them readable by obs.
- Cross-project: tasks (storage and CLI), ops (profiles and the staging hook), mindful
  (collection model), obs (indexing), tack (instructions and flow).

## 4. Alternatives

1. **Status quo, tighter pruning.** Keep everything in the repo; delete or archive
   briefs and plans when their goal closes. Cheapest; doesn't change the shape.
2. **Move the narrative layer only (current lean).** Briefs, handoffs, and plans go to
   an agent collection in mindful, linked from tasks by thought id. Task records and
   specs stay in the repo, so the code-coupled pieces (flow's record-with-code, stale
   copy, review gates on specs) are untouched. Needs: an agent collection or tag scheme
   in mindful, a `--source`/`--plan` reference form that resolves thought ids, and a new
   profile value (for example `design_docs: mindful`).
3. **Move tasks too.** The leanest repositories, but it reverses the tasks design
   (records branch and merge with code) and needs a new consistency model for work in
   worktrees. Largest change, across four projects.

## 5. Unanswered questions

Answered by the user on 2026-10-02: only briefs, handoffs, and plans leave the
repository (alternative 2); task records and specs stay. Start now rather than after
flow-trial-1.

- Can mindful hold an agent-authored collection with stable ids that tasks can reference
  and obs can index? Shared corpus tagged by author, or a separate collection? —
  research tack-fa8757.
- tasks resolves `--plan` under `docs/plans` and checks `--step` against the plan's
  headings (tasks `src/repo.rs:66`, `src/resolve.rs:181`), so a plan outside the
  repository needs a tasks change; tack-fa8757 sizes it.

## 6. Proposed decomposition

- tack-fa8757: research on mindful, tasks, and obs readiness; wakes tack-fed9db.
- After it: a design task for the agent collection and the reference form, filed only if
  the research shows changes in more than one project.
