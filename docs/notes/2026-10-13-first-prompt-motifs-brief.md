# First-prompt motifs

Scoping handoff, 2026-10-13. Idea: hq-1459f0. Goal and research ids are in §6.

Updated 2026-10-25 from the owner's completed inspection and the first dry run.
This is a scope handoff, not a design or implementation approval. The owner requests no further session
collection. Historical evidence and the original pilot proposal remain below;
the dated updates distinguish the supplied result from unperformed validation.

## Problem

A session's first prompt says a lot about what kind of conversation follows. The
owner's framing (2026-10-12): "implement x" and "review y" likely lead to different
conversations and flows. The idea is to name the recurring kinds of first prompt, such
as greenfield project idea, feature idea, research idea or copied message, with
examples of each, and to treat "copied" as a modifier that combines with the others.
Nothing yet shows whether those kinds separate session shapes well enough to be worth
tooling.

The inspection supplies recurring opening forms and a possible consumer: reducing
the repeated copying of review targets and context into a new session. These are two
questions: whether motifs explain session outcomes, and whether a task-based review
prompt saves effort. The dry-run consumer need not wait for an outcome-prediction
study. The supplied result does not establish that motifs predict outcomes.

## Current behaviour and evidence

- `agents/bin/session-episodes` already reads both stores into ordered events
  (`read_claude`, `read_codex`). It tags human turns, strips the `<pasted_content>`
  wrapper while keeping the pasted text (4e8762c), and skips subagent and
  non-interactive files before it parses them. It has no command that lists a
  session's first human turn.
- The human-or-injected rule (`agents/skills/session-logs/SKILL.md`, "Human or
  injected") treats any turn starting with `<` as not human. A Claude Code session
  opened with a slash command starts with a `<command-name>` wrapper, so under that
  rule its first human turn is a later one or doesn't exist. Skill-opened sessions are
  probably a large motif of their own, and the current rule hides them.
- Scale: the session-episodes acceptance run (hq-bc49ed, 2026-09-19) read 1,094 Claude
  Code and 14,460 Codex files. It excluded 10,490 subagent files and 1,713
  non-interactive ones, which leaves roughly 3,300 interactive sessions.
- The idea was filed in obs as obs-0b0167 and moved here on 2026-10-12 by the owner's
  decision. obs keeps no prompt text in its index (outcome measures D6). Its research
  obs-82341c labels follow-up owner turns for missed intent and excludes first prompts
  explicitly. The earlier scope note on this idea, which pointed at obs-82341c, is out
  of date. obs's brief `docs/notes/2026-10-12-human-turn-labels-brief.md` (in obs)
  records the labels-only precedent, and obs-82341c's population rule (dispatch
  prompts, injected messages, fork and resume copies excluded and counted) carries over
  to first prompts.
- "Copied" overlaps with the mediated-exchange work: a Codex session whose first prompt
  is a pasted Claude message is one leg of a relayed exchange (hq-ba1758,
  `docs/notes/2026-10-10-mediated-cross-harness-brief.md`).

### Supplied inspection, 2026-10-24

The local script imports the session-episodes readers. The supplied summary reports
1,374 recently modified files: 376 subagents, 506 non-interactive sessions, 15 opened
before the window, 23 without a timed record, four without human text, and 444 kept.
It records session locator, harness/home/project, opening time, preceding slash
commands, first human text and turn counts. Raw prompts include work-home text;
their location and checkpoint belong in task retained-item notes, not this document.

| Opening bucket | Reported sessions |
| --- | ---: |
| Take a task | 116 |
| Scope | 107 |
| Review | 76 |
| Choose next | 45 |
| Test/smoke, identified by cwd | 24 |
| Execute | 22 |
| Free-form | 20 |
| Question/investigation | 17 |
| Idea/file a task | 10 |
| Copied reply | 4 |
| Other skill | 3 |

Keep intent commands such as `/scope` as motif evidence; record configuration
commands separately, including `/clear` (42), `/model` (24) and `/effort` (18).
Preserve both the actual opening command and the first substantive text. A copied
approval or answer may continue an earlier conversation, while copied feature or
research prompts can still be independent openings: copying and continuation are
separate attributes. A one-human-turn session is not necessarily empty or useless.

The launcher report separately identifies 77 non-test review prompts: 56 naming a
docs path, 28 a task id, and 44 with a resolved task record (28 explicit ids, 16
basename matches). Of those 44, 25 have spec/plan fields, 13 SHA-bearing notes, and
three a worktree in a review note. Eighteen typed paths match the linked artifact;
three reported differences include sibling documents or ledgers. These are candidate
resolutions, not proof of the correct artifact and revision.

Limits to carry forward without collecting more sessions:

- The supplied narrative's harness totals, 209 + 229, equal 438 rather than 444;
  the bucket table's harness columns total 215 + 229. Its turn-count groups,
  186 + 142 + 97, total 425, and 186 of 444 is about 42 percent, not half.
- The five proposed intents total 366: about 82 percent of all 444, or 87 percent
  of 420 after removing 24 test sessions. The reported 82 percent after removing
  tests mixes denominators.
- The motif tally has 76 reviews and the launcher report has 77. The 25 linked
  artifacts are not fully accounted for by 18 matches and three differences.
  Preserve the two reports' populations and do not infer missing results.
- This was rule-based inspection, not the original random, harness-stratified
  75/75 frozen-taxonomy validation. The supplied summary reports no fork copies
  excluded; that alone does not demonstrate copy detection coverage.
- Similar median turns do not answer duration, task/spec activity or tool-error
  questions. Four copied-reply labels do not estimate all copied prompts.
- Fourteen identical prompts across harnesses are a reason to retain harness
  choice, not evidence requiring automatic dual launch.
- `hq sessions` uses Claude prompt-history display text and Codex thread names or
  titles, with 60-character display labels and activity-based ordering. Its earlier
  listing cannot substitute for opening-time, transcript-based evidence.

### Dry-run follow-through, 2026-10-24

hq-268cc2 verified the six retained inputs and evaluated the saved mappings without
collecting sessions or launching a harness. The original launcher artifact retains
three sample mappings but no per-case inventory or resolver for the reported 44.
All three samples have unique dataset locators: one reconstructs an implementation
review at its explicit merge revision, while two map to the wrong task (one crosses
repositories; the other selects a child created after the review opened).

Counts against the reported 44 are **1 matched historical target, 0 incomplete,
2 ambiguous/misbound, and 41 unavailable identities**. Within the three recovered
mappings the counts are 1/3 matched and 2/3 ambiguous. These were differing examples,
not a representative sample; neither denominator estimates general resolver
coverage. No current review/worktree state is established by the closed records.

The portable report is attached to hq-268cc2 at
`tasks/files/hq-268cc2/review-dry-run-report.md`. The script, task snapshots and
editable previews stay local under the retained-item ownership of hq-2d8e81.
Four self-checks cover unambiguous, missing, conflicting and future-only revision
evidence, each with a caught targeted break. Recommendation: keep the editable,
explicit-selection experiment as the launcher milestone; do not build a production
command from this result. Concrete candidate gaps are target identity, kind/revision
binding and current review state, with tasks/flows ownership discussed in the
report; no shared-schema prerequisite is established. The unavailable mappings
remain unavailable rather than being replaced by new matches.

### Next experiment scoped, 2026-10-25

hq-2b3929 tests the next milestone. The merged result (7d66d22) supports using a
deliberately selected, named set rather than trying to reconstruct the missing
41 mappings.
The old helper left repository and artifact checks to the investigator. The next
experiment puts those checks inside the helper and freezes each case's provenance,
selected kind/target/revision, historical or current state, and expected outcome
before evaluation. Retain C01/C02/C03; add only labelled controlled variants for
missing, conflicting and stale evidence, at most six cases total. Derived cases
are checks, not additional observed reviews or a coverage estimate.

A positive result requires repository identity and commit/blob availability, or
an exact out-of-tree artifact hash, to pass. C02 can be a historical positive;
it cannot establish a current review. Unsupported review kinds remain explicit.
Keep editable previews local, record required manual corrections, and recommend
whether a narrow production preview is worth designing. No launch or new session
collection is part of this experiment.

At scoping, both retained manifest hashes and all 24 listed files matched. The
original six-file manifest excludes 12 later inspection files recorded in the
idea's notes; account for these before reuse without deleting evidence or assuming
that historical extracts are reproducible from today's live stores. The complete
18-file dry-run bundle had no unlisted files. hq-2d8e81 retains both bundles.

## Constraints

- Read the stores through the existing readers. Never modify harness stores. Keep
  private transcript text out of committed artifacts: commit labels, counts, session
  locators and paraphrased examples only.
- If the human-or-injected list changes, change it together in session-episodes and
  obs's two adapters, as the skill says.
- Motif labels are inferred, not observed.

- Current scope: record and interpret the supplied inspection, with the limits above;
  do not repeat the historical 30-day/150-session study. Its unanswered outcome
  questions remain unproven, not prerequisites to the prompt-builder experiment.
- The launcher experiment is dry-run only. It may inspect the existing cases and
  task records, but launches no harness, changes no session store, and adds no
  product CLI, shared schema, model judge or embedding pipeline.
- A review handoff must identify review kind, target repository/artifact and the
  corresponding frozen commit or out-of-tree hash. Multiple artifacts, stale notes,
  basename collisions and missing revision/worktree evidence must be explicit.
  A task id or any SHA in its notes is insufficient by itself.

## Alternatives

Current lean: hq-83c787 records the inspection's useful findings and limits;
independently, test editable drafts with explicit target selection and validation
inside the helper, using the bounded set above. Compare context and meaning, not
identical wording. A second option is to stop with the existing report if explicit
selection saves no meaningful work. Reject a production launcher or mandatory
handoff-schema project now: the nonrepresentative evidence does not justify either.
Production hq integration, if supported, adopts
ops's existing CLI vocabulary with that implementation. Crew remains a possible
flow consumer; lore owns shared template text only when there is a second consumer.
fzf target selection, other actions, graphical flow links, dual launch, CLI visual
components and text/embedding indexes are preserved possibilities, not this task.
The later one-turn inspection also suggests offering a preceding choose-next
recommendation as a default target and a `--harness both` option. Preserve these as
later candidates: a suggested next task does not identify its review revision,
and repeated prompts across harnesses do not establish a need for automatic launch.

Historical alternatives, retained as context rather than new work orders:

1. **Hand-labelled pilot first (recommended).** Label a random sample of first
   prompts, letting the motifs emerge, freeze the taxonomy, label a second half with
   it, and check whether motifs line up with session shape. Cheap, needs no tooling,
   and settles whether the idea pays off.
2. **A `first-prompts` subcommand in session-episodes with deterministic labels.**
   Worth building only if the pilot finds motifs that patterns can separate, and that
   predict shape.
3. **A judged taxonomy over the whole store.** A model labels every first prompt. That
   needs its own judge validation, and like obs-82341c's option B it isn't earned
   before the pilot.

## Unanswered questions

Current follow-through:

- hq-83c787 records the supplied inspection, the denominator and method limits, and
  what it supports. No additional population collection or duration/error study is
  required by this scope pass. Predictive validity remains unknown.
- The next explicit-selection experiment determines whether validated editable
  drafts preserve intended context, which corrections remain manual, and whether
  a narrow production preview is worthwhile. The frozen case manifest and report
  answer this; a human judges any eventual interactive preview. It does not
  assume a new schema or establish population-wide resolver coverage.
- A live launch and the final choice of supported actions remain later decisions.

Original research questions, not answered by the inspection:

- Which motifs recur, and does "copied" combine with the others or stand as its own
  kind? Answered by hq-83c787.
- Do motifs line up with session shape (human-turn count, duration, whether a task is
  started or a spec or plan is written) and with the tool errors a session meets?
  Answered by hq-83c787, using Claude Code's `is_error` and Codex's `exit_code`, which
  both stores record.

Decided by the owner, 2026-10-13:

- A session opened by a slash command counts the command (for example `/scope`) as its
  first prompt. Opening with a command strongly indicates the intent and how the
  conversation will go, so it is a motif signal, not noise to exclude.
- Motifs have two consumers. First, obs and any session-data mining or debugging layer:
  the kinds and rate of errors probably depend on the kind of conversation, which the
  opening prompt partly reveals, so a motif can stratify error and failure series.
  Second, flows, or whichever system detects conversation patterns and derives
  structured flows from them. The pilot's recommendation says which of these its
  evidence supports.

## Proposed decomposition

| Task | Next action | Ideas it wakes |
| --- | --- | --- |
| hq-83c787 | Label 150 first prompts in two halves, freeze the taxonomy, relate motifs to session shape and tool errors, recommend option 1, 2 or 3 and its consumers | hq-1459f0 |
| hq-1459f0 | Stays an idea until the pilot shows motifs that separate session shapes | — |

Goal: hq-4c1555. Not a design task: one pilot answers the open questions first.

Current scope supersedes the historical pilot instruction in the table: hq-83c787
records this result and its limits, then wakes hq-1459f0.

| Task | Current next action | Ideas it wakes |
| --- | --- | --- |
| hq-83c787 | Record the supplied inspection and its limits without more collection | hq-1459f0 |
| hq-1459f0 | Reconsider the motif/tooling idea after the result is recorded | — |
| hq-268cc2 | Done: one historical match, two misbound mappings, 41 unavailable identities; separate artifact checks required | hq-2d8e81 |
| hq-2b3929 | Test editable drafts with a frozen case manifest, explicit selection and built-in repository/artifact validation | hq-2d8e81 |
| hq-2d8e81 | Wait on hq-2b3929; own the retained private inspection and dry-run artifacts | — |

The completed hq-268cc2 remains evidence; the next experiment, not a new taxonomy
study, supplies the launcher's remaining decision. Historical
session-content search remains hq-3558a1 / hq-ea0975; this pass does not duplicate or
re-scope those tasks. The session evidence reader remains obs-d98663, with its own
delivery constraints, and is not a prerequisite for this local experiment.
