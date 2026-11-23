"""Run the rendered SessionStart bridge with real relay and isolated notice owners."""
from dataclasses import replace
import json
from pathlib import Path
import shlex
import subprocess
import sys

import pytest

from hook_routes.render import render_candidate
from hook_routes.table import load
from test_agy_hooks import HOOK, ROOT, make_agy_checkout, notice_runtime, write_script

DELEGATES = ("lore hook profile-notice", "mindful notice session-start")


@pytest.fixture
def runtime():
    package = notice_runtime()
    assert (package / "package.json").is_file(), f"missing required SessionStart relay installation {package}"
    return package


@pytest.fixture
def notice_home(tmp_path):
    home, workspace, binaries = (tmp_path / name for name in ("home", "work space", "bin"))
    for directory in (home, workspace, binaries):
        directory.mkdir()
    (binaries / "python3").symlink_to(sys.executable)
    return home, workspace, binaries


def install_owner(notice_home, delegate, body):
    home, workspace, binaries = notice_home
    name, *args = shlex.split(delegate)
    return write_script(binaries / name, f"""import json, os, sys
from pathlib import Path
assert sys.argv[1:] == {args!r}
request = json.load(sys.stdin)
assert request['schema'] == 2 and request['type'] == 'event' and request['subscriber']
event = request['event']
assert event['kind'] == 'session-start' and event['nativeEvent'] == 'SessionStart' and event['harness'] == 'agy'
assert event['cwd'] == {str(workspace)!r} and Path.cwd() == Path(event['cwd'])
assert event['private']['transcriptPath'] == {{'status': 'valid', 'value': {str(workspace / 'session.jsonl')!r}}}
assert request['registry'] == {{'status': 'not-requested'}}
assert 'CLAUDE_ENV_FILE' not in os.environ
with (Path.home() / 'calls').open('a') as log:
    print({name!r}, file=log)
{body}
""")


def run_bridge(notice_home, runtime, *, raw=None, argv=None):
    home, workspace, binaries = notice_home
    if argv is None:
        argv = [HOOK, "SessionStart", "--runtime", runtime]
        for delegate in DELEGATES:
            argv.extend(["--delegate", delegate])
    if raw is None:
        raw = json.dumps(dict(conversationId="session-1", workspacePaths=[str(workspace)],
                              transcriptPath=str(workspace / "session.jsonl"))).encode()
    return subprocess.run(argv, input=raw, cwd=home,
                          env={"PATH": str(binaries), "HOME": str(home),
                               "CLAUDE_ENV_FILE": str(home / "unexpected")},
                          capture_output=True, timeout=30)


def invoke(notice_home, runtime, **options):
    result = run_bridge(notice_home, runtime, **options)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def message(reply):
    [step] = reply["injectSteps"]
    return step["systemMessage"]["systemMessage"]


def render_session_start(tmp_path, runtime, home, delegates):
    table = load(ROOT / "harnesses/hook-routes.toml")
    agy = table.homes["agy"]
    index = next(i for i, b in enumerate(agy.bindings) if b.event == "SessionStart" and
                 any("claude-profile" in line.policies for line in b.lines))
    table.runtimes["v0.6.0"] = replace(table.runtimes["v0.5.0"], script=str(runtime / "bin/relay.js"),
                                       commit="9078727105f06b4a17ccbf177821806d7eed93be")
    candidate = tmp_path / "bridge.toml"
    candidate.write_text(f'''[[moves]]
home = "agy"
binding = {index}
[[moves.lines]]
policies = ["claude-profile", "capture-notice", "agy-healing"]
runtime = "v0.6.0"
delegates = {json.dumps([shlex.split(command) for command in delegates])}
command = {json.dumps(shlex.quote(str(HOOK)))}
''' + "".join(f'[moves.lines.states.{name}]\nstate = "bridge"\nevidence = "fixture"\n'
              for name in ("claude-profile", "capture-notice", "agy-healing")))
    image = render_candidate(table, candidate, home)
    [entry] = [e for e in json.loads(image[agy.path])["hq"]["SessionStart"] if str(HOOK) in e["command"]]
    return shlex.split(entry["command"])


def test_profile_and_capture_reach_one_inject_step_in_order(notice_home, runtime, tmp_path):
    argv = render_session_start(tmp_path, runtime, notice_home[0], DELEGATES)
    assert argv == [str(HOOK), "SessionStart", "--runtime", str(runtime),
                    "--delegate", DELEGATES[0], "--delegate", DELEGATES[1]]
    install_owner(notice_home, DELEGATES[0], """print('{"context":"profile: personal"}')""")
    install_owner(notice_home, DELEGATES[1], """print('{"context":"captures: 3"}')""")
    assert message(invoke(notice_home, runtime, argv=argv)) == "profile: personal\ncaptures: 3"
    assert (notice_home[0] / "calls").read_text().splitlines() == ["lore", "mindful"]


def test_candidate_refuses_a_repeated_notice_owner(notice_home, runtime, tmp_path):
    with pytest.raises(ValueError, match="duplicate delegate"):
        render_session_start(tmp_path, runtime, notice_home[0], (*DELEGATES, DELEGATES[1]))


def test_duplicate_cli_delegate_refused_before_owners_run(notice_home, runtime):
    for delegate in DELEGATES:
        install_owner(notice_home, delegate, "print('{}')")
    argv = [HOOK, "SessionStart", "--runtime", runtime, "--delegate", DELEGATES[0],
            "--delegate", DELEGATES[1], "--delegate", "mindful notice 'session-start'"]
    result = run_bridge(notice_home, runtime, argv=argv)
    assert result.returncode == 2 and b"duplicate delegate" in result.stderr
    assert not (notice_home[0] / "calls").exists()


def test_full_profile_keeps_capture_failure_visible(notice_home, runtime):
    install_owner(notice_home, DELEGATES[0], "print(json.dumps({'context': 'x' * 10000}))")
    install_owner(notice_home, DELEGATES[1], "sys.exit(7)")
    result = run_bridge(notice_home, runtime)
    assert result.returncode == 0 and message(json.loads(result.stdout)) == "x" * 10000
    [diagnostic] = result.stderr.decode().splitlines()
    assert "mindful" in diagnostic and "exited 7" in diagnostic


def test_empty_replies_produce_nothing(notice_home, runtime):
    for delegate in DELEGATES:
        install_owner(notice_home, delegate, "print('{}')")
    assert invoke(notice_home, runtime) == {}


@pytest.mark.parametrize("script", ["print('private malformed bytes')",
                                    """print('{"context":"private nonzero output"}'); sys.exit(7)""", None])
def test_malformed_reply_yields_diagnostic_only(notice_home, runtime, script):
    install_owner(notice_home, DELEGATES[0], "print('{}')")
    if script is not None:
        install_owner(notice_home, DELEGATES[1], script)
    output = message(invoke(notice_home, runtime))
    assert len(output.splitlines()) == 1 and "mindful" in output and "private" not in output


def test_delegate_timeout_yields_diagnostic(notice_home, runtime):
    install_owner(notice_home, DELEGATES[0], "import time\ntime.sleep(25)")
    install_owner(notice_home, DELEGATES[1], """print('{"context":"captures: 3"}')""")
    failure, capture = message(invoke(notice_home, runtime)).splitlines()
    assert failure.startswith("profile: unresolved") and "timed out" in failure
    assert capture == "captures: 3"


@pytest.mark.parametrize("raw", [b'{}', b'not-json', b'\xff'])
def test_profile_unresolved_line_kept_on_projection_failure(notice_home, runtime, raw):
    line = message(invoke(notice_home, runtime, raw=raw))
    assert line.startswith("profile: unresolved") and len(line.splitlines()) == 1
    assert not (notice_home[0] / "calls").exists()


def test_notice_exceeding_combined_limit_is_dropped_whole(notice_home, runtime):
    install_owner(notice_home, DELEGATES[0], "print(json.dumps({'context': 'x' * 9999}))")
    install_owner(notice_home, DELEGATES[1], """print('{"context":"more"}')""")
    assert message(invoke(notice_home, runtime)) == "x" * 9999


def test_detached_settings_healing_still_runs(tmp_path, runtime):
    repo, home, link, env = make_agy_checkout(tmp_path)
    detached = json.loads(link.read_bytes())
    detached["model"] = "test-pick"
    link.unlink()
    link.write_text(json.dumps(detached))
    write_script(tmp_path / "lore", f"""import json
from pathlib import Path
assert Path({str(link)!r}).is_symlink()
print(json.dumps({{"context": "profile: healed"}}))
""")
    result = subprocess.run([repo / "harnesses/agy/hook", "SessionStart", "--runtime", runtime,
                             "--delegate", DELEGATES[0]],
                            input=json.dumps({"workspacePaths": [str(repo)], "conversationId": "healing"}),
                            cwd=home, env=env,
                            text=True, capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert message(json.loads(result.stdout)) == "profile: healed"
    assert link.resolve() == repo / "harnesses/agy/settings.json"
    assert json.loads(link.read_bytes())["model"] == "test-pick"
