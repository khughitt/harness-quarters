# First-prompt motifs

Scoping handoff, 2026-10-13. Idea: hq-1459f0. Goal and research ids are in §6.

## Problem

A session's first prompt says a lot about what kind of conversation follows. The
owner's framing (2026-10-12): "implement x" and "review y" likely lead to different
conversations and flows. The idea is to name the recurring kinds of first prompt, such
as greenfield project idea, feature idea, research idea or copied message, with
examples of each, and to treat "copied" as a modifier that combines with the others.
Nothing yet shows whether those kinds separate session shapes well enough to be worth
tooling.

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

## Constraints

- Read the stores through the existing readers. Never modify harness stores. Keep
  private transcript text out of committed artifacts: commit labels, counts, session
  locators and paraphrased examples only.
- If the human-or-injected list changes, change it together in session-episodes and
  obs's two adapters, as the skill says.
- Motif labels are inferred, not observed.

## Alternatives

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
