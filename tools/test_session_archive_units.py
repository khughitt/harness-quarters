"""The units call the tool with PATH set, on the spec's schedule, and links.toml links them."""
import configparser
import re
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
UNITS = ROOT / "systemd" / "user"
TOOL = ROOT / "tools" / "session-archive"


def unit(name):
    parser = configparser.ConfigParser(strict=False, interpolation=None, delimiters=("=",))
    parser.optionxform = str
    parser.read(UNITS / name)
    return parser


ALLOWED = ("%h/.local/bin", "/usr/local/bin", "/usr/bin", "/bin")


def paths_off_the_allowlist(text):
    """Every path a unit names outside comments that is not under an allowed directory.
    A unit that names a checkout, by any spelling, stops working when the checkout moves
    (docs/specs/2026-10-06-rename-to-hq-design.md §3.1)."""
    off = []
    for line in text.splitlines():
        if line.startswith("#"):
            continue
        for token in re.split(r"[\s=:]+", line):
            if "/" in token and not any(token == a or token.startswith(a + "/") for a in ALLOWED):
                off.append(token)
    return off


@pytest.mark.parametrize("name, command", [("capture", "capture"), ("prune", "prune")])
def test_service_runs_the_linked_tool_with_path(name, command):
    service = unit(f"session-archive-{name}.service")["Service"]
    assert service["Type"] == "oneshot"
    assert service["ExecStart"] == f"/usr/bin/python3 %h/.local/bin/session-archive {command}"
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


def test_the_tool_is_linked_onto_path():
    """The units call the tool through this link, so they never name the checkout."""
    required = tomllib.loads((ROOT / "links.toml").read_text())["required"]
    assert required["~/.local/bin/session-archive"] == "tools/session-archive"


def test_the_tool_runs_through_a_link_from_any_directory(tmp_path):
    link = tmp_path / "bin" / "session-archive"
    link.parent.mkdir()
    link.symlink_to(TOOL)
    (tmp_path / "home").mkdir()
    result = subprocess.run(["/usr/bin/python3", str(link), "status"], cwd=tmp_path, text=True,
                            capture_output=True, env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path / "home")})
    # Past argument parsing and into the package: it reads this host's configuration.
    assert result.returncode == 2, result.stderr
    assert "is not configured on this host" in result.stderr


@pytest.mark.parametrize("line", [
    "ExecStart=/usr/bin/python3 %h/d/tack/tools/session-archive capture",
    "ExecStart=/usr/bin/python3 %h/hq/tools/session-archive capture",
    "ExecStart=/usr/bin/python3 %h/Dropbox/hq/tools/session-archive capture",
    "ExecStart=/home/someone/bin/session-archive capture",
    "Documentation=file://%h/d/tack/docs/specs/x.md",
])
def test_the_allowlist_catches_a_unit_that_names_a_checkout(line):
    assert paths_off_the_allowlist(line)


def test_the_allowlist_passes_the_linked_tool_and_path():
    assert paths_off_the_allowlist("ExecStart=/usr/bin/python3 %h/.local/bin/session-archive capture\n"
                                   "Environment=PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin\n"
                                   "# Design: docs/specs/x.md, in the repository that holds this unit.\n") == []


def test_every_path_a_unit_names_is_on_the_allowlist():
    for path in sorted(UNITS.iterdir()):
        assert paths_off_the_allowlist(path.read_text()) == [], path.name
