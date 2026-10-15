# Agent notifications during internal work

Investigation for hq-b339a9, 2026-10-15. The prepared Codex mitigation is
not activated. The task remains open for the Claude shell case and a live
acceptance check.

## Observed paths

The installed versions are Codex CLI 0.162.1, Claude Code 2.1.296, and
Noctalia 5.2.1. The personal harness settings call Familiar directly, not
relay. Neither personal config declares an external Codex `notify` command.

All 100 entries in Noctalia's current notification history were inspected.
At that read, 98 came from Kitty and two from Firefox. The Kitty entries
comprised 63 native Claude idle messages, 31 response previews, three Codex
questions, and one shell command completion. These counts identify the
notification channels; the history contains no harness session or parent
thread id and cannot establish which individual alert was premature.
No private response text is reproduced here.

The live history is `~/.local/state/noctalia/notification_history.json`.
`~/.cache/noctalia/notifications.json` contains August history. The enabled
QML `niri-urgent-on-notification` plugin declaration under the old Noctalia
config belongs to the former shell; it is not evidence that the running
native shell executes that plugin.

### Codex

The [version-matched notification implementation][codex-notifications] sends
response previews as `agent-turn-complete`. With `tui.notifications` unset,
all notification types are enabled. In Kitty, the automatic transport is
[OSC 9][codex-transport], producing desktop notifications through Kitty.

[Upstream #16844][codex-16844] confirms that the TUI filter cannot distinguish
main-agent and subagent completions. [#52922][codex-52922] reports the related
limitation of the external `notify` command; that external command is not
configured here. Open and closed issues/PRs, the default branch's notification
module, and the latest stable release changelog were checked. The notification
module differs only in the enum's Rust visibility on the installed tag versus
the inspected default branch; no released main-only filter was found.

The prepared change allows `approval-requested`, `plan-mode-prompt`, and
`async-question` in the personal `codex/config.toml`. It suppresses all native
completion popups, including ordinary final responses. It does not infer
whether response prose needs attention. Familiar's visual status remains.
The private work config is a separate input and is not changed by this patch.

### Claude Code

The installed bundle's idle notifier sends “Claude is waiting for your input”
through Kitty's OSC 99 channel. It invokes Notification hooks and then its
native transport; Familiar's state filtering does not cancel that native send.

The [background-agent bug #93672][claude-93672] is fixed in the installed
changelog. An isolated check executed the installed idle controller and its
background-task predicate with a fake clock and output collector:

| Running work | Native idle sends after the timer |
| --- | ---: |
| Subagent (`local_agent`) | 0 |
| Workflow (`local_workflow`) | 0 |
| Shell (`local_bash`) | 1 |
| No background work | 1 |

This verifies the current agent suppression and the remaining shell case
without opening windows or emitting desktop notifications. It does not
reproduce the historical incident in a live session. The shell distinction is
discussed in [#98373][claude-98373]: a finite check and a deliberately persistent
server need different treatment, and the native idle predicate excludes both.

Disabling Claude's whole native channel would also suppress useful question
and permission notices. Changing the mobile notification toggles would not
control this terminal path. Neither is part of the prepared mitigation.

### Familiar, Kitty, and workspace attention

Familiar's `src/render/term/emit.js` emits BEL only on transitions to
`needs-input`, `needs-approval`, or `error`. Working and done do not ring.
Its Claude reducer already changes an idle prompt to idle while the last
reported background-task count is positive. That protects Familiar's BEL,
not Claude's independent OSC 99 notification.

Familiar also publishes niri signal levels and pulses for done/error through
`integrations/niri/signal.js`; those visual signals are separate from desktop
notifications. A Stop still maps to done even with background work, and the
native Familiar Stop command precedes the independent claim guard in the
declared settings. No claim is made here that this caused a particular
workspace change.

Kitty has `window_alert_on_bell` enabled by default; disabling audio does not
disable requests for window attention. Its separate command-finished notifier
is configured for unfocused commands lasting at least 600 seconds. Neither
setting identifies internal agent work. The exact historical workspace urgency
trigger remains uncorrelated; desktop history alone does not prove it.

## Verification and remaining work

The config assertion failed before the change and passed afterwards. An
isolated Rust program compiled the original installed-tag notification enum,
`type_name`, and `allowed_for` methods, using the allowlist parsed from the
modified TOML. It confirmed that completion is rejected and all three explicit
request types remain enabled, including exec/edit/MCP approval variants.
`just test` also passed: 228 agent-tool tests and 831 hook/tool tests.

The Claude check above used extracted installed code, not a reimplementation
of its timer. Its clock, task stores, and output sinks were substitutes. No
model calls, live terminal writes, host pointer changes, or desktop capture
were needed. Throwaway checks and downloaded source are under the host's
temporary directory, not runtime dependencies.

Before activation, the user must approve merging the personal Codex setting:
main is linked into the live harness home. Existing sessions may need restarting.
After activation, verify a real question and a completion in an isolated session
with captured terminal output before declaring the Codex behavior accepted.

For Claude and workspace urgency, the next agent step is to correlate a
current false alert with hook events and running background tasks. Preserve
explicit question/permission alerts and the distinction between finite checks
and persistent servers. Design a replacement only if that capture shows the
existing fix and foreground-wait rules leave a real gap; do not globally mute
Kitty or add a second notification service on the present evidence.

[codex-notifications]: https://github.com/openai/codex/blob/rust-v0.162.1/codex-rs/tui/src/chatwidget/notifications.rs
[codex-transport]: https://github.com/openai/codex/blob/rust-v0.162.1/codex-rs/tui/src/notifications/mod.rs
[codex-16844]: https://github.com/openai/codex/issues/16844
[codex-52922]: https://github.com/openai/codex/issues/52922
[claude-93672]: https://github.com/anthropics/claude-code/issues/93672
[claude-98373]: https://github.com/anthropics/claude-code/issues/98373
