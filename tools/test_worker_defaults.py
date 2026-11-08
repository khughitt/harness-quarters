"""Every personal harness home starts its tool shell with small runner worker counts.

A runner started outside host-budget (`pytest -n auto`, `cargo build`, nextest, Go tests)
otherwise sizes itself from the full CPU count. host-budget `run` overwrites these same
variables with its grant, so a budgeted job still gets its full width. The library thread
variables (OMP_NUM_THREADS and kin) are left to the host: a host may pin them to 1, and
`nproc` honours OMP_NUM_THREADS.
"""
import json
import os
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = {
    "PYTEST_XDIST_AUTO_NUM_WORKERS": "4",
    "CARGO_BUILD_JOBS": "4",
    "RUST_TEST_THREADS": "4",
    "NEXTEST_TEST_THREADS": "4",
    "GOMAXPROCS": "4",
}
LIBRARY_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS", "NUMBA_NUM_THREADS", "RAYON_NUM_THREADS",
                "POLARS_MAX_THREADS")
# host-budget's own grant markers: setting them would make an unbudgeted shell look budgeted.
GRANT_VARS = ("OPS_BUDGET", "OPS_WORKERS")


def worker_view(env):
    return {name: env[name] for name in DEFAULTS if name in env}


def assert_leaves_alone(env):
    assert not [name for name in (*LIBRARY_VARS, *GRANT_VARS) if name in env]


def test_claude_settings_set_the_defaults():
    env = json.loads((ROOT / "harnesses/claude" / "settings.json").read_text())["env"]
    assert worker_view(env) == DEFAULTS
    assert_leaves_alone(env)


def test_codex_shell_policy_sets_the_defaults():
    config = tomllib.loads((ROOT / "harnesses/codex" / "config.toml").read_text())
    env = config["shell_environment_policy"]["set"]
    assert worker_view(env) == DEFAULTS
    assert_leaves_alone(env)


VERSION = json.loads((ROOT / "harnesses/pi" / "package.json").read_text())["dependencies"]["@earendil-works/pi-coding-agent"]
FAKE = "#!/usr/bin/env bash\nenv\n"


@pytest.fixture
def installed(tmp_path):
    root = tmp_path / "install"
    bin_dir = root / VERSION / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "pi").write_text(FAKE)
    (bin_dir / "pi").chmod(0o755)
    (root / VERSION / "package-lock.json").write_bytes((ROOT / "harnesses/pi" / "package-lock.json").read_bytes())
    home = tmp_path / "home"
    home.mkdir()
    return {"PATH": os.environ["PATH"], "HOME": str(home), "PI_INSTALL_ROOT": str(root)}


def pi_env(env):
    result = subprocess.run([str(ROOT / "harnesses/pi" / "bin" / "pi")], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)


def test_pi_launcher_sets_the_defaults(installed):
    env = pi_env(installed)
    assert worker_view(env) == DEFAULTS
    assert_leaves_alone(env)


def test_pi_launcher_keeps_a_value_it_was_given(installed):
    env = pi_env({**installed, "CARGO_BUILD_JOBS": "12"})
    assert env["CARGO_BUILD_JOBS"] == "12"
    assert worker_view(env) == {**DEFAULTS, "CARGO_BUILD_JOBS": "12"}


@pytest.fixture
def agy_installed(tmp_path):
    home = tmp_path / "home"
    binary = home / ".local" / "share" / "agy" / "agy"
    binary.parent.mkdir(parents=True)
    binary.write_text(FAKE)
    binary.chmod(0o755)
    return {"PATH": os.environ["PATH"], "HOME": str(home), "AGY_BIN": str(binary)}


def agy_env(env, *args):
    result = subprocess.run([str(ROOT / "harnesses/agy" / "bin" / "agy"), *args], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)


def test_agy_launcher_sets_the_defaults(agy_installed):
    manifest = tomllib.loads((ROOT / "links.toml").read_text())
    assert manifest["required"]["~/.local/bin/agy"] == "harnesses/agy/bin/agy"
    env = agy_env(agy_installed)
    assert worker_view(env) == DEFAULTS
    assert_leaves_alone(env)
    default_path_env = agy_env({k: v for k, v in agy_installed.items() if k != "AGY_BIN"})
    assert worker_view(default_path_env) == DEFAULTS
    assert_leaves_alone(default_path_env)


def test_agy_launcher_keeps_a_value_it_was_given(agy_installed):
    env = agy_env({**agy_installed, "CARGO_BUILD_JOBS": "12"})
    assert env["CARGO_BUILD_JOBS"] == "12"
    assert worker_view(env) == {**DEFAULTS, "CARGO_BUILD_JOBS": "12"}


def test_agy_launcher_yields_to_host_budget_override(agy_installed):
    base = agy_env(agy_installed)
    assert worker_view(base) == DEFAULTS
    assert_leaves_alone(base)
    grant = {
        **{name: "8" for name in DEFAULTS},
        **{name: "1" for name in LIBRARY_VARS},
        "OPS_BUDGET": "8",
        "OPS_WORKERS": "8",
    }
    for merged in ({**base, **grant}, agy_env({**agy_installed, **grant})):
        assert worker_view(merged) == {name: "8" for name in DEFAULTS}
        assert merged["OPS_BUDGET"] == "8"
        assert merged["OPS_WORKERS"] == "8"
        assert {name: merged[name] for name in LIBRARY_VARS} == {name: "1" for name in LIBRARY_VARS}


def test_agy_launcher_fails_closed_when_binary_missing(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    missing = tmp_path / "missing"
    for env, expected_path in (
        ({"PATH": os.environ["PATH"], "HOME": str(home), "AGY_BIN": str(missing)}, missing),
        ({"PATH": os.environ["PATH"], "HOME": str(home)}, home / ".local" / "share" / "agy" / "agy"),
        ({"PATH": os.environ["PATH"], "HOME": str(home), "AGY_BIN": str(home)}, home),
    ):
        result = subprocess.run(
            [str(ROOT / "harnesses/agy" / "bin" / "agy")],
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 127
        assert str(expected_path) in result.stderr

