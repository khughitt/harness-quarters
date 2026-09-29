---
id: tack-cea269
title: Flatten agents/skills and serve superpowers from the pinned submodule alone
status: done
priority: "2"
size: m
complexity: mid
process: direct
owner: main
created: 2026-09-27T12:10:30Z
updated: 2026-09-27T12:55:48Z
started: 2026-09-27T12:25:09Z
completed: 2026-09-27T12:55:48Z
depends: []
parent: tack-e2ed51
tags: [skills]
model: claude-opus-5-5
agent: claude-code/claude-opus-5-5
---

Why: Codex agents misread skill paths shown as r0/agent-skills/<skill>/SKILL.md and r0/superpowers/skills/<skill>/SKILL.md, dropping or adding the middle directory; superpowers is listed twice in Codex (submodule v6.3.0 under r0, remote plugin 6.4.2 under r3), and the plugin copy's versioned path goes stale mid-session. Evidence and the rejected alternative: docs/notes/2026-09-27-path-mistakes-brief.md (Codex section, ai-929d4f).

Done:
- Every skill sits directly under agents/skills/<name>/: the seven vendored agent-skills move up out of agent-skills/; their shared references move to one directory and the ../../references/ links are rewritten to resolve from the new place; source.md keeps the origin.
- The superpowers submodule moves out of the skill root (for example agents/vendor/superpowers, updating .gitmodules) and each of its skills is linked at agents/skills/<name>; the pin is bumped to the Claude plugin's version (6.4.1 today).
- The Codex remote superpowers plugin is disabled in codex/config.toml and codex/config.work.toml, and the stale superpowers/6.3.0 allow rule in codex/rules/default.rules is replaced with the submodule path.
- agents/skills/README.md describes the flat layout and the readers (Codex, OpenCode, Crush).

Check: codex debug prompt-input in a trusted checkout lists every r0 skill as r0/<name>/SKILL.md, each superpowers skill once; a live Codex session shows no r3 superpowers root; every relative link in a moved SKILL.md resolves (a script over the tree); Crush's patch script still finds the skills; ~/.claude/skills links still resolve.

## Notes

- 2026-09-27T12:25:09Z (main): started
  provenance: {"harness_session":"claude-code:bec18fd8-1f8d-434b-9918-7301545eb86e","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-27T12:55:48Z (flatten-skills): Codex ignores [plugins.<remote>] enabled=false for remote plugins (live TUI still loaded r3 superpowers/6.4.2); per the user, uninstalled it with codex plugin remove and dropped the inert stanzas
- 2026-09-27T12:55:48Z (flatten-skills): done
  provenance: {"harness_session":"claude-code:bec18fd8-1f8d-434b-9918-7301545eb86e","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-27T12:55:48Z (flatten-skills): Flat agents/skills: 7 vendored skills moved up with references/ beside them, superpowers submodule at agents/vendor/superpowers v6.4.1 linked per skill, Codex remote superpowers plugin uninstalled, allow rule repointed. Verified: codex debug prompt-input lists 39 flat r0/<name>/SKILL.md entries once each; live TUI shows no superpowers root; every relative link in the moved SKILL.md files resolves; Crush's scan finds 28 skills; ~/.claude/skills links resolve.
  provenance: {"harness_session":"claude-code:bec18fd8-1f8d-434b-9918-7301545eb86e","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
