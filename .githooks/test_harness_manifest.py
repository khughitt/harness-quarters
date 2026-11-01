"""harnesses.toml loader, validation, .gitattributes/filter-config/tree checks and cleaners."""
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent
REPO = HOOKS.parent


def load_module():
    spec = importlib.util.spec_from_file_location("harness_state_under_test", HOOKS / "harness_state.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


hs = load_module()


def isolated_env(tmp_path):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    (tmp_path / "xdg").mkdir(exist_ok=True)
    gitconfig = tmp_path / "gitconfig"
    gitconfig.touch()
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(tmp_path / "xdg"),
        "GIT_CONFIG_GLOBAL": str(gitconfig),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def git(repo, env, *args, check=True):
    return subprocess.run(["git", "-C", str(repo), *args], env=env, text=True,
                          capture_output=True, check=check)


def init_repo(tmp_path, name="scratch"):
    env = isolated_env(tmp_path)
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], env=env, check=True)
    assert Path(git(repo, env, "rev-parse", "--show-toplevel").stdout.strip()) == repo.resolve()
    assert Path(git(repo, env, "rev-parse", "--absolute-git-dir").stdout.strip()).is_relative_to(repo.resolve())
    return repo, env


SHIPPED = (REPO / "harnesses.toml").read_text()


def manifest_from(tmp_path, text):
    path = tmp_path / "m.toml"
    path.write_bytes(text if isinstance(text, bytes) else text.encode())
    return hs.load_manifest(path)


JSON_ENTRY = '''schema = 1
[harnesses.a.live_state]
config = "a/s.json"
filter_glob = "a/s*.json"
format = "json"
clean_keys = ["m", "e", "x"]
picks_record = "local/p.json"
pick_units = [["m"], ["e"]]
unrestored_keys = ["x"]
'''

TOML_ENTRY = '''schema = 1
[harnesses.c.live_state]
config = "c/c.toml"
filter_glob = "c/c*.toml"
format = "toml"
clean_keys = [{ table = "", keys = ["m", "e"] }, { table = "tui", keys = ["n"] }]
clean_tables = ['t\\..+', 'p\\..+']
trust_table = 'p\\..+'
picks_record = "local/p.json"
pick_units = [["m", "e"]]
'''


def test_shipped_manifest_loads_and_matches_gitattributes_and_git_check_attr(tmp_path):
    manifest = hs.load_manifest()
    assert manifest.schema == 1
    assert manifest.harnesses == ("agy", "claude-code", "codex", "opencode", "pi", "pi-durable")
    assert manifest.by_harness["opencode"] is None and manifest.by_harness["pi-durable"] is None
    expected = {
        "agy": (("model", "effort", "effortByBase", "trustedWorkspaces"), ()),
        "claude-code": (("model", "modelSettings", "effortLevel"), ()),
        "codex": (("model", "model_reasoning_effort"), ()),
        "pi": (("defaultProvider", "defaultModel", "defaultThinkingLevel"), ("deviceId", "trackingId")),
    }
    for name, (picks, unrestored) in expected.items():
        spec = manifest.by_harness[name]
        assert spec.pick_keys == picks
        assert spec.unrestored_keys == unrestored
    assert [s.harness for s in manifest.live_state] == ["agy", "claude-code", "codex", "pi"]
    hs.check_gitattributes(manifest)

    repo, env = init_repo(tmp_path)
    shutil.copy(REPO / ".gitattributes", repo / ".gitattributes")
    positive = ["claude/settings.json", "claude/settings.work.json", "codex/config.toml",
                "codex/config.work.toml", "pi/settings.json", "agy/settings.json"]
    negative = ["claude/settings/nested.json", "harnesses.toml", "links.toml", "codex/hooks.json"]
    for path in positive + negative:
        out = git(repo, env, "check-attr", "filter", "--", path).stdout
        filtered = out.strip().endswith(": filter: harness-state")
        matched = any(s.filter_re.fullmatch(path) for s in manifest.live_state)
        assert filtered == matched == (path in positive), path


def replaced(old, new, base=JSON_ENTRY):
    assert old in base
    return base.replace(old, new)


VIOLATIONS = {
    "schema2": SHIPPED.replace("schema = 1", "schema = 2"),
    "schema-bool": SHIPPED.replace("schema = 1", "schema = true"),
    "schema-float": SHIPPED.replace("schema = 1", "schema = 1.0"),
    "top-unknown": SHIPPED + "\nextra = 1\n",
    "empty-harnesses": "schema = 1\n[harnesses]\n",
    "bad-slug": SHIPPED.replace("[harnesses.pi-durable]", "[harnesses.Claude]"),
    "unknown-key": SHIPPED.replace("[harnesses.pi.live_state]", "[harnesses.pi]\nfoo = 1\n[harnesses.pi.live_state]"),
    "config-star": replaced('config = "a/s.json"', 'config = "a/*.json"'),
    "config-dotdot": replaced('config = "a/s.json"', 'config = "a/../s.json"'),
    "config-local": replaced('config = "a/s.json"', 'config = "local/s.json"').replace(
        'filter_glob = "a/s*.json"', 'filter_glob = "local/s*.json"'),
    "config-noslash": replaced('config = "a/s.json"', 'config = "s.json"'),
    "glob-question": replaced('"a/s*.json"', '"a/s?.json"'),
    "glob-class": replaced('"a/s*.json"', '"a/[s]*.json"'),
    "glob-doublestar": replaced('"a/s*.json"', '"a/**.json"'),
    "glob-two-star": replaced('"a/s*.json"', '"a/*s*.json"'),
    "config-not-in-glob": replaced('config = "a/s.json"', 'config = "a/t.json"'),
    "dup-config": SHIPPED + '\n[harnesses.dup.live_state]\nconfig = "pi/settings.json"\n'
                  'filter_glob = "pi/settings.json"\nformat = "json"\nclean_keys = ["k"]\n',
    "dup-glob": SHIPPED + '\n[harnesses.dup.live_state]\nconfig = "pi/settings.json"\n'
                'filter_glob = "pi/settings*.json"\nformat = "json"\nclean_keys = ["k"]\n',
    "glob-overlap": JSON_ENTRY + '''
[harnesses.b.live_state]
config = "a/s-x.json"
filter_glob = "a/s-x*.json"
format = "json"
clean_keys = ["k"]
''',
    "bad-regex-table": replaced('table = "tui"', 'table = "tui("', TOML_ENTRY),
    "bad-regex-clean-tables": replaced("'p\\..+']", "'p(']", TOML_ENTRY),
    "trust-not-in-tables": replaced("trust_table = 'p\\..+'", "trust_table = 'q\\..+'", TOML_ENTRY),
    "record-without-units": replaced('pick_units = [["m"], ["e"]]\n', ""),
    "units-without-record": replaced('picks_record = "local/p.json"\n', ""),
    "record-outside-local": replaced('"local/p.json"', '"picks.json"'),
    "record-dotdot": replaced('"local/p.json"', '"local/../x.json"'),
    "units-overlap-across": replaced('[["m"], ["e"]]', '[["m"], ["m", "e"]]'),
    "units-overlap-within": replaced('[["m"], ["e"]]', '[["m", "m"], ["e"]]'),
    "json-key-missing": replaced('unrestored_keys = ["x"]\n', ""),
    "json-key-in-both": replaced('unrestored_keys = ["x"]', 'unrestored_keys = ["x", "e"]'),
    "toml-top-key-missing": replaced('pick_units = [["m", "e"]]', 'pick_units = [["m"]]', TOML_ENTRY),
    "toml-top-key-in-both": replaced('pick_units = [["m", "e"]]',
                                     'pick_units = [["m", "e"]]\nunrestored_keys = ["m"]', TOML_ENTRY),
    "json-unknown-live-key": replaced('format = "json"', 'format = "json"\ntrust_table = "x"'),
    "bad-format": replaced('"json"', '"yaml"'),
}


@pytest.mark.parametrize("name", sorted(VIOLATIONS))
def test_manifest_validation_refuses_each_schema_and_partition_violation(tmp_path, name):
    with pytest.raises(hs.ManifestError) as caught:
        manifest_from(tmp_path, VIOLATIONS[name])
    assert caught.value.problems


def test_valid_fixtures_load(tmp_path):
    assert manifest_from(tmp_path, JSON_ENTRY).by_harness["a"].unrestored_keys == ("x",)
    spec = manifest_from(tmp_path, TOML_ENTRY).by_harness["c"]
    assert spec.trust_table.pattern == "p\\..+" and spec.pick_keys == ("m", "e")


def test_clean_only_live_state_defaults_unrestored_keys_and_validates(tmp_path):
    clean_only = '''schema = 1
[harnesses.a.live_state]
config = "a/s.json"
filter_glob = "a/s*.json"
format = "json"
clean_keys = ["m", "e"]
'''
    spec = manifest_from(tmp_path, clean_only).by_harness["a"]
    assert spec.unrestored_keys == ("m", "e") and spec.pick_units == () and spec.picks_record is None
    explicit = manifest_from(tmp_path, clean_only + 'unrestored_keys = ["e", "m"]\n').by_harness["a"]
    assert set(explicit.unrestored_keys) == {"m", "e"}
    with pytest.raises(hs.ManifestError):
        manifest_from(tmp_path, clean_only + 'unrestored_keys = ["m"]\n')


def test_non_utf8_and_malformed_toml_raise_manifest_error(tmp_path):
    missing = tmp_path / "nope.toml"
    with pytest.raises(hs.ManifestError):
        hs.load_manifest(missing)
    bad = {"truncated": b'schema = 1\n[harnesses.a', "bytes": b"\xff\xfe"}
    for payload in bad.values():
        path = tmp_path / "bad.toml"
        path.write_bytes(payload)
        with pytest.raises(hs.ManifestError):
            hs.load_manifest(path)
        with pytest.raises(SystemExit) as caught:
            hs.load_manifest_or_exit("tool", path)
        assert str(caught.value).startswith("tool: ")
    with pytest.raises(SystemExit) as caught:
        hs.load_manifest_or_exit("tool", missing)
    assert str(caught.value).startswith("tool: ")


def test_check_gitattributes_refuses_drift_duplicates_and_negated_filter(tmp_path):
    manifest = hs.load_manifest()
    good = (REPO / ".gitattributes").read_text()
    path = tmp_path / "attrs"
    path.write_text(good)
    hs.check_gitattributes(manifest, path)
    bad = {
        "missing": "\n".join(good.splitlines()[1:]) + "\n",
        "extra": good + "other/*.json filter=harness-state\n",
        "duplicate": good + good.splitlines()[0] + "\n",
        "negated": good + "x/y.json -filter=harness-state\n",
        "typo": good + "x/y.json filter=harness_state\n",
    }
    for name, text in bad.items():
        path.write_text(text)
        with pytest.raises(hs.ManifestError):
            hs.check_gitattributes(manifest, path)
    path.write_text("# comment\n\n" + good)
    hs.check_gitattributes(manifest, path)


def test_check_filter_config_and_cli_check(tmp_path, monkeypatch):
    repo, env = init_repo(tmp_path)
    git_dir = repo / ".git"

    def configure(clean=None, required=None):
        for key in ("clean", "required"):
            git(repo, env, "config", "--unset", f"filter.harness-state.{key}", check=False)
        if clean is not None:
            git(repo, env, "config", "filter.harness-state.clean", clean)
        if required is not None:
            git(repo, env, "config", "filter.harness-state.required", required)

    # check_filter_config spawns git with the process environment: leave only the isolated keys.
    for key in list(os.environ):
        monkeypatch.delenv(key)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    for clean, required in ((None, "true"), ("/abs/path/harness-state-clean %f", "true"),
                            (hs.EXPECTED_CLEAN_FILTER, None), (hs.EXPECTED_CLEAN_FILTER, "false")):
        configure(clean, required)
        with pytest.raises(hs.ManifestError, match="just setup"):
            hs.check_filter_config(git_dir)
    configure(hs.EXPECTED_CLEAN_FILTER, "true")
    hs.check_filter_config(git_dir)


def test_cli_check_reports_filter_config_through_isolated_subprocess(tmp_path):
    repo, env = scratch_checkout(tmp_path, '{\n  "theme": "system"\n}\n')
    assert run_check(repo, env).returncode == 0
    git(repo, env, "config", "filter.harness-state.required", "false")
    result = run_check(repo, env)
    assert result.returncode == 2 and "just setup" in result.stderr
    git(repo, env, "config", "filter.harness-state.required", "true")
    git(repo, env, "config", "filter.harness-state.clean", "/abs/harness-state-clean %f")
    result = run_check(repo, env)
    assert result.returncode == 2 and "just setup" in result.stderr


def test_non_object_json_is_reported_cleanly(tmp_path):
    manifest = hs.load_manifest()
    (tmp_path / "pi").mkdir()
    (tmp_path / "pi" / "settings.json").write_text("[]")
    with pytest.raises(hs.ManifestError, match="pi/settings.json"):
        hs.check_clean_tree(manifest, tmp_path)
    (tmp_path / "cli").mkdir()
    repo, env = scratch_checkout(tmp_path / "cli", "[]")
    result = run_check(repo, env)
    assert result.returncode == 2 and "Traceback" not in result.stderr
    assert "pi/settings.json" in result.stderr and "harness-state: " in result.stderr


def scratch_checkout(tmp_path, pi_text):
    repo, env = init_repo(tmp_path)
    (repo / ".githooks").mkdir()
    shutil.copy(HOOKS / "harness_state.py", repo / ".githooks" / "harness_state.py")
    shutil.copy(REPO / "harnesses.toml", repo / "harnesses.toml")
    shutil.copy(REPO / ".gitattributes", repo / ".gitattributes")
    (repo / "claude").mkdir()
    (repo / "claude" / "settings.json").write_text('{\n  "theme": "dark"\n}\n')
    (repo / "pi").mkdir()
    (repo / "pi" / "settings.json").write_text(pi_text)
    git(repo, env, "config", "filter.harness-state.clean", hs.EXPECTED_CLEAN_FILTER)
    git(repo, env, "config", "filter.harness-state.required", "true")
    return repo, env


def run_check(repo, env):
    return subprocess.run([sys.executable, str(repo / ".githooks" / "harness_state.py"), "check",
                           "--git-dir", str(repo / ".git"), "--staged-tree"],
                          env=env, text=True, capture_output=True, cwd=repo)


@pytest.mark.parametrize("leaked", ['{"theme": "system", "deviceId": "secret"}', "{not json"])
def test_check_clean_tree_refuses_unfiltered_blob_and_names_renormalize(tmp_path, leaked):
    repo, env = scratch_checkout(tmp_path, leaked)
    result = run_check(repo, env)
    assert result.returncode == 2
    assert "pi/settings.json" in result.stderr
    assert "git add --renormalize pi/settings.json" in result.stderr
    assert result.stderr.startswith("harness-state: ")
    assert "Traceback" not in result.stderr
    (repo / "pi" / "settings.json").write_text('{\n  "theme": "system"\n}\n')
    result = run_check(repo, env)
    assert result.returncode == 0, result.stderr


def test_check_clean_tree_in_process_ignores_worktrees_and_git(tmp_path):
    manifest = hs.load_manifest()
    (tmp_path / "pi").mkdir()
    (tmp_path / "pi" / "settings.json").write_text('{\n  "theme": "x"\n}\n')
    (tmp_path / ".worktrees" / "w" / "pi").mkdir(parents=True)
    (tmp_path / ".worktrees" / "w" / "pi" / "settings.json").write_text('{"deviceId": "s"}')
    hs.check_clean_tree(manifest, tmp_path)
    (tmp_path / "pi" / "settings.json").write_text('{"deviceId": "s"}')
    with pytest.raises(hs.ManifestError, match="git add --renormalize pi/settings.json"):
        hs.check_clean_tree(manifest, tmp_path)


def test_clean_json_and_three_arg_clean_toml(tmp_path):
    assert hs.clean_json('{"a": 1, "model": "x", "é": 2}', ["model"]) == '{\n  "a": 1,\n  "é": 2\n}\n'
    manifest = hs.load_manifest()
    codex = manifest.by_harness["codex"]
    text = (
        'model = "gpt"\n'
        'model_reasoning_effort = "high"\n'
        'keep = 1\n'
        '[tui]\n'
        'screen_reader_detection_done = true\n'
        'model = "kept: nested table key"\n'
        '[tui.model_availability_nux]\n'
        'a = 1\n'
        '\n'
        '[marketplaces.foo]\n'
        'last_updated = "x"\n'
        'last_revision = "y"\n'
        'source = "s"\n'
        '[projects."/p"]\n'
        'trust_level = "trusted"\n'
        '\n'
        '[other]\n'
        'model = "kept"\n'
    )
    expected = (
        'keep = 1\n'
        '[tui]\n'
        'model = "kept: nested table key"\n'
        '[marketplaces.foo]\n'
        'source = "s"\n'
        '[other]\n'
        'model = "kept"\n'
    )
    assert hs.clean_toml(text, codex.toml_clean_keys, codex.toml_clean_tables) == expected
    assert hs.clean_for_spec(codex, text) == expected
    pi = manifest.by_harness["pi"]
    assert hs.clean_for_spec(pi, '{"deviceId": "d", "theme": "t"}') == '{\n  "theme": "t"\n}\n'
    unmatched = re.compile(r"nomatch")
    assert hs.clean_toml(text, (), (unmatched,)) == text
