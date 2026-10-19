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
    tools/harness-links {{args}}

# Exit non-zero when this host's home links drift from links.toml.
link-check:
    tools/harness-links --check

# The fact file's check, then the agents/bin, .githooks and tools tests.
test:
    tools/harness-facts check
    python3 -m pytest agents/bin -q
    uv run -q --with pytest pytest .githooks tools -q

# Install the pinned pi (pi/package.json and its lock) under ~/.local/share/pi/<version>,
# outside the synced checkout; pi/bin/pi runs it. pi needs no lifecycle scripts (its README).
# Rerun the pi probes after a version change.
pi-install:
    #!/usr/bin/env bash
    set -euo pipefail
    version=$(node -p "require('./pi/package.json').dependencies['@earendil-works/pi-coding-agent']")
    dest="${PI_INSTALL_ROOT:-$HOME/.local/share/pi}/$version"
    mkdir -p "$dest"
    cp pi/package.json pi/package-lock.json "$dest/"
    npm ci --prefix "$dest" --ignore-scripts --no-fund --no-audit

# Install the pinned relay outside the synced checkout; relay/bin/relay runs it.
relay-install:
    #!/usr/bin/env bash
    set -euo pipefail
    version=$(/usr/bin/node -p "require('./relay/package.json').dependencies.relay.split('#')[1]")
    dest="${RELAY_INSTALL_ROOT:-$HOME/.local/share/relay}/$version"
    mkdir -p "$dest"
    cp relay/package.json relay/package-lock.json "$dest/"
    npm ci --prefix "$dest" --ignore-scripts --no-fund --no-audit

# Validate and test each Claude Code mod under claude/mods (needs the claude CLI).
mods:
    for mod in claude/mods/*/; do claude plugin validate "$mod" && claude plugin test "$mod" || exit 1; done
