# Harness quarters

Type: guide; document types 1. Hq owns harness homes, declared links, settings,
capability facts and session-state hygiene. Start with [home links](home-links.md),
[live state](live-state.md) or [sessions](sessions.md) for operational detail.

## Responsibilities

This is a personal reference configuration, wired to registered owner checkouts.
A clone can validate its manifest, facts and synthetic fixtures; it cannot recreate
private work settings or apply another person's home layout without configuration.

| Surface | Source | Consumer |
| --- | --- | --- |
| Home routing | links.toml | tools/harness-links; harness homes |
| Live configuration | harnesses.toml, .gitattributes | Git filter, pick and trust hooks |
| Capability observations | facts/capabilities.toml | tools/harness-facts and its lookup interface |
| Session discovery | tools/harness_stores/ | hq sessions, transcript archive and evidence tools |
| Native transcript evidence | tools/harness_evidence/ | standalone harness-evidence decoder; shared home discovery |
| Transcript custody | tools/session_archive/ | session-archive commands and optional user timers |
| Turn accounting | tools/turn_pause/ | lifecycle/tool hooks and hq pause diagnostics |
| Pinned runtimes | harnesses/pi/, relay/ | home launchers and installed hook images |

The shared checkout holds configuration; homes contain authentication, session
stores and other private state. The untracked local/ directory holds the private work
Codex configuration, saved picks and Codex trust. The work Claude Code settings
are tracked at harnesses/claude/work/settings.json. Setup creates directories, not secrets.

## Owner boundaries

- Lore owns instructions, profiles and general skills. Hq links directly to their
  owner, so a link assembled skills directory requires a symlink-following search.
- Tasks owns task records, claims and project/records resolution. New hq working
  documents live in its private records home, located through tasks where.
- Flows owns workflow gates. Hq does not turn an observed harness capability into
  task policy or redefine a gate.
- Relay owns event adapters and subscriber dispatch. Hq pins a runtime and wires
  hook images; native capabilities, adapter support and installed policy differ.
- Ops hosts shared guards and maintenance tools. Hostkit owns host resource
  controls; hq launchers use their declared interfaces.
- Obs indexes execution evidence and supplies archive pruning readiness. Hq's
  transcript archive is custody, not an alternative evidence index.

## Setup and checks

Run just setup in each checkout. It installs repository hooks and the required
clean/smudge filter configuration. Run just docs after identity changes; generated
README and AGENTS regions come from identity.toml and the family contract.

Use just test-one with explicit pytest arguments for changed behavior, and
just check-hygiene before committing. Automatic broad runs are disabled by the
landed policy; see [test execution](test-execution.md). A skipped suite is not a pass.

Apply home links from main only, after owner targets exist and with authorization
for the host operation. Test a worktree by its explicit executable path; never
route a live home, launcher or service into it.

## Current capability and future direction

Read observations through tools/harness-facts; an unknown entry is no capability
promise. The pi CLI and durable SDK are separate runtimes. Current session-store
adapters are Claude Code, Codex, agy and the pi CLI. Support planned for other stores must not
be inferred from an installed launcher or a design document.

Current code and live activation are separate facts. Replica support and a timer
unit do not prove a host has configured and enabled replication. Turn-pause
history covers local retained hook transitions, not every agent-initiated stop.
See [capabilities](harness-capabilities.md), [archive](session-archive.md) and
[turn accounting](turn-pause.md) for their boundaries.

## Pinned runtimes and local extensions

just pi-install installs the lock-pinned CLI and durable SDK below the executing
home's .local/share/pi/VERSION. PI_INSTALL_ROOT selects an alternate destination.
The launcher checks that install's lock against harnesses/pi/package-lock.json;
a missing install or lock mismatch refuses launch. It rejects pi self-updates;
model-catalog, extension and package updates have separate targets. Change the pin
and requalify its probes as described in [capabilities](harness-capabilities.md).
No install is performed merely by validating a clone.

Create the real .pi/agent home and apply declared links before first use. If pi
already wrote a real settings.json, preserve it and merge needed configuration
into the tracked settings before restoring declared links. Authentication, trust,
model-store and sessions stay in the home. Other configuration needs an explicit
links.toml declaration once it has content. The picker extension preserves model
and thinking selections; installation identifiers are deliberately not restored.
When restricting pi tools, include required MCP names explicitly, for example
`--tools 'read,grep,mcp__SERVER__*'`; a list of built-in names does not establish
that a direct MCP tool is reachable. Recheck the pinned runtime after upgrades.

Claude Code function-hook mods live under harnesses/claude/mods/. The home mods
link and colon-separated CLAUDE_CODE_PLUGIN_DIRS entries select the loaded folders.
A missing home link starts Claude without the mods. The cli-pane mod offers
`/tas ID` for tasks show and `/m ID` for mindful show. `/m` without an ID opens a
thought search picker; the mobile surface instead requires an explicit ID.
Search waits 200 ms after typing, serializes requests and returns at most ten hits.

Each command focuses its pane; Escape closes it and another invocation replaces
its content. Errors and output truncation are visible. Output stays out of model
context, but the slash-command invocation itself remains in the transcript.
Generated plugin types and tsconfig.json are ignored. Use just mods for plugin
validation/tests and `tsc -p harnesses/claude/mods/NAME` for a mod's type check.
