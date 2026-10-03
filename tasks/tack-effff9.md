---
id: tack-effff9
title: "Local slash commands /tas and /m that show CLI output in a pane, outside the conversation"
status: doing
priority: 2
size: s
complexity: mid
process: direct
owner: feat/cli-pane
created: 2026-10-03T16:34:02Z
updated: 2026-10-03T17:11:42Z
started: 2026-10-03T17:05:14Z
depends: []
tags: [hooks]
agent: claude-code/claude-opus-5-5
---

Viewing a task or a mindful thought inline today means `! tasks show <id>`, whose output enters the model's context. A Claude Code function-hook plugin (mod) can register slash commands that run on the host with no model request and show their output in a pane only.

## Commands

- `/tas <ID>` runs `TASKS_FORMAT=pretty tasks --color=always show <ID>`
- `/m <ID>` runs `mindful show <ID>`

## Approach (settled; plugin API of Claude Code 2.1.288)

- `session.start`: `$.command.register({ name, description })` for each command.
- `on('command.run', { command }, …)`: `$.process.run(argv, { env })` (no shell, so pass `TASKS_FORMAT` through `env`), store stdout (stderr on a non-zero exit) in an `atom`, `$.ui.open({ id, title, focus: true, closeOnEscape: true })`, and return `{}` without calling `next`.
- A `ui.render` hook on `{ component: 'Pane', requestId }` draws the stored output.
- Do not return `{ text }`: a command's text becomes a transcript row the model reads on the next turn, which is what this replaces. `context` likewise.
- An empty or missing ID shows a usage line in the pane, not an error row.

## Open within scope

- Whether a pane's `Text` renders ANSI SGR from `--color=always`. The bundled types do not mention ANSI. If it does not, parse the SGR sequences into styled `Text` spans, or drop `--color=always` and note why.
- Where the mod lives in this repo and how it loads: a plugin folder named in `CLAUDE_CODE_PLUGIN_DIRS` in the `env` block of `claude/settings.json` (user settings only, never project settings), or `--plugin-dir`. Keep the path free of machine-specific absolutes where the setting allows `~`.

## Done when

- `claude plugin validate` and `claude plugin test` pass on the mod, with a `*.test.ts` covering: each command runs the right argv, returns no `text`/`context`, and opens its pane; a failing CLI shows stderr.
- `tsc -p <mod>` type-checks once loaded.
- A live session shows `/tas <id>` and `/m <id>` output in a pane, and the next model turn has no trace of it.

## Notes

- 2026-10-03T17:05:14Z (main): started
  provenance: {"harness_session":"claude-code:52b56f25-e54e-4bcf-a122-738bb3c849fd","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-03T17:06:15Z (feat/cli-pane): resumed
  provenance: {"harness_session":"claude-code:52b56f25-e54e-4bcf-a122-738bb3c849fd","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-03T17:11:42Z (feat/cli-pane): Text refuses control characters, so hooks/sgr.ts parses SGR into styled Text spans (16 colors by name, 256/truecolor as hex). Mod lives at claude/mods/cli-pane, linked as ~/.claude/mods, loaded by CLAUDE_CODE_PLUGIN_DIRS=~/.claude/mods/cli-pane. Headless check: /tas made no model request and its transcript holds the command record (/tas + args, under the local-command caveat) but no output row; the record cannot be removed (slash commands bypass prompt.submit, session.append cannot refuse a row).
