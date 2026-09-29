# Instruction provenance audit

Audited 2026-09-16 (ai-45934e). One row per rule in `AGENTS.md` (the global
CLAUDE.md) and per instruction in the authored skills `tasks`, `curate` (tasks repo,
`skills/`) and `quick-add` (ops repo, `skills/`). Each row records the failure the rule
guards against, where and when that failure was last observed, and whether the record
says a current model still shows it. Rules that encode a preference or an environment
fact rather than a failure are marked as such: they are not removal candidates on the
"no failure behind it" criterion, but they are candidates for moving out of prose.

**Evidence sources.** Commit history of `AGENTS.md` (17 commits since `b0e3454`,
2026-08-14) and of each skill; the `rules`- and `feedback`-tagged task records in ai,
tasks and ops; the tasks design specs under `docs/specs/`; the ops friction memo
(`docs/reports/2026-09-11-friction-diagnosis.md`, transcripts 2026-08-25 to 09-11);
and the pretooluse hook's block log (`$XDG_STATE_HOME/ops/attribution-blocks.log`,
83 entries, 2026-09-06 to 09-15), which is the only source that records *attempts*
rather than incidents someone chose to write down.

**Model attribution.** Every incident the records name was a Claude Code session, and
the `agent` stamps on the rule tasks read `claude-code/claude-opus-5[1m]`. Codex
appears only in the friction memo (F4, F8) and in the WORK_ROOT `--ensure` report. No
incident names Fable 5.1, Sonnet 5, Haiku 4.5, or a GPT model: nothing here says they
do not show a failure, only that nothing was recorded. The hook log carries no model
field.

**Still shows?** `yes` = observed on a current model after the rule landed; `rule
predates evidence` = the last observation is what caused the rule and nothing since;
`none recorded` = no incident found anywhere; `n/a` = not a failure-guard.

**Words** = words the rule costs in the rendered instruction file, the ranking key for
the removal list at the end.

## AGENTS.md

| # | Rule | Guards against | Last observed | Still shows? | Words |
|---|---|---|---|---|---|
| A1 | Composition > Inheritance | Deep class hierarchies where composition would do. | None recorded. Present at init (`b0e3454`, 2026-08-14); origin predates the repo. | none recorded | 3 |
| A2 | Explicit > Defensive | Defensive checks that hide missing state instead of failing. | None recorded. Init. | none recorded | 3 |
| A3 | Fail early / avoid silent fallbacks | Fallback branches that mask a broken input or missing file. | None recorded as an incident; the topic was on the advice-doc outline (`doc/agentic-coding-advice.md` §5 "silent fallbacks", never written up). Init. | none recorded | 6 |
| A4 | No legacy/compatibility layers unless asked | Shims kept "for compatibility" in a codebase with one consumer. | None recorded as an incident. The rule was already being restated per plan by 2026-07-14 (dotfiles `e74c54a`, noctalia plan: "Add no ... compatibility layer, or component name beginning with Unified"), so the failure predates the repo. | rule predates evidence | 10 |
| A5 | No "Unified" prefix | The `UnifiedX` naming reflex when merging two components. | Same trace as A4 (dotfiles `e74c54a`, 2026-07-14). | rule predates evidence | 9 |
| A6 | Conventional commits | Preference: commit-message format. | n/a | n/a | 3 |
| A7 | No AI attribution by default; guidelines decide where it is requested | Harness-injected `Claude-Session:` / session-URL / "Generated with" trailers and `Co-Authored-By: Claude` lines landing in commits and PRs; and, after `ai-57f4eb`/`ai-273c7a` (2026-09-14), the opposite error of omitting a trailer a repository does ask for. | Claude Code, continuously: the hook blocked 68 `Claude-Session` trailer attempts in 42 sessions between 2026-09-06 and 2026-09-15 (`attribution-blocks.log`), up to 9 per session. The prose rule was in place the whole time. | **yes** — daily; the guard that works is the hook, not the prose (the harness system-reminder asks for the trailer on every commit) | 106 |
| A8 | `gh` account per checkout | Writes to GitHub from the wrong account (the active account is global state and was `<work-account>` at filing time). | Environment fact, not a model failure. Filed `ai-bb99d4` 2026-09-14; enforced by hook check 1. | n/a (mechanised) | 57 |
| A9 | External PRs: draft, read CONTRIBUTING/PR template first, search duplicates, `--body-file` | A PR to a repository the user does not maintain opened without reading the guidelines; the PR flagged by maintainers. `--body` silently dropping the template; a duplicate of a closed attempt. | Claude Code (Opus 5), 2026-09-14: opencode PR #48990 opened as a draft but flagged for skipping CONTRIBUTING (`ai-b9dd14`, source URL on the record). `--body`/duplicate clauses (`ai-f05ae8`) were added from the same incident, not from a second one. Draft-ness is enforced by hook check 2; the guideline read, duplicate search and `--body-file` are prose only. | rule predates evidence (one incident, one day) | 198 |
| A10 | Worktree under `.worktrees/` for any repository code change; `git worktree add`, not the native tool; `just setup`; WORK_ROOT link/lock mechanics | (a) Direct fixes made on `main` because the rule only named brainstorming sessions; (b) `EnterWorktree` placing worktrees under `.claude/worktrees/`, which only one harness reads; (c) fresh worktrees failing tests for lack of dependencies; (d) worktrees on Dropbox filling the disk and Dropbox's inotify budget. | (a) `prism-28e29c` ran on main, reported 2026-09-13 (`ai-69ccac`, `tasks-61cc5c`); (b) `f9c9202` 2026-09-10, superpowers `using-git-worktrees` step 1a reaches for `EnterWorktree` before reading the directory preference; (c) friction memo F5 (forge, beliefs; 2026-08-25..09-11) — "resolved the same setup problem in three sessions"; (d) `ops-0f5ed2`: the Dropbox SSD at 98%, 59G of `.worktrees`, 2026-09-14. A Codex session on a temp-dir clone hit `--ensure` exit 1 on 2026-09-14 (tooling bug, fixed `7a1ee42`). | (a),(b): rule predates evidence; (c): mechanised by `just setup`; (d): environment fact | 205 |
| A11 | Paths shown to the user are relative to the main checkout, prefixed `.worktrees/<name>/` | Agent reports `src/foo.rs` from inside a worktree; the user, standing in the main checkout, cannot resolve it. | `f9c9202` 2026-09-10 (commit body: "Agents report paths relative to the worktree root; those do not resolve from the main checkout"). Verified compliant in the `ops-0f5ed2` Task 8 harness check, 2026-09-14. | rule predates evidence; one post-rule check passed | 69 |
| A12 | No machine-specific absolute paths (home directory, Dropbox root) in comments and docs | Machine-specific absolute paths committed. | None recorded. Init. | none recorded | 12 |
| A13 | Design specs and plans not committed by default; a checkout opts in through its own instructions; `.git/info/exclude`; copy out before removing a worktree | Superpowers specs/plans committed to public repos the user does not maintain and to work repos that never asked; a reviewer asked for one to be moved off a PR branch. The brainstorming skill says "commit the design document" and nothing countered it. | `ai-889237` 2026-09-15 (Opus 5). Hook check 4 landed the same day; its log shows real staging attempts in three sessions on 2026-09-15 (beliefs, prism, material, nodes) after the rule was in the instructions. | **yes** — attempted the day after the rule landed; the hook is the working guard | 228 |
| A14 | A doc's status header and checkboxes are claims about the past; verify against the tree | Trusting a stale "Status: draft" / unchecked box and redoing or skipping landed work. | None recorded as an incident. Init. `tasks check` now enforces the plan-heading half mechanically (drift contract). | none recorded | 38 |
| A15 | Correct the design doc's status in the same change that lands the work | Status going stale at merge. | None recorded. Init. | none recorded | 21 |
| A16 | After fixing a stale claim, grep user-facing docs for the same claim | Drift propagated into README/guides. | None recorded as an incident, though the pattern appears in commit bodies (`62131e1` corrected the same stale claim in a spec, README and AGENTS.md). Init. | none recorded | 21 |
| A17 | Hold a recommendation → state it with the rejected alternative and act; do not stop to confirm | Blocking questions whose "(Recommended)" option the user then accepts: one stop per question, each costing the time until the human returns. | Friction memo F1/F2, transcripts 2026-08-25..09-11, Claude sessions in forge/beliefs/tasks/material: 55–81% of questions carried a recommendation, accepted 89–94% of the time; ~120 of beliefs' 155 questions would have had the same outcome without the stop. Rule landed `1b5a445` 2026-09-11 (`ai-062b74`, source `ops-2cb205`). | rule predates evidence; the memo names the before/after measure (§5) and nothing has re-measured since | 72 |
| A18 | Stop only for review of an artifact, a taste/scope/priority choice, spend, or an action outside the repo | Same class as A17; also forge's serial spend re-authorisation loops (memo F4, Codex session 2026-08-29..31, four consecutive approvals of the same paid call). | Memo F2/F4, 2026-09-11. | rule predates evidence | 45 |
| A19 | Spec and plan keep their review gate; sections are not individually approved | Per-section "Approved / Revise" gates (memo F6: beliefs, 181 questions, design slicing and rulings). | Memo F6, 2026-09-11. | rule predates evidence | 28 |
| A20 | A question carries the recommendation first and is one question, not a series | Question series where the answers were predictable (memo F2). | Memo F2, 2026-09-11. | rule predates evidence | 18 |
| A21 | Confirm a sudden switch to a different project | Working in the wrong project after an ambiguous prompt. | None recorded. Init. | none recorded | 16 |

The generated projects block (~230 words) is not a rule; it is the routing vocabulary
`quick-add` and the prefix conventions depend on, rendered by `ops-projects`.

## tasks skill (`skills/tasks/SKILL.md`, 3271 words)

The skill is mostly a reference for a CLI whose `--help` is terse by design; the
imperative rules are a minority of its words. Rows marked *reference* describe a
capability rather than guard a failure; their cost is context, and the alternative is
a fuller `tasks help <cmd>`.

| # | Instruction | Guards against | Last observed | Still shows? | Words |
|---|---|---|---|---|---|
| T1 | Session protocol: `prime` first | Starting work without seeing parked work, closeout, and live claims. | Design (`62b524b` 2026-08-29); no incident. | none recorded | 25 |
| T2 | Pick from `ready`; never pick an `idea`; scope first | Implementing an unscoped one-liner as if it were a task. | Design; hierarchy spec §1 (2026-09-03) gives the motivating case: goals living only in documents, `ready` showing "nearly finished" with four large pieces outstanding. | none recorded post-rule | ~60 |
| T3 | `shelved`, `defer`, `--max-complexity` cutoff, `TASKS_MAX_COMPLEXITY`: what the pickers hide and why; do not take work from parked/roadmap; one exception for a parked idea waiting on the agent | A cheaper session picking a task rated above it; a session implementing an idea `next` handed it for scoping. | Complexity spec §3.3 (2026-09-12): rating reserved for a frontier session; the cutoff is a harness form. `tasks-f5ab4a` (from prism, 2026-09-15) asked for a one-shot defer. No incident of a cutoff session taking a hidden task. | none recorded | ~200 |
| T4 | Never pick a task with children (goals) | Implementing a goal directly instead of its pieces. | Hierarchy spec (2026-09-03). No incident. | none recorded | 12 |
| T5 | `next`, `quiet`, `list --sort` descriptions | *reference* | — | n/a | ~90 |
| T6 | Read `process`, follow **Process and workspace** before implementation; `start` before changing code | Brainstorming skipped without a decision; code changed with no owner recorded. | `prism-28e29c` on main, reported 2026-09-13 (process spec "Problem and evidence"). | rule predates evidence | ~40 |
| T7 | Claims: `start` records a claim outside git; `--force` takeover; `ready`/`next` omit live claims; `TASKS_SESSION` when agents share a process | Two sessions executing the same plan in the same worktree unaware of each other; `doing` invisible across worktrees; task files diverging and conflicting at merge. | `tasks-d184e3` (beliefs, 2026-09-04), `tasks-8f4b41` (material, 2026-09-05). Fixed in the CLI (claims spec 2026-09-05); the prose now describes the mechanism. | mechanised | ~90 |
| T8 | `note` whenever scope or understanding changes | Resume without the reasoning that changed the plan. | Design. | none recorded | 11 |
| T9 | `park` before ending a turn that waits on the user; `--waiting-on`, `--reason` vocabulary; when each reason fits | Unfinished work left silently open with the next step buried in prose notes (park spec §1, 2026-09-09); the memo's "what is the agent waiting on" gap (F8: restarts leave no trace). `--reason` came from memo intervention 1 (`tasks-82b559`, 2026-09-11). | Park spec problem statement; memo F8. `tasks-b5add6`/`tasks-74a525` (dots, prism, 2026-09-10): the skill required `park` before the installed binary had it — a skill/CLI version skew, not a model failure. | rule predates evidence | ~130 |
| T10 | Escalation: observable trigger, note the evidence, `park --reason capability --complexity <level>`; the level rules; `--waiting-on user` when no level exists; environment failure never raises the rating; rerun if not recorded | A cheaper session giving up on a feeling, or raising a rating to dodge work; a rating raised for a missing credential. | Complexity spec §3 (2026-09-12). No incident of misuse recorded either way. | none recorded | ~150 |
| T11 | `--reason quiet --minutes --needs headless` for host-load refusals; quiet is not environment or decision | Benchmarks and preflights that refuse on load being parked as "environment" and never resumed; the bedtime queue not knowing how long a job runs. | Quiet-queue spec (2026-09-13); memo F8 (material: niri restarts, TTY switching for benchmarks). | rule predates evidence | ~110 |
| T12 | `done` in the same commit as the code; no `--force` over open dependencies unless irrelevant; `done`/`drop` refuse with open descendants | Task records closing in a different commit from the work; goals closed over open children. | Design. Hierarchy spec review (`5db4fe6` 2026-09-03). | none recorded | ~60 |
| T13 | `TASKS_MODEL` / `TASKS_AGENT` stamps; `--agent` only when known, never guess | Completions with no model attribution; a guessed `agent` stamp (a fabricated provenance record). | Provenance design (`a8d634e` 2026-09-10; `5086fec` 2026-09-13). No incident of a guessed stamp. | none recorded | ~130 |
| T14 | Recurring tasks (`--every`) | *reference* | `e7f0be9` 2026-09-09 | n/a | ~60 |
| T15 | `check` before committing; a failing check means task and plan drifted; fix both | Plan headings renamed under an open task; `tasks/` files committed inconsistent. | Design; `tasks-80fec3` (2026-09-03) added the uncommitted-files warning to `prime`. | none recorded post-rule | 18 |
| T16 | Closeout: confirm the goal is met, or add the missing children | Goals closed on child count alone. | `tasks-3c611e` (ops, 2026-09-08): closeout listed a goal whose depends were still open — a CLI bug, fixed. | mechanised | 22 |
| T17 | Never edit `tasks/*.md` directly; `edit` flag list; `--tag` is additive; tag dictionary | Hand edits breaking the schema; `edit --tag` replacing the whole list and dropping provenance tags during triage. | `tasks-289fdb` (2026-09-04): `--tag` replaced the list. Fixed in the CLI (`67d7535`); the prose describes current behaviour. | mechanised | ~120 |
| T18 | `--source` semantics; sourced `add` is idempotent; reused call's flags are ignored, not merged | Refiling a batch creating duplicates; assuming a reused add merged its flags. | `b6895eb` 2026-09-07: "the first real quick-add batches showed exact title equality is the right key". No incident of flags assumed merged. | none recorded post-rule | ~90 |
| T19 | Write commands route by id prefix; read commands take `--project`/`--all-projects`; `tree <id>` routes by prefix | `task_not_found` on a foreign id; `-C <dir>` needed to read another project; `tree` documenting a bug as intended behaviour. | `tasks-2eccdc` (ops, 2026-09-05), `tasks-7eb169` (2026-09-07), `tasks-88d356` (2026-09-08, "the skill documented the gap as though it were intended"). All fixed in the CLI. | mechanised | ~170 |
| T20 | Process and workspace: `direct`/`planned`/missing semantics; do not silently default or infer from size, priority, complexity, parents, or links; escalate direct→planned on an unresolved design decision | Skipping brainstorming without a recorded decision; inferring approval from a document link. | Process spec (2026-09-13), motivated by `prism-28e29c`. | rule predates evidence | ~180 |
| T21 | Both paths use an isolated worktree; commit the task record before `git worktree add`; `just setup` else the root guide's explicit setup command; never guess an installer | A worktree started from an uncommitted record, which then cannot be completed there without divergence; a guessed installer on a project without Just. | `tasks-5a46b9` (from ai, 2026-09-14): record uncommitted before worktree; `tasks-5e6971` (from rad, 2026-09-15): no Just. Both Opus 5, both landed 2026-09-15. | rule predates evidence (two incidents, each once) | ~110 |
| T22 | Recording work: idea vs todo vs shelve; scoped-add flag recipe; complexity rubric with the "precisely specified concurrent algorithm can still be high / many files does not make it high" calibration; choose process separately | Size mistaken for complexity; complexity inherited from a parent. | Complexity spec (2026-09-12). `ai-e2b3f6` (closed 2026-09-16) found one unrated task in this project. | none recorded | ~250 |
| T23 | Decomposing: children with `--parent`, `dep` only for ordering; a committed goal is a `todo` with a body | Goals as ideas; dependencies used to express hierarchy. | Hierarchy spec §1 (2026-09-03). | none recorded post-rule | ~90 |
| T24 | `--parallel` marker asserts only pairwise non-collision; read `doing` before dispatch; re-examine on scope change | Dispatching agents onto tasks that collide with in-flight work. | `9860017` 2026-09-06. No incident. | none recorded | ~80 |
| T25 | Cross-project goals and pieces; `tasks root` | *reference* | `bf72a65` 2026-09-04 | n/a | ~70 |
| T26 | Id collision after a merge: keep one, rename the other, fix `depends` | Two branches minting the same random id. | Design; no incident recorded. | none recorded | ~40 |
| T27 | Throwaway registry for scratch projects (`XDG_CONFIG_HOME=$(mktemp -d)`) | Stale registry entries pointing at deleted temp dirs. | `5189613` 2026-09-04; `tasks-9b5f81` (beliefs, 2026-09-04): init could not re-point a stale prefix. | rule predates evidence | ~80 |
| T28 | Prefix renames and recovery | *reference* for a rare command; the recovery caveats guard against treating `git checkout .` as an undo. | `8361032` 2026-09-08. No incident. | none recorded | 204 |
| T29 | With superpowers: brainstorming attaches with `--spec`; writing-plans adds one child per heading with explicit `--complexity` and `--process`; plan headings are the drift contract | Plan children without a process or rating; headings renamed silently. | `ai-e8dcc5` 2026-09-13: there is no locally owned writing-plans skill, so the adapter lives here. | none recorded | ~180 |
| T30 | Feedback: file at the moment; describe the tool, not the project; no repo names or paths; do not commit upstream; `--recur`/`--new` | Project details leaking into a public repository's task corpus. | Feedback design (`963b94f` 2026-09-03). No leak recorded; the redaction step in "In the tasks repository" exists because reports arrive unreviewed. | none recorded | ~170 |

## curate skill (`skills/curate/SKILL.md`, 1187 words)

| # | Instruction | Guards against | Last observed | Still shows? | Words |
|---|---|---|---|---|---|
| C1 | One pass improves what it draws; creates no tasks, drops none, changes no priority — proposals only | A maintenance pass that grows the corpus or makes decisions that are the human's. | Curation spec "Problem"/"Decision" (2026-09-08). Design bound, no incident. | none recorded | ~50 |
| C2 | Read `sample`'s warnings: shortfall, live-claim omissions, `pending` proposals; relay, do not open | Re-reporting a proposal the human has not answered; opening a claimed task. | `f2cd47a` 2026-09-09: the first pass had the skill re-check pending itself; moved into `sample`. | mechanised | ~70 |
| C3 | One root per task: fix the root and run every command as `tasks -C <root>` | Sampling one copy of a task from a worktree and rewriting another. | Curation spec review rounds (`2fa2601`, `71d6298` 2026-09-09); the unscoped-root rule corrected in `f2cd47a`. No incident of a wrong-copy write. | none recorded | 159 |
| C4 | Read the task, spec, plan, parent; gather evidence with grep and `git log -S`; check duplicates | A verdict without evidence. | Design. | none recorded | ~80 |
| C5 | Exactly one verdict from the fixed set | Free-form verdicts that the summary cannot group. | Design. | none recorded | ~110 |
| C6 | Revalidate immediately before the first write: status, live claim, `updated` stamp; a check, not a lock | Writing over a task that became active or changed during the pass. | `0a79d28` 2026-09-09 (revalidation tests). No incident. | none recorded | ~100 |
| C7 | Edit only through the CLI, only the listed fields; never status/priority/`--parallel`/`--source`/`add`/`drop`/hand edits; `--process` with evidence, never inferred | Curation changing meaning or ownership; process inferred from size or links. | Process spec (2026-09-13) added the `--process` clause. | none recorded | ~250 |
| C8 | Exactly one `curate:` note; `proposal:` only for the four verdicts | Missing audit trail; a task re-drawn every pass. | Design; the note is what `sample` reads. | mechanised (the pool rule is in code) | ~50 |
| C9 | Bounds: zero new tasks; prefer shorter; touch only the sampled tasks | Rewrites that grow bodies without adding facts. | Design. | none recorded | 47 |
| C10 | Summary format: one line per task, then the human's decisions grouped | A pass whose output the human has to re-read to find the decisions. | Design. | none recorded | 92 |
| C11 | What a good task reads like | Style guidance for rewrites. | Design. | n/a | 53 |
| C12 | Kinds are derived from passes, not written up front (`tasks-5b73bf`) | Premature templates. | Design. | n/a | 28 |

## quick-add skill (`skills/quick-add/SKILL.md`, 1389 words)

| # | Instruction | Guards against | Last observed | Still shows? | Words |
|---|---|---|---|---|---|
| Q1 | Read routing.toml, the registry, and identity.toml; resolve the symlink first | Project mentions resolving to nothing because the skill named the registry alone, which has no aliases: "an explicit instruction naming the wrong source beats the rendered projects block sitting in the session's context". | `62131e1` 2026-09-09 (`ops-8b27e5`): `niri`, `mindful` unresolved. | rule predates evidence | ~60 |
| Q2 | `bin/mindful-op` over HTTP; never fall back to a local corpus command when HTTP fails; no proxies, redirects, retries | Writes going to a different store than the running web service; a retry duplicating an uncertain capture. | `ops-207179` 2026-09-12 (the cutover design). No incident of a fallback write. | none recorded | ~80 |
| Q3 | Read human self once via `mindful --json config self`; fail if unset or not human; never infer the human author from a model name; supply the agent as `via` | Captures attributed to an agent, or to a human guessed from a model name. | `ops-207179`; actor validation is in the API. | mechanised (API validates) + prose | ~70 |
| Q4 | Title = first non-empty line, 80 chars; body unchanged | Reworded pastes. | Design (2026-09-06). | none recorded | ~30 |
| Q5 | Construct operation JSON as data; never interpolate pasted prose into shell commands | Shell injection / quoting breakage from a paste. | `ops-207179`; the code block exists so the model does not build a shell string. No incident. | none recorded | ~30 |
| Q6 | Uncertain capture: do not retry or re-paste; reconcile; report `result.id` immediately | Duplicate seeds from a timed-out capture that actually committed. | `ops-207179` (task text: "no automatic retry after uncertain capture"). No incident. | none recorded | ~50 |
| Q7 | Existing reference: strip only `mindful:`; keep the `thought:` prefix; source is exactly `mindful:<seed>` | Source strings that `list --source` cannot match byte for byte. | Design §3; `ops-a95a4f` backfilled seventeen hand-filed tasks 2026-09-07. | rule predates evidence | ~60 |
| Q8 | Parse: `idea` vs `todo`; raw paste stays in mindful; `idea`/`todo` are statuses, never tags | Tasks carrying the paste verbatim; status as a tag. | Design. | none recorded | ~60 |
| Q9 | Project mention = prefix, name, or alias, one namespace; unknown projects, conflicting cues, unclear destinations require a question; never ops as a catch-all | Guessing a destination; dumping unclear items into ops. | `62131e1` 2026-09-09; the `mindful`/`seed` collision is the recorded case of one word naming two things. | rule predates evidence | ~90 |
| Q10 | Read each candidate project once, closed tasks included; rows with this seed's source are an earlier run: reuse title and id; near-duplicates from other origins are referenced, not refiled | Duplicates across reruns; a second task for something another origin already filed. | `1d0bbf0` 2026-09-07 moved the exact check into the CLI; "the step-2 read stays: near-duplicates from other origins are still the skill's judgement". | half mechanised | ~90 |
| Q11 | Tag lookup: only `NOT_FOUND` means missing; `AMBIGUOUS` needs the user; never create a tag to resolve ambiguity | A second tag thought created because the first name was ambiguous. | `ops-207179`. No incident. | none recorded | ~50 |
| Q12 | One review table before filing; wait for one approval; general permission does not approve an unseen table; no item-by-item questions | Filing without review; or a question per item (memo F2 class). | Design (2026-09-06); one review is the skill's founding constraint. | none recorded | ~190 |
| Q13 | Sourced add is idempotent; read `action`; `reused` ignores flags; a failed add is not a reused one | Assuming a reused row was updated; treating a failure as a reuse. | `1d0bbf0` 2026-09-07. | none recorded | ~80 |
| Q14 | Seed-bound items stay in the seed; add the union of approved tags to the seed; recheck tag names before creating | Per-item thoughts; a tag created twice on a rerun. | Design §4. | none recorded | ~70 |
| Q15 | Tag every approved tag; tagging is idempotent | (Was) `mindful tag` appending duplicate relations. | `mind6-7ee879` fixed 2026-09-12; the pre-read workaround removed 2026-09-16 (`ai-5b72de`). | mechanised | ~40 |
| Q16 | `tasks check` in every touched project; report seed, ids, tags, unanswered rows, failures; a mid-batch failure leaves writes in place — retry filing, never an uncertain capture; do not commit | Partial batches left inconsistent; the skill committing under its own protocol. | Design §4/§5. | none recorded | ~110 |

## Removal candidates, ranked by context cost

"Remove" here means take out of the always-loaded prose. Most candidates are not
wrong; they are either enforced elsewhere (a hook or the CLI) so the words buy
nothing, or they are mechanics that belong in the tool they describe. Words saved are
against the current text.

| Rank | Candidate | Words | Basis | Proposed form |
|---|---|---|---|---|
| 1 | A13 design-doc mechanics: the `docs/superpowers` migration clause, the `git config ops.designDocs` escape hatch, the `.git/info/exclude` recipe, the copy-before-removing-a-worktree step | ~150 of 228 | Hook check 4 blocks the staging and its refusal message already names the checkout's convention and the instruction-file line to add. The rule *did not* prevent attempts (three sessions on 2026-09-15); the hook did. | Keep the rule (~60 words: not committed by default; a checkout opts in by naming the directory in its instructions; otherwise write it at the skill's path, excluded). Move the mechanics into the hook message and the `flow`/brainstorming adapter. |
| 2 | A10 WORK_ROOT mechanics: symlink creation, `work-link --ensure`, lock reason, unlock-then-remove, the "outside" case | ~110 of 205 | Environment facts the tooling owns. `just setup` and `work-link` already do the linking; a wrapper (or a `just worktree <name>` recipe) can lock on creation and unlock on removal. | Keep: worktree under `.worktrees/` for any code change, `git worktree add` not the native tool, `just setup` after, reuse on resume. Move the rest into the recipe. |
| 3 | T19 routing paragraphs (write commands route by prefix; read commands take `--project`; `tree` exception) | ~170 | All three describe fixed CLI behaviour (`tasks-2eccdc`, `-7eb169`, `-88d356`); nothing an agent can get wrong now except not knowing the flag exists, which `--help` covers. | One sentence: "Every id-taking command routes by the id's prefix; read commands take `--project <prefix>` or `--all-projects`." |
| 4 | A9 + A7 overlap: the guideline list (CONTRIBUTING casing/locations, PR template paths, repo AGENTS.md) appears in both bullets; draft-ness is hook-enforced | ~90 of 304 | One incident (2026-09-14) produced both bullets in one afternoon; the list is duplicated verbatim. Hook check 2 enforces `--draft`. | Merge into one bullet: read the guidelines before the work; attribute only where they ask, at that level; external PRs are drafts and must meet every stated convention; search open and closed PRs and issues first; `--body-file`. |
| 5 | T28 prefix renames and recovery | 204 | Rare command; no incident; the recovery procedure is linked from the spec. | Two lines: the command exists, retired prefixes keep resolving, and the spec's §5.6 is the recovery procedure. |
| 6 | T17 flag inventory and tag-dictionary paragraph | ~90 of 120 | Reference; `--tag` additivity is CLI behaviour now. | Keep "never edit `tasks/*.md` directly" and "prefer a defined tag"; drop the flag list (`tasks edit --help`). |
| 7 | T13 stamp mechanics (`TASKS_MODEL`, `TASKS_AGENT`, feedback's env-var form, `edit --agent`) | ~100 of 130 | The harness exports the variables (`ai-d5a56c`); the only agent-facing rule is "never guess". | Keep "pass `--agent` only when you know it; never guess". |
| 8 | T7 claim mechanics (store, liveness handle, `TASKS_SESSION` guidance) | ~60 of 90 | Fixed in the CLI 2026-09-05; the warnings explain omissions at the point of use. | Keep `--force` semantics and "`ready` omits live claims". |
| 9 | T3 picker-hiding inventory (shelved, deferred, cutoff, what each command hides and warns) | ~120 of 200 | `ready`/`next` say in warnings what they hid; the prose repeats the warnings. | Keep the three rules (never an idea; under a cutoff pick only through `ready`/`next`; the parked-idea exception). |
| 10 | Q12 review-table prose | ~60 of 190 | The table header and the "wait for one approval" rule carry the guard; the column-by-column description restates the header. | Keep the header, the one-approval rule and the cross-project layout note. |
| 11 | A14–A16 doc-status triplet | 80 | No incident in the record; the plan-heading half is now `tasks check`'s drift contract. Keeping these is a judgment call — they are cheap and the failure class is real elsewhere. | Fold into one bullet (~30 words). |
| 12 | A1–A5 core and refactoring rules | 31 | No recorded failure; A4/A5 were already being restated per plan in July, which is weak evidence the reflex existed then. Cost is negligible, so the "no failure behind it" criterion applies but the saving does not. | Keep until a per-model variant question makes it matter; then test by removal. |
| 13 | A21 project-switch confirmation | 16 | No recorded failure. | Keep or drop; cost is negligible. |

Not candidates:

- **A7 attribution and A13 design docs (the rule itself).** The only two rules with
  post-rule evidence of the failure recurring on a current model. Their prose is still
  worth keeping because Codex and opencode read the same file and have no hook.
- **A17–A20 Decisions.** The strongest pre-rule evidence in the corpus (memo F2,
  hundreds of questions) and no post-rule measurement. Re-run the memo's question
  measure before touching them.
- **A11 path reporting.** Structural: an agent sees the worktree cwd; the rule is the
  only guard.
- **T21 commit-before-worktree, T6/T20 process.** Two-day-old rules from real
  incidents; too early to judge.

## Per-model variants

The task asks which rules justify a per-model variant: only a rule whose failure
differs by model. The record cannot answer that yet: every named incident is a Claude
Code session, the hook log has no model field, and the Codex evidence (memo F4, F8) is
about session shape, not rule violations. Two things would make the answer computable:

1. A `model` field on the hook block log (the harness exposes it; `TASKS_MODEL` is
   already exported by the same session-start hook).
2. The question measure from memo §5 re-run per model, which needs the session-log
   parsing goal (`ai-bc49ed`).

Until then the only per-model signal is the settings drift observed during this audit:
the work profile has moved to Fable 5.1 (uncommitted `claude/settings.work.json`), so
the next incidents will be the first Fable data points.

## Method notes

- `mindful search` returned nothing useful for rule origins; the source thought of
  this task (`8e45d49e`) is the quick-add batch that filed it, not a rule discussion.
- The advice document (`doc/agentic-coding-advice.md`) lists "silent fallbacks" and
  "unified" as topics but never wrote them up, so it is not a provenance source.
- Word counts are from the rendered files on 2026-09-16; the tasks-skill rows are
  approximate because instructions span paragraphs.
