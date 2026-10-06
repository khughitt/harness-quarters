# Once per clone: git hooks and the harness-state filter, and the untracked local/
# directories a public clone needs. Work configs under local/ come from another host.
setup:
    git config core.hooksPath .githooks
    git config filter.harness-state.clean '.githooks/harness-state-clean %f'
    mkdir -p local/codex/rules

# Regenerate the identity regions of README.md and AGENTS.md from identity.toml.
docs:
    python3 tools/ops-docs write

# Report the home links links.toml wants on this host; `just link --apply` converges them.
link *args:
    tools/tack-link {{args}}

# Exit non-zero when this host's home links drift from links.toml.
link-check:
    tools/tack-link --check

# The fact file's check, then the agents/bin, .githooks and tools tests.
test:
    tools/harness-facts check
    python3 -m pytest agents/bin -q
    uv run -q --with pytest pytest .githooks tools -q

# ops's test of its claim-guard constants against this checkout's fact file (interim).
facts-mirror:
    python3 .githooks/pre-commit facts-mirror

# Validate and test each Claude Code mod under claude/mods (needs the claude CLI).
mods:
    for mod in claude/mods/*/; do claude plugin validate "$mod" && claude plugin test "$mod" || exit 1; done
