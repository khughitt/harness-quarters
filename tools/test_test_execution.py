"""Exercise the actual recipe/wrapper boundary and reconcile individual suite identities."""
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
from xml.etree import ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ("agents", "hooks-tools", "relay-parallel", "relay-signal")


def executable(path, text):
    path.write_text("#!/usr/bin/env python3\n" + text)
    path.chmod(0o755)


@pytest.fixture
def world(tmp_path):
    repo = tmp_path / "checkout with 'quotes $ and *"
    repo.mkdir()
    home, binaries = tmp_path / "home", tmp_path / "bin"
    home.mkdir()
    binaries.mkdir()
    config = home / "gitconfig"
    config.write_text("")
    environment = {
        "PATH": str(binaries) + os.pathsep + os.defpath, "HOME": str(home),
        "USER": "test", "LC_ALL": "C.UTF-8", "XDG_CONFIG_HOME": str(home / ".config"),
        "GIT_CONFIG_GLOBAL": str(config), "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.com",
        "OPENAI_API_KEY": "test-invalid", "ANTHROPIC_API_KEY": "test-invalid",
        "TT_LOG": str(tmp_path / "timing.jsonl"), "MARKERS": str(tmp_path / "markers.jsonl"),
    }

    def command(*args):
        return subprocess.run(args, cwd=repo, env=environment, capture_output=True,
                              text=True, check=True).stdout.strip()

    command("git", "init", "-q")
    assert Path(command("git", "rev-parse", "--show-toplevel")) == repo.resolve()
    assert Path(command("git", "rev-parse", "--absolute-git-dir")).is_relative_to(repo.resolve())
    (repo / "tasks").mkdir()
    (repo / "tasks/.config.toml").write_text('prefix = "hq"\n')
    (repo / "tools").mkdir()
    (repo / "agents/bin").mkdir(parents=True)
    (repo / ".githooks").mkdir()
    shutil.copyfile(ROOT / "justfile", repo / "justfile")
    for name in ("tt", "test-suite", "pytest_evidence.py"):
        if (ROOT / "tools" / name).exists():
            shutil.copy2(ROOT / "tools" / name, repo / "tools" / name)
    executable(repo / "tools/harness-facts", "raise SystemExit(0)\n")
    marker = "with open(os.environ['MARKERS'], 'a') as out: out.write(json.dumps({ROW}) + '\\n')\n"
    executable(binaries / "host-budget", "import json,os,sys\n"
               + marker.replace("{ROW}", "{'kind': 'budget', 'argv': sys.argv[1:]}")
               + "assert sys.argv[1:3] == ['run', '--']\n"
               + "os.environ['PYTEST_XDIST_AUTO_NUM_WORKERS'] = '2'\n"
               + "os.environ['OPS_WORKERS'] = '2'\n"
               + "os.execvp(sys.argv[3], sys.argv[3:])\n")
    executable(binaries / "uv", "import json,os,sys\n"
               + marker.replace("{ROW}", "{'kind': 'runner', 'argv': sys.argv[1:]}")
               + "if os.environ.get('REAL_PYTEST') == '1':\n"
               + f"    os.execv({sys.executable!r}, [{sys.executable!r}, '-m', 'pytest', *sys.argv[sys.argv.index('pytest')+1:]])\n"
               + "raise SystemExit(int(os.environ.get('CHILD_STATUS', '0')))\n")
    command("git", "add", ".")
    command("git", "commit", "-q", "-m", "fixture")

    class World:
        root = repo
        env = environment

        def policy(self, enabled):
            (repo / ".tt.toml").write_text(
                f'automatic_broad = {str(enabled).lower()}\nbroad_targets = ["test", "ci-test"]\n')

        def run(self, recipe, *args, env=None):
            supplied = dict(environment)
            supplied.update(env or {})
            return subprocess.run([shutil.which("just"), "--justfile", str(repo / "justfile"),
                                   recipe, *args], cwd=repo, env=supplied,
                                  capture_output=True, text=True, timeout=90)

        def rows(self):
            path = Path(environment["TT_LOG"])
            return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

        def markers(self):
            path = Path(environment["MARKERS"])
            return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    return World()


@pytest.mark.parametrize("target", ["test", "ci-test"])
def test_off_never_requests_budget_or_runner(world, target):
    world.policy(False)
    assert world.run(target).returncode == 0
    assert world.markers() == []
    row = world.rows()[-1]
    assert row["execution"] == "skipped"
    assert all(row[key] is None for key in ("exit", "tests", "selection", "content", "slowest"))


def test_ci_off_skips_locally_and_refuses_hosted_without_force(world):
    world.policy(False)
    assert world.run("ci-test").returncode == 0
    assert world.rows()[-1]["execution"] == "skipped"
    assert world.run("ci-test", env={"GITHUB_ACTIONS": "true"}).returncode != 0
    assert world.markers() == []


@pytest.mark.parametrize("target", ["test", "ci-test"])
def test_nested_hosted_without_force_refuses(world, target):
    world.policy(False)
    with (world.root / "justfile").open("a") as out:
        out.write(f"\nnested:\n    tools/tt hook-nested -- just {target}\n")
    result = world.run("nested", env={"GITHUB_ACTIONS": "true"})
    assert result.returncode != 0
    assert "hosted verification would be skipped" in result.stderr
    assert world.markers() == []


def test_focused_args_are_literal(world):
    world.policy(False)
    args = ["a file 'with quotes' $ and *.py", "-k", 'a or "b"', "$HOME"]
    result = world.run("test-one", *args)
    assert result.returncode == 0, result.stderr
    assert [m["kind"] for m in world.markers()] == ["budget", "runner"]
    assert world.markers()[-1]["argv"][-len(args):] == args
    assert world.rows()[-1]["target"] == "test-one"
    assert world.rows()[-1]["execution"] == "ran"


def test_focused_requires_arguments(world):
    assert world.run("test-one").returncode != 0
    assert world.markers() == []


def test_full_alias_preserves_child_failure(world, tmp_path):
    world.policy(False)
    evidence = tmp_path / "failure evidence"
    result = world.run("test-full", env={"CHILD_STATUS": "17", "HQ_TEST_EVIDENCE_DIR": str(evidence)})
    assert result.returncode == 17, result.stderr
    assert [r["target"] for r in world.rows()] == ["test"]
    assert world.rows()[0]["exit"] == 17
    assert world.rows()[0]["execution_reason"] == "forced"
    assert world.markers()[0]["kind"] == "budget"


@pytest.mark.parametrize("workers", ["", "0", "-1", "auto", "1.5"])
def test_ci_requires_explicit_positive_workers(world, workers):
    world.policy(True)
    result = world.run("ci-test", env={"PYTEST_XDIST_AUTO_NUM_WORKERS": workers})
    assert result.returncode != 0
    assert world.markers() == []


def suite_module():
    path = ROOT / "tools/test-suite"
    assert path.is_file(), "suite driver is missing"
    return runpy.run_path(str(path))


def write_evidence(directory):
    directory.mkdir(exist_ok=True)
    ids = ["agents/bin/test_a.py::test_a", ".githooks/test_b.py::test_b",
           "tools/test_relay_cutover_bootstrap.py::test_c", "tools/test_relay_cutover_transport.py::test_signal"]
    (directory / "inventory.json").write_text(json.dumps({
        "nodeids": ids, "collection_problems": [], "modules": [n.split("::")[0] for n in ids]}))
    for name, nodeid in zip(REPORTS, ids):
        root = ET.Element("testsuites")
        suite = ET.SubElement(root, "testsuite")
        case = ET.SubElement(suite, "testcase", name=nodeid.split("::")[-1], classname=name, time="0.01")
        ET.SubElement(ET.SubElement(case, "properties"), "property", name="nodeid", value=nodeid)
        ET.ElementTree(root).write(directory / f"pytest-{name}.xml")
    return ids


def test_four_partitions_cover_inventory(tmp_path):
    ids = write_evidence(tmp_path)
    result = suite_module()["verify_evidence"](tmp_path)
    assert result["collected"] == result["reported"] == len(ids)
    assert result["excluded_modules"] == []
    assert result["skipped_modules"] == 0
    assert result["problems"] == []
    tt = runpy.run_path(str(ROOT / "tools/tt"))
    warnings = []
    assert len(tt["read_junit_dir"](tmp_path, ROOT, warnings.append)) == 4
    assert warnings == []


def test_equal_count_replacement_is_rejected(tmp_path):
    write_evidence(tmp_path)
    path = tmp_path / "pytest-agents.xml"
    tree = ET.parse(path)
    tree.find(".//property").set("value", "agents/bin/test_a.py::replacement")
    tree.write(path)
    with pytest.raises(ValueError, match="identit|missing|unexpected"):
        suite_module()["verify_evidence"](tmp_path)


def test_collection_skip_is_visible(tmp_path):
    write_evidence(tmp_path)
    path = tmp_path / "inventory.json"
    inventory = json.loads(path.read_text())
    inventory["collection_problems"] = [{"nodeid": "tools/test_missing.py", "outcome": "skipped", "reason": "missing zsh"}]
    path.write_text(json.dumps(inventory))
    with pytest.raises(ValueError, match="collection|missing zsh"):
        suite_module()["verify_evidence"](tmp_path)


def test_phase_errors_are_one_identity(tmp_path):
    write_evidence(tmp_path)
    path = tmp_path / "pytest-agents.xml"
    tree = ET.parse(path)
    case = tree.find(".//testcase")
    tree.find("testsuite").append(ET.fromstring(ET.tostring(case)))
    tree.write(path)
    assert suite_module()["verify_evidence"](tmp_path)["reported"] == 4


@pytest.mark.parametrize("damage", ["missing", "overlap", "empty", "malformed", "encoding"])
def test_incomplete_evidence_is_rejected(tmp_path, damage):
    write_evidence(tmp_path)
    if damage == "missing":
        (tmp_path / "pytest-relay-signal.xml").unlink()
    elif damage == "overlap":
        shutil.copyfile(tmp_path / "pytest-agents.xml", tmp_path / "pytest-relay-signal.xml")
    elif damage == "empty":
        (tmp_path / "inventory.json").write_text('{"nodeids": [], "collection_problems": [], "modules": []}')
    elif damage == "encoding":
        (tmp_path / "pytest-agents.xml").write_text('<?xml version="1.0" encoding="unknown-codec"?><testsuites/>')
    else:
        (tmp_path / "pytest-agents.xml").write_text("interrupted XML")
    with pytest.raises(ValueError):
        suite_module()["verify_evidence"](tmp_path)


def miniature_suite(world, failure=False):
    (world.root / "agents/bin/test_agent.py").write_text(
        "import pytest\n@pytest.mark.parametrize('x', [1], ids=[\"quotes ' $ * and space\"])\ndef test_agent(x): assert x == 1\n")
    (world.root / ".githooks/test_hook.py").write_text(
        "import pytest\n@pytest.mark.skip(reason='intentional fixture skip')\ndef test_hook(): pass\n")
    (world.root / "tools/test_relay_cutover_bootstrap.py").write_text("def test_parallel(): pass\n")
    (world.root / "tools/test_relay_cutover_transport.py").write_text(
        "def test_other(): pass\ndef test_signal_while_recording_start_cancels(): pass\n")
    if failure:
        (world.root / "agents/bin/test_agent.py").write_text(
            "import pytest\n@pytest.fixture\ndef broken():\n    yield\n    assert False, 'teardown failure'\n"
            "def test_agent(broken): assert False, 'call failure'\n")


@pytest.mark.parametrize("failure", [False, True])
def test_reports_survive_wrapper_exit_on_failure(world, tmp_path, failure):
    miniature_suite(world, failure)
    evidence = tmp_path / "caller-owned evidence"
    result = world.run("ci-test", env={"TT_FORCE": "1", "PYTEST_XDIST_AUTO_NUM_WORKERS": "2",
                                        "REAL_PYTEST": "1", "HQ_TEST_EVIDENCE_DIR": str(evidence)})
    assert (result.returncode != 0) == failure, result.stdout + result.stderr
    assert (evidence / "pytest-agents.xml").is_file()
    assert (evidence / "coverage.json").is_file()
    assert all(m["kind"] != "budget" for m in world.markers())
    assert "unknown runner" not in result.stderr
    if failure:
        assert not (evidence / "pytest-hooks-tools.xml").exists()
        cases = ET.parse(evidence / "pytest-agents.xml").findall(".//testcase")
        assert len(cases) == 2
        assert len({p.get("value") for c in cases for p in c.findall("properties/property") if p.get("name") == "nodeid"}) == 1
    else:
        coverage = json.loads((evidence / "coverage.json").read_text())
        assert coverage["collected"] == coverage["reported"] == 5
        assert coverage["skips"] == [{"nodeid": ".githooks/test_hook.py::test_hook", "reason": "intentional fixture skip"}]
        assert world.rows()[-1]["slowest"]
        for name in REPORTS:
            assert (evidence / f"pytest-{name}.xml").is_file()
    # A second run must not overwrite an earlier attempt.
    old = (evidence / "pytest-agents.xml").read_bytes()
    assert world.run("ci-test", env={"PYTEST_XDIST_AUTO_NUM_WORKERS": "2", "REAL_PYTEST": "1",
                                     "HQ_TEST_EVIDENCE_DIR": str(evidence)}).returncode != 0
    assert (evidence / "pytest-agents.xml").read_bytes() == old


def test_evidence_write_failure_is_not_success(world, tmp_path):
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("keep")
    result = world.run("ci-test", env={"PYTEST_XDIST_AUTO_NUM_WORKERS": "2",
                                       "HQ_TEST_EVIDENCE_DIR": str(blocked)})
    assert result.returncode != 0
    assert world.markers() == []
    assert blocked.read_text() == "keep"


def test_fixed_suite_ignores_ambient_selection(world, tmp_path):
    miniature_suite(world)
    evidence = tmp_path / "ambient selection evidence"
    result = world.run("ci-test", env={
        "PYTEST_XDIST_AUTO_NUM_WORKERS": "2", "REAL_PYTEST": "1",
        "HQ_TEST_EVIDENCE_DIR": str(evidence),
        "PYTEST_ADDOPTS": "--deselect=tools/test_relay_cutover_transport.py::test_other",
    })
    assert result.returncode == 0, result.stdout + result.stderr
    inventory = json.loads((evidence / "inventory.json").read_text())
    assert "tools/test_relay_cutover_transport.py::test_other" in inventory["nodeids"]
    coverage = json.loads((evidence / "coverage.json").read_text())
    assert coverage["collected"] == coverage["reported"] == 5


@pytest.mark.parametrize("mode,outcome", [("skip", "skipped"), ("error", "error")])
def test_plugin_records_collection_problems(world, tmp_path, mode, outcome):
    miniature_suite(world)
    source = ("import pytest\npytest.skip('fixture collection omission', allow_module_level=True)\n"
              if mode == "skip" else "raise RuntimeError('fixture collection error')\n")
    (world.root / "tools/test_missing.py").write_text(source)
    evidence = tmp_path / "collection evidence"
    result = world.run("ci-test", env={"PYTEST_XDIST_AUTO_NUM_WORKERS": "2", "REAL_PYTEST": "1",
                                        "HQ_TEST_EVIDENCE_DIR": str(evidence)})
    assert result.returncode != 0
    inventory = json.loads((evidence / "inventory.json").read_text())
    problem, = inventory["collection_problems"]
    assert problem["nodeid"] == "tools/test_missing.py"
    assert problem["outcome"] == outcome
    assert "fixture collection" in problem["reason"]
    assert json.loads((evidence / "coverage.json").read_text())["problems"]


def test_copy_failure_preserves_existing_runner_failure(tmp_path, monkeypatch):
    module = suite_module()
    evidence, timing = tmp_path / "evidence", tmp_path / "timing"
    timing.mkdir()
    monkeypatch.setenv("HQ_TEST_EVIDENCE_DIR", str(evidence))
    monkeypatch.setenv("TT_JUNIT_DIR", str(timing))
    monkeypatch.setenv("PYTEST_XDIST_AUTO_NUM_WORKERS", "2")

    def fail_suite(root, destination):
        write_evidence(destination)
        return 17

    def fail_copy(*args):
        raise OSError("fixture copy failure")

    monkeypatch.setitem(module["main"].__globals__, "run_suite", fail_suite)
    monkeypatch.setattr(module["shutil"], "copyfile", fail_copy)
    assert module["main"]([]) == 17
    assert (evidence / "pytest-agents.xml").is_file()
