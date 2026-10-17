# Agent notifications during internal work

Investigation for hq-b339a9, 2026-10-15. The Codex mitigation was merged and
activated in the personal config after user approval on 2026-10-15. The task
remains open for the Claude shell case. The live Codex acceptance check passed
on 2026-10-16 (see Live Codex acceptance).

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

The change allows `approval-requested`, `plan-mode-prompt`, and
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
control this terminal path. Neither is part of this mitigation.

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

The user approved activation and the change was merged into main, which is
linked into the live personal harness home. The link target and the on-disk
allowlist were verified after the merge. Existing sessions may need restarting.

### Live Codex acceptance

On 2026-10-16 the installed Codex CLI was 0.163.0, while the shared background
server still ran 0.162.1. The notification filter and its transport are in the
TUI client. Between the two tags they differ only in the `Notification` enum's
Rust visibility, so the earlier filter check still applies.

Three fresh TUI sessions ran in a private detached tmux server, each under
`script` to record raw terminal output. A process listing at the first launch
showed no Kitty or niri window among its ancestors, so Familiar could not
target one. `KITTY_WINDOW_ID` was set so the TUI detected Kitty. The terminal
starts focused, so each check first wrote a focus-lost sequence (`CSI O`) into
the pane. `script` records output only, so these injected focus sequences are
absent from the recordings.

The first session passed `-c` overrides, which forced embedded mode instead of
the shared server; the overrides apply on top of the live config. The others
ran plain `codex` against the live personal home. The first two sessions unset
`TMUX` but not `TMUX_PANE`, so the TUI still detected tmux and wrapped each
OSC 9 in a tmux DCS passthrough. The third also unset `TMUX_PANE` and received
the bare OSC 9 that Kitty gets. Results:

| Case | Session | Notification payload |
| --- | --- | --- |
| Ordinary completion, unfocused | 1 and 2 | none |
| `request_user_input_async`, unfocused | 1 (DCS-wrapped) | `Question: hq1ec500 probe` |
| `request_user_input` in plan mode, unfocused | 2 (DCS-wrapped) | `Plan mode prompt: hq1ec500 sync` |
| Plan implementation prompt, unfocused | 2 (DCS-wrapped) | `Plan mode prompt: Implement this plan?` |
| `request_user_input_async`, focused (`CSI I`) | 2 | none |
| `request_user_input_async`, unfocused | 3 (bare OSC 9) | `Question: hq1ec500 plain` |

Each silent ordinary completion is followed in the same session by a
notification, with no focus-gained sequence injected in between. The private
server ran without `focus-events`, so nothing else changed the focus flag. The
async-question turn in session 1 also completed without a second notification.
The focused question was registered: it appeared on screen and the state went
to blocked.

The actual TUI therefore loads the filter from the live config. Explicit
questions and plan prompts still notify when the terminal is unfocused.
Ordinary completion does not. A focused terminal raises no desktop
notification, although the TUI still updates the terminal title and its state
sequence. Every BEL in the recordings ends an OSC sequence; none is bare.

Exec and edit approvals are unreachable under the personal
`approval_policy = "never"` and were not manufactured. An MCP elicitation,
which its server initiates, was not exercised. All three variants map to
`approval-requested`, which the allowlist keeps; that mapping is unchanged in
0.163.0. Delivery from Kitty to the desktop was not exercised because it would
take the live desktop. The raw recordings were throwaway files in the host's
temporary directory.

### Remaining work

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
