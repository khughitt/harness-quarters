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

# The fact file's check, then the agents/bin, .githooks and tools tests. The two relay
# cutover files run on parallel workers; their test that signals its own process while it
# masks the signal runs alone, since another worker thread may take a process signal.
test:
    tools/harness-facts check
    python3 -m pytest agents/bin -q
    uv run -q --with pytest pytest .githooks tools -q --ignore=tools/test_relay_cutover_bootstrap.py --ignore=tools/test_relay_cutover_transport.py
    uv run -q --with pytest --with pytest-xdist pytest tools/test_relay_cutover_bootstrap.py tools/test_relay_cutover_transport.py -q -n auto -k 'not test_signal_while_recording_start_cancels'
    uv run -q --with pytest pytest tools/test_relay_cutover_transport.py -q -k test_signal_while_recording_start_cancels

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

# Install the pinned relay outside the synced checkout; relay/bin/relay runs it. The system
# npm installs it, as the system node runs it: a version manager's npm on PATH may predate
# npm's fix for --allow-git=root under npm ci (npm 11.9 refuses the direct Git dependency).
relay-install:
    #!/usr/bin/env bash
    set -euo pipefail
    version=$(/usr/bin/node -p "require('./relay/package.json').dependencies.relay.split('#')[1]")
    dest="${RELAY_INSTALL_ROOT:-$HOME/.local/share/relay}/$version"
    mkdir -p "$dest"
    cp relay/package.json relay/package-lock.json "$dest/"
    "${RELAY_NPM:-/usr/bin/npm}" ci --prefix "$dest" --ignore-scripts --allow-git=root --no-fund --no-audit

# Render the host subscriber config; FORCE=1 permits replacing different content.
relay-subscribers:
    #!/usr/bin/env bash
    set -euo pipefail
    umask 077
    rendered=$(mktemp)
    trap 'rm -f "$rendered"' EXIT
    sed "s|@HOME@|$HOME|g" relay/subscribers.template.json > "$rendered"
    dest="$HOME/.config/relay/subscribers.json"
    if [[ -e "$dest" ]] && ! cmp -s "$rendered" "$dest" && [[ "${FORCE:-0}" != 1 ]]; then
        echo "refusing to overwrite $dest with different content; rerun with FORCE=1" >&2
        exit 1
    fi
    install -d -m 700 "$HOME/.config/relay"
    install -m 600 "$rendered" "$dest"

# Validate and test each Claude Code mod under claude/mods (needs the claude CLI).
mods:
    for mod in claude/mods/*/; do claude plugin validate "$mod" && claude plugin test "$mod" || exit 1; done
