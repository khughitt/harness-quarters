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
