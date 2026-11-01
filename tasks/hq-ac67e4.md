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
updated: 2026-11-01T22:09:58Z
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
