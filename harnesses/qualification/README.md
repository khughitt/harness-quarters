# Relay qualification records

Store the schema-1 HookQualification JSON for each qualified harness version,
session mode, platform, runtime commit and subscriber-file digest here. Use the
record from relay-d487c1 and cite its source repository and commit when adding
it. Keep relay's evidence fields intact. Name the files in the policy's
`records` list in the hook route table. The record names are relative to this
directory.

A binding needs passing records for both `interactive` and `non-interactive`
at the same harness version. Relay checks every role selected by the complete
subscriber configuration at the binding's outer timeout. The JSON fixture in
the relay package illustrates the schema. Today's `existing` bindings cite
their original grant and owner.

Records here:

- `claude-code-2.1.331-interactive-v0.5.0-19b427ac306a.json` and
  `claude-code-2.1.331-non-interactive-v0.5.0-19b427ac306a.json`: relay
  `7406232000fa3cc79dffd82e66c7bb2ad1f63b96`,
  `docs/evidence/hook-transport/route-status.json`. The source entries are the
  Claude Code 2.1.331 `interactive` and `print` entries for donor-2 (configDigest
  `19b427ac306aa5eb1dfeff24a00c89d28db4eef76c14aa106e02c8e7d01eb14b`, relay v0.5.0
  `1f1c28da62e7867caf3acaddf16ba13079a37e85`). Each route's `roles` map expands
  to one row per role with the route's event, `outerMs` and check objects copied
  unchanged. Relay's `print` mode is hq's `non-interactive` (`claude -p`).
