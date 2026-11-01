---
id: hq-ac67e4
title: Converge agy ~/.gemini/config links on europa and reconcile ~/.gemini/antigravity-cli/settings.json live-state drift across titan and europa
status: doing
priority: 2
size: s
complexity: mid
process: direct
owner: feat/hq-ac67e4-agy-bootstrap
created: 2026-11-01T22:03:31Z
updated: 2026-11-01T22:43:11Z
started: 2026-11-01T22:06:20Z
depends: []
tags: [hooks]
source: hq-8af61d
agent: agy
origin: user
---

Why: During hq-8af61d rollout across titan and europa, two agy home-link and settings hygiene issues surfaced across ~/.gemini/antigravity-cli/settings.json and ~/.gemini/config/*:
1. Bootstrap deadlock on europa (`just link` / `just link --apply`): europa already has real directories `~/.gemini/antigravity-cli` and `~/.gemini/config`, with an initial regular file at `~/.gemini/antigravity-cli/settings.json` (`{"seasonalThemesOptIn": "halloween-2026", "showFeedbackSurvey": false, "trustedWorkspaces": ["/home/keith/d/dotfiles"]}`) written when agy first ran before `just link --apply`. Because `[harness.agy]` in `links.toml` requires `anchors = ["~/.gemini/config/hooks.json", "~/.gemini/config/skills.json"]` and `tools/harness-links` checks `is_anchored` before creating planned `[harness.agy-config]` links (`create ~/.gemini/config/{AGENTS.md,hooks.json,skills.json}`), `just link` and `just link --apply` refuse `~/.gemini/antigravity-cli/settings.json` (`a real file is there`) and leave `~/.gemini/config/*` unlinked on europa (so agy on europa does not load `AGENTS.md`, `agy/hooks.json`, or `agy/skills.json`).
2. Cross-host `agy/settings.json` live-state drift on titan and europa: on titan, agy rewrites `statusLine.enabled: false` into `agy/settings.json` (leaving `M agy/settings.json` dirty on main), while on europa agy wrote `seasonalThemesOptIn` and `showFeedbackSurvey` alongside host-local `trustedWorkspaces`. `[harnesses.agy.live_state]` in `harnesses.toml` currently strips only `["model", "effort", "effortByBase", "trustedWorkspaces"]`, so adopting europa's initial `settings.json` or running agy on titan/europa dirties tracked `agy/settings.json` unless host/UI keys are classified (either tracked intentionally or added to `harnesses.toml` `clean_keys` / `unrestored_keys` / `pick_units` and reconciled with `hq-e77206` for `statusLine`).

Done:
- `tools/harness-links` / `links.toml` and `.githooks/live-picks` cleanly onboard a second host where agy created an initial `~/.gemini/antigravity-cli/settings.json` before `~/.gemini/config/{AGENTS.md,hooks.json,skills.json}` were linked, without weakening foreign-file refusal when `[harness.agy-config]` itself has foreign conflicts.
- `harnesses.toml` `[harnesses.agy.live_state]` and `agy/settings.json` classify or reconcile `seasonalThemesOptIn`, `showFeedbackSurvey`, and `statusLine` (coordinating with `hq-e77206` if `statusLine` is owned there) so normal agy runs and adoption across titan and europa leave `git status` clean.
- After tests (`just test`) pass and home-link rollout is approved, `just link --apply` and `just link-check` converge on both titan and europa (`ok` across `~/.gemini/antigravity-cli/settings.json` and `~/.gemini/config/{AGENTS.md,hooks.json,skills.json}`).

Where: links.toml, harnesses.toml, agy/settings.json, tools/harness-links, tools/test_harness_links.py, .githooks/harness_state.py, .githooks/live-picks, .githooks/test_live_picks.py.

## Notes

- 2026-11-01T22:03:31Z (add): created
  provenance: {"origin":"user"}
- 2026-11-01T22:04:00Z (main): concerns: hq-8af61d extension — onboard europa ~/.gemini/config/* links past unanchored initial settings.json and classify agy/settings.json live-state drift across titan and europa
- 2026-11-01T22:06:20Z (main): started
  provenance: {"harness_session":"claude-code:6dcbd897-967a-4e20-a982-604b9c48faaf","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-01T22:06:38Z (main): trial: flow-trial-1 — enrolled — flow off
- 2026-11-01T22:06:40Z (main): arm: flow-trial-1 — unit tack-ac67e4 — flow off
- 2026-11-01T22:09:58Z (feat/hq-ac67e4-agy-bootstrap): resumed
  provenance: {"harness_session":"claude-code:6dcbd897-967a-4e20-a982-604b9c48faaf","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-01T22:31:04Z (feat/hq-ac67e4-agy-bootstrap): baseline: just test in .worktrees/hq-ac67e4 — 2068 passed (agents/bin 268, .githooks+tools 1408, relay-cutover 391, signal cancel 1); harness-facts check ok
- 2026-11-01T22:43:11Z (feat/hq-ac67e4-agy-bootstrap): Decisions: (1) bootstrap: new live-picks first-run, run by harness-links --apply before any link when every anchor would be created; keeps agy/settings.json as base, union for list picks, refuses non-live keys the tracked config lacks. Why: anchored adopt_detached takes the detached file as base and would drop permissions/allowNonWorkspaceAccess/statusLine from a first-run file. Rejected: two-pass apply (create anchors, then sync) for the same reason; accepting repoint anchors (foreign/dangling link) — kept refusing. Cost if wrong: a foreign-link anchor still deadlocks until removed by hand. (2) classification: agy sets these from its UI (binary symbols SetSeasonalThemes, SetShowFeedbackSurveyOverride, SetStatusLineConfig). seasonalThemesOptIn ('halloween-2026', seasonal churn) -> clean key + own pick unit; showFeedbackSurvey false -> tracked. Why: stable preference vs season-keyed host value. Cost: a showFeedbackSurvey toggle shows as a tracked diff. (3) statusLine.enabled false (titan agy UI write 2026-11-01 16:58:53 -0500) committed on main adaa54d6 rather than reverted; Why: a recorded UI action on a tracked key; hq-e77206 owns the command and must set enabled when it points at familiar. Rejected: revert to true.
