# Session search — brief

Idea: hq-3558a1 (hq sessions search: find a past session by its content and launch it).
Lane: hq-65f661. Scoped 2026-10-17.

## 1. Problem

`hq sessions` (hq-839083) lists recent sessions across harness homes from their native
metadata and launches one. Finding an older session means remembering roughly when it
ran and in which directory. The idea, from the source thought's "later" half, is to find
one by what was said in it (`hq sessions search <text>`, or `/` in a picker) and launch
it through the existing launcher.

## 2. Current behaviour and evidence

- `tools/hq_cli/sessions.py` reads Claude `<home>/history.jsonl` (one line per typed
  prompt) and Codex `<home>/state_5.sqlite` `threads` (whose `preview` holds the
  first prompt). Neither read keeps prompt text beyond the listing's title.
- The scoping of hq-839083 (docs/notes/2026-10-15-session-discovery-contract.md, "What
  depends on obs") named obs's index as the candidate source for full-text search,
  gated on obs-914269. That premise does not hold: obs's `index.py` schema keeps
  per-session and per-turn counts and byte sizes (`turns.output_text_bytes`,
  `prompt_bytes`) and no message text, and no obs task proposes indexing text.
  obs-914269 widens coverage to `archived_sessions/` and `~/.codex-work`, not content.
- Typed-prompt text already exists per home, keyed by session id:
  Claude `history.jsonl` (`display`, `pastedContents`, `sessionId`; personal 36,701
  lines, work 3,298) and Codex `history.jsonl` (`text`, `session_id`; personal 23,151
  lines, work 932). Assistant output and tool results live only in transcripts:
  `~/.claude/projects` 3.9G and `~/.codex/sessions` 25G on this host.

## 3. Constraints

- The lane's guidance (hq-65f661): no shared search framework and no new transcript
  index; keep the session launcher independent of the thought picker.
- Launching reuses hq-839083's native resume contract; hq-d2c11e still probes two
  unverified resume paths.
- Session stores are read-only inputs; archive tests and probes use temporary stores
  (AGENTS.md).

## 4. Alternatives

1. **Search typed prompts.** Grep the per-home `history.jsonl` files (and the Codex
   `preview`), group hits by session id, and print `hq sessions` rows for the matching
   sessions. No index, sub-second on today's sizes (to be measured), and it matches how
   a person remembers a session: by what they asked.
2. **Scan transcripts.** `rg` over transcript files, bounded by home, harness and
   recency, for text the assistant or a tool produced. Finds more, but costs a scan of
   up to ~29G per query and must exclude injected context (skills, instructions) that
   repeats across sessions.
3. **Index text in obs** (an FTS table). Rejected for now: it is the new transcript
   index the lane rules out, and it is obs's scope, not hq's.

Lean: 1 as the default, with 2 as an explicit opt-in (`--transcripts`) only if the
research shows prompt-only search misses lookups that matter and a bounded scan is
fast enough.

## 5. Unanswered questions

- How many listed sessions have at least one typed-prompt line, per home and harness
  (subagent and `exec` sessions have none), and how long does a prompt search take? —
  research hq-ea0975.
- What does a bounded transcript scan cost on this host, and do three real lookups
  succeed under 1, under 2, or only under 2? — hq-ea0975.
- Picker `/` versus a `search` subcommand: settled after the research, by the user if
  the measured costs leave both viable.

## 6. Proposed decomposition

- hq-ea0975 (research, under lane hq-65f661) — wakes hq-3558a1, which depends on it.
- hq-3558a1 no longer depends on obs-914269: obs holds no text, so its coverage work
  does not gate search.
