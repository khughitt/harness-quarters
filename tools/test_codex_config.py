"""Tracked Codex config values that other projects' rules depend on."""
from pathlib import Path
import tomllib

CONFIG = Path(__file__).resolve().parents[1] / 'harnesses/codex/config.toml'


def test_background_terminal_wait_reaches_one_hour():
    # lore rule 369c0028 asks a Codex controller for one write_stdin with
    # yield_time_ms 3600000; this setting caps that wait (default 300000 ms).
    # hq fact long-shell-wait (codex 0.169.0) records the probe.
    # Codex wants a u64: a float such as 3600000.0 compares equal in Python but
    # stops Codex loading its config.
    value = tomllib.loads(CONFIG.read_text())['background_terminal_max_timeout']
    assert type(value) is int and value == 3600000
