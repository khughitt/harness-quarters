---
id: tack-589cdd
title: Strip model and effort keys from the tracked harness configs with a git clean filter
status: done
priority: "2"
size: s
complexity: mid
process: direct
owner: main
created: 2026-09-21T11:51:58Z
updated: 2026-09-22T00:23:45Z
started: 2026-09-22T00:19:58Z
completed: 2026-09-22T00:23:45Z
depends: []
tags: [hooks]
model: "claude-opus-5[1m]"
agent: "claude-code/claude-opus-5[1m]"
---

Why: the harness homes symlink to the tracked files (`~/.claude/settings.json` -> `claude/settings.json`, `~/.codex/config.toml` -> `codex/config.toml`, and the `.work.` variants), so every model or reasoning-effort switch made from inside a session (`/model`, `/effort`) writes straight into the checkout. Observed 2026-09-21: main carried a dropped `model` line and a `modelSettings.claude-opus-5.effortLevel` in the Claude files and a `model`/`model_reasoning_effort` flip in `codex/config.toml`, mixed with real changes (plugin toggles, a new marketplace, hook trust hashes), and the dirty files had to be stashed around a fast-forward merge of an unrelated task. The noise hides real uncommitted work and makes clean-checkout checks lie.

Checked 2026-09-21, both harness-native layers are closed: Claude Code reads no user-level `settings.local.json` and `/model` always persists to the user `settings.json` (`--settings`/`--model` are per-session and never written; a read-only file makes a switch session-only, which also blocks legitimate writes such as plugin toggles). Codex has `$CODEX_HOME/<name>.config.toml` profiles and project `.codex/config.toml` but no include mechanism, and its picker rewrites the top-level `model` and `model_reasoning_effort` keys in `config.toml`.

Decision: model and effort are session state; everything else the harness writes (`enabledPlugins`, `extraKnownMarketplaces`, `[hooks.state.*] trusted_hash`) is configuration and keeps being committed. Keep the symlinks (the profiles plan relies on a change being live in every home once it is on main) and strip the state keys at staging with a git clean filter rather than breaking the link for a copy-and-sync step (loses immediacy, adds a step to forget) or a read-only tracked file (blocks the config writes too).

Done: `.gitattributes` routes `claude/settings*.json` and `codex/config*.toml` through a `harness-state` clean filter (smudge is identity); the filter script lives in the repository (next to `.githooks/`) and drops `model` and `modelSettings` from the JSON (jq, 2-space indent, key order preserved) and top-level `model` / `model_reasoning_effort` lines from the TOML (only before the first table header). README's per-clone setup gains the `git config filter.harness-state.clean` line beside `core.hooksPath`. The first commit under the filter normalises the four files and lands the plugin and trust-hash changes that are pending now.

Check: switch model and effort in a Claude and a Codex session, `git status` stays clean; edit a hook entry or toggle a plugin, `git status` shows it; `git diff` never shows a `model` key; `git stash`/checkout of the file keeps the working tree's live values out of the index without losing them until the harness rewrites them. Note in README that after a checkout the harness falls back to its default model until the next pick.

## Notes

- 2026-09-22T00:19:25Z (main): scope: scoped; harness-native layering checked and closed on both sides (no user-level settings.local.json, /model writes settings.json; Codex has profiles and project config, no include), decided model+effort are state and plugin/marketplace/trust-hash writes are config, chose a git clean filter over breaking the symlink or a read-only file; todo P2 s mid direct
- 2026-09-22T00:19:58Z (main): started
  provenance: {"harness_session":"claude-code:f94bce47-700f-4fdb-8122-6f38b7f103dd","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-22T00:23:45Z (main): done
  provenance: {"harness_session":"claude-code:f94bce47-700f-4fdb-8122-6f38b7f103dd","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-22T00:23:45Z (main): Clean filter .githooks/harness-state-clean wired by .gitattributes strips model/modelSettings from claude/settings*.json and top-level model/model_reasoning_effort from codex/config*.toml at staging; README carries the per-clone git config line and the size-only git status residual (git diff is content-true, git add -u clears it, never stash the files). First filtered commit normalises the four files and lands the pending plugin, marketplace, and trust-hash changes.
  provenance: {"harness_session":"claude-code:f94bce47-700f-4fdb-8122-6f38b7f103dd","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
