# Harness live state

Type: data model, guide; document types 1. Harness manifest schema 1 and the
currently unversioned pick/trust records separate mutable selections from tracked
configuration. [Home links](home-links.md) describes ownership and adoption;
[capabilities](harness-capabilities.md) covers observed picker behavior.

## Required Git filter

just setup configures these repository-local keys:

| Key | Required value |
| --- | --- |
| core.hooksPath | .githooks |
| filter.harness-state.clean | .githooks/harness-state-clean %f |
| filter.harness-state.required | true |
| filter.harness-state.smudge | cat |

The identity smudge is required even though it changes no bytes. Clean strips only
fields declared for the matched path; a broken manifest/module or invalid JSON/TOML
fails closed. Never disable required to get past a Git refusal. Restore/resolve the
manifest or fix the invalid config; during an unresolved merge use normal conflict
resolution or abort rather than checking out an unmerged path blindly.

Pre-commit validates the staged manifest/attributes/config export and the shared
repository filter configuration. If a blob was staged without the filter, use
`git add --renormalize <path>` after setup. Do not stash live settings to clear a
stat-only modified marker: that can drop the selection until restoration.

## harnesses.toml schema 1

The root has schema=1 and a nonempty harnesses table. Harness names are canonical
slugs; a bare harness table declares a runtime without a managed live-state config.
Each live_state entry defines:

| Field | Meaning and constraints |
| --- | --- |
| config | Concrete checkout-relative, directory-qualified file outside local/ |
| filter_glob | Directory-qualified glob routed by .gitattributes; only one * per segment, no ? or character classes |
| format | json or toml |
| clean_keys | JSON key names, or TOML records with exactly table regex and nonempty keys list |
| clean_tables | TOML-only list of table regexes to strip |
| trust_table | Optional TOML-only regex for Codex project trust |
| picks_record | Optional local/ record path; its absence makes the entry filter-only |
| pick_units | Non-overlapping nonempty groups of picker-owned keys, saved/restored as units |
| unrestored_keys | Cleaned keys deliberately excluded from picker restoration |

Paths cannot contain empty, parent/current-directory or absolute components;
concrete paths cannot contain wildcard syntax. Duplicate/overlapping config routes,
invalid regexes, malformed key lists, unknown manifest fields, mismatched formats
and invalid picker ownership are refused. Attributes must route exactly the declared
filter globs to harness-state. The validator in .githooks/harness_state.py owns the
full checks; staged-tree validation reads the staged files, not just working copies.

## Current stripped selections

| Runtime | Removed from committed config | Preservation |
| --- | --- | --- |
| Claude Code | model, modelSettings, effortLevel | Model and effort are separate units in local/live-picks.json |
| Codex | model, model_reasoning_effort; projects tables; selected TUI/marketplace bookkeeping | Model/effort unit in local/live-picks.json; trust separately in local/codex/trust.toml |
| agy | model, effort, effortByBase, trustedWorkspaces, seasonalThemesOptIn | Separate units in local/live-picks-agy.json |
| pi | defaultProvider, defaultModel, defaultThinkingLevel, deviceId, trackingId | Model/provider and thinking units in local/live-picks-pi.json; installation IDs are not restored |

Codex bookkeeping comprises tui.screen_reader_detection_done,
tui.model_availability_nux, and last_updated/last_revision in matching marketplace
tables. Other harness-written configuration remains tracked. A fresh clone starts
with harness defaults and no saved trust; private work settings are separate inputs.

## Saved pick records

Each JSON record maps an owned config path to one of these exact shapes:

- `{"state":"default"}`: explicit reset; no other fields.
- `{"state":"set","values":{...}}`: nonempty JSON selection using declared pick keys.
- `{"state":"set","lines":[...]}`: nonempty one-line top-level TOML key assignments,
  with each owned key at most once, before any table.

Unknown owned-file entries, malformed JSON, unknown fields and invalid selections
refuse that record independently. Machine-owned records are rewritten whole only
when changed; hand-added commentary is not retained. A missing record starts empty.
Capture changes only units actually held by the live config. Restore fills a unit
only when every one of its fields is absent, preserving newer live selections.
Absence alone is ambiguous: only forget records a deliberate default.

## Operations and recovery

From main, `.githooks/live-picks` provides capture, restore, sync, first-run,
forget CONFIG and hook NAME. `.githooks/codex-trust` captures/restores trust and
forgets a named path explicitly. Both serialize config/record changes through
local/harness-state.lock. Writes preserve file privacy; Codex restoration removes
group/other access from its live config.

Stop refresh captures picks/trust and restages filtered-empty stat changes. Git
post-checkout/post-merge/post-rewrite restore from saved state on main; worktree
copies are not live. Operations skipped by Git hooks recover at the next turn end.
A selection made since the last capture may be lost by an earlier Git rewrite.
Pi's extension also captures after picker events, at settle and shutdown; shutdown
waits for bounded refresh processes and exit cleanup kills owned refresh groups.

An invalid record is never silently overwritten; repair it or explicitly discard
it knowing its selections will be forgotten. Hooks warn without turning a completed
Git checkout into failure. Non-hook operations refuse linked worktrees. Agy atomic
settings saves are adopted only with the anchors/first-run rules in home-links;
never treat an arbitrary real settings file as owned.
