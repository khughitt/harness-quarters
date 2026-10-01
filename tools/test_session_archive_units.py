"""The units call the tool with PATH set, on the spec's schedule, and links.toml links them."""
import configparser
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
UNITS = ROOT / "systemd" / "user"


def unit(name):
    parser = configparser.ConfigParser(strict=False, interpolation=None, delimiters=("=",))
    parser.optionxform = str
    parser.read(UNITS / name)
    return parser


@pytest.mark.parametrize("name, command", [("capture", "capture"), ("prune", "prune")])
def test_service_runs_tool_with_path(name, command):
    service = unit(f"session-archive-{name}.service")["Service"]
    assert service["Type"] == "oneshot"
    assert service["ExecStart"] == f"/usr/bin/python3 %h/d/tack/tools/session-archive {command}"
    assert service["Environment"] == "PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin"


@pytest.mark.parametrize("name, calendar", [("capture", "*-*-* 04:00:00"), ("prune", "*-*-01 05:00:00")])
def test_timer_schedule(name, calendar):
    timer = unit(f"session-archive-{name}.timer")["Timer"]
    assert timer["OnCalendar"] == calendar and timer["Persistent"] == "true"


def test_units_are_linked():
    required = tomllib.loads((ROOT / "links.toml").read_text())["required"]
    for name in ("capture", "prune"):
        for suffix in ("service", "timer"):
            filename = f"session-archive-{name}.{suffix}"
            assert required[f"~/.config/systemd/user/{filename}"] == f"systemd/user/{filename}"
