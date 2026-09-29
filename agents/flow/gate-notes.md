# Gate notes: the grammar

A gate note is a task note whose text, after stripping surrounding whitespace,
begins with `gate:`. `agents/bin/flow-state` is the reference parser
(`parse_note`); `agents/flow/gate-notes.jsonl` is the corpus every parser of
these notes is tested against. The machine the states belong to is
`docs/specs/2026-09-15-flow-state-machine-design.md`.

## Kinds

`parse_note(text)` returns one of three kinds.

- `not-a-gate`: the stripped text does not begin with `gate:`. Prose that
  mentions "gate:" later in the sentence, and every `retro:` note, are this.
  A retro is `retro:` followed by text; the derivation reads it by position
  (after the verified gate), never by content.
- `gate`: `gate:` followed by optional whitespace, a run of letters that is
  one of `scoped`, `designed`, `planned`, `implementing`, `verified`, then
  optional detail. The detail is the remainder, stripped; a leading em dash
  is part of the detail, and `scoped—adopted` is `scoped` with detail
  `—adopted`.
- `malformed`: the stripped text begins with `gate:` and the rest is not a
  gate. The reasons are listed below. A malformed note is a failed attempt at
  the state it names: the derivation cancels the gates at the tail of the
  history that name that state, stops at a back edge, and forgets the attempt
  once a later well-formed gate supersedes it (functional core spec, 4.2).

## Back edges

A back edge is a gate whose detail leads with a marker matching its state:
`gate: scoped — invalidated: <why>` or `gate: implementing — reopened: <why>`
(the dash may be an em dash or one or more hyphens). The words elsewhere in a
detail, including inside finding text, mark nothing. The derivation's
cancellation for a malformed note stops at a back edge.

## Tree

The first `tree:` token in the detail, wherever it appears, names the covered
tree; its value is the run of letters and digits after the colon. A token
starts at a word boundary, so `worktree:` is not one. A `verified` gate
without one is still a gate: the derivation reports it as
`verified gate without tree:<hash>`. A first token whose value is not exactly
40 lowercase hex characters makes the note malformed; later tokens (a reopen
note names two trees) are free text.

## The verified verdict

When a `verified` detail contains `review:`, the detail after the tree token
and an optional leading dash is a list of fields separated by `;`, each
`name: value` with a non-empty value, every name exactly once, in any order,
no other names:

    checks: <free text without ";">
    review: none | <finding>, <finding>, ...
    reviewer: <label> [session:<qualified id>]

    finding := (important | minor) (addressed | deferred) <text>
    text    := one or more characters, none of them "," or ";"
    label   := human | none | <harness>/<model>    any label may carry a session
    session := <harness>:<native id>   harness is [a-z][a-z0-9-]*, the id is non-empty and has no whitespace

Whitespace separates a finding's three parts: `important addressedness …` has
no disposition and is malformed, and `important addressed` alone has empty
text.

A `verified` detail without `review:` is free text and carries no verdict.

## Malformed reasons

| Reason | Example |
| --- | --- |
| `unknown state <word>` | `gate: reviewed by someone`; `gate:` alone is `unknown state <none>` |
| `tree hash not 40 hex` | `gate: verified tree:abc` |
| `missing field <name>` | a verdict without `reviewer:`, or with `checks: ;` |
| `unknown field <name>` | `checks: a; b; review: none; reviewer: human`; a trailing `;` is `unknown field <none>` |
| `duplicate field <name>` | two `review:` fields |
| `finding without severity and disposition: <text>` | `review: minor addressed handle retries, timeouts` |
| `empty finding text` | `review: minor addressed ` |
| `important finding deferred` | `review: important deferred rename` |
| `reviewer field` | `reviewer: codex/gpt-5.6 extra words` |
| `session id` | `session:garbage`, `session:codex:` |

## Outcome notes

Two other note shapes are not gates (`not-a-gate`, corpus cases above): obs's
outcome measures read them (obs `docs/specs/2026-09-28-outcome-measures-design.md`
§4). The `verified` gate's `review:` field is a disposition record and never a round.

    review: <spec|plan|impl> round <n> — verdict: <revise|accept>; findings: <label> <count>, … | none; reviewer: <harness/model | human>
    concerns: <task-id> <defect|change|extension> — <one line>

`test_outcome_notes_match_their_grammar` in `agents/bin/test_flow_state.py` checks
every corpus text that begins with either word against these shapes.
