---
id: hq-b7b9ac
title: "cli-pane /m: pick a thought from a typeahead when no ID is given"
status: idea
priority: 2
created: 2026-10-09T14:46:50Z
updated: 2026-10-10T13:27:26Z
depends: []
parent: hq-65f661
tags: [claude]
source: mind6-96e1c0
---

The cli-pane mod (claude/mods/cli-pane, 38b6821) already answers `/m <ID>` by showing `mindful show <ID>` in a pane outside the conversation, as `/tas` does for tasks. Still missing from mind6-96e1c0 (source thought mindful:thought:5499887366b74519c03214ddaa3aafcc): picking the thought without knowing its ID, with its tags (and perhaps its colour) visible while picking.

Feasibility: the mod API has no dynamic argument completion for slash commands (`$.command.register` takes only a static `argumentHint`), but a pane can draw `Input` and `Select` on terminal and desktop (types: claude-code index.d.ts, `ui.select`, `onSubmit`). So `/m` with no ID (or a non-ID query) could open a pane with an input that queries `mindful --json search` as you type and a Select of results (title, alias, top tags); choosing one shows it as `/m <ID>` does today.

Open: whether the picker inserts a reference into the prompt as well as showing the thought; how colour is shown (the CLI's sprite colours already arrive as SGR, which the pane parses); and the mobile app, which draws no Input or Select yet.

## Notes

- 2026-10-10T13:27:26Z (main): scope: briefed; hq-4ba161 will verify tags/color and typeahead in the existing pane; preserve nonempty /m arguments and pane-only selection; brief: docs/notes/2026-10-10-context-discovery-brief.md
