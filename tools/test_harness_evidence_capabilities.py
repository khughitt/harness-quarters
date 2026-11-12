"""Deterministic capability evidence and fixture-free pinned package operation."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tomllib

from harness_evidence_testing import FIXTURES, path_of

TOOLS = Path(__file__).resolve().parent
ARTIFACT = TOOLS / "harness_evidence" / "capabilities.json"


def environment(tmp_path):
    home = tmp_path / "user-home"
    home.mkdir(parents=True, exist_ok=True)
    return {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(home),
            "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}


def command(root, env, *args, stdin=None):
    return subprocess.run([str(root / "tools/harness-evidence"), *args], cwd=root,
                          env=env, input=stdin, capture_output=True, text=True, timeout=60)


def git(root, env, *args):
    result = subprocess.run(["git", *args], cwd=root, env=env,
                            capture_output=True, timeout=60)
    assert result.returncode == 0, result.stderr
    return result.stdout


def fixture_repo(tmp_path):
    root = tmp_path / "repo"
    (root / "tools").mkdir(parents=True)
    shutil.copytree(TOOLS / "harness_evidence", root / "tools/harness_evidence",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(TOOLS / "harness-evidence", root / "tools/harness-evidence")
    shutil.copy2(TOOLS / "hq", root / "tools/hq")
    shutil.copytree(FIXTURES, root / "tools/fixtures/session-logs")
    (root / ".gitignore").write_text("__pycache__/\n")
    env = environment(tmp_path)
    git(root, env, "init", "-q")
    assert Path(git(root, env, "rev-parse", "--show-toplevel").decode().strip()) == root.resolve()
    assert Path(git(root, env, "rev-parse", "--absolute-git-dir").decode().strip()).is_relative_to(root.resolve())
    git(root, env, "add", ".")
    git(root, env, "commit", "-qm", "fixture")
    return root, env


def build_in(root, env):
    result = command(root, env, "capabilities", "--build")
    assert result.returncode == 0, result.stderr
    return (root / "tools/harness_evidence/capabilities.json").read_bytes()


def test_committed_artifact_equals_a_fresh_build(tmp_path):
    root, env = fixture_repo(tmp_path)
    assert build_in(root, env) == ARTIFACT.read_bytes()


def test_recorded_identity_capability_uses_only_qualifying_native_field(tmp_path):
    from harness_evidence.capabilities import build
    (tmp_path / "one.jsonl").write_text('{"type":"user","sessionId":"recorded"}\n')
    catalogue = tmp_path / "CATALOGUE.toml"
    catalogue.write_text('[[sample]]\npath="one.jsonl"\nharness="claude-code"\nversion="test"\nprovenance="synthetic"\n')
    evidence = build(catalogue)["harnesses"]["claude-code"]
    assert evidence["fields"]["header.recorded_identity.session"]["provenance"] == ["sessionId"]
    assert "header.recorded_identity.session" in evidence["versions"]["test"]["fields_seen"]["synthetic"]
    (tmp_path / "one.jsonl").write_text('{"type":"user","sessionId":"side","isSidechain":true}\n')
    assert "header.recorded_identity.session" not in build(catalogue)["harnesses"]["claude-code"]["versions"]["test"]["fields_seen"]["synthetic"]


def test_build_is_independent_of_revision_dirty_state_and_host_path(tmp_path):
    root, env = fixture_repo(tmp_path / "one")
    first = build_in(root, env)
    (root / "tools/harness_evidence/extra.py").write_text("# changed revision\n")
    git(root, env, "add", ".")
    git(root, env, "commit", "-qm", "changed revision")
    (root / "tools/harness_evidence/extra.py").write_text("# dirty package\n")
    assert build_in(root, env) == first
    other, other_env = fixture_repo(tmp_path / "elsewhere")
    assert build_in(other, other_env) == first
    assert b'"revision"' not in first and b'"dirty"' not in first
    assert str(tmp_path).encode() not in first


def test_served_view_attaches_current_identity_without_writing_artifact(tmp_path):
    root, env = fixture_repo(tmp_path)
    artifact = root / "tools/harness_evidence/capabilities.json"
    before = artifact.read_bytes(), artifact.stat().st_mtime_ns
    for dirty in (False, True):
        if dirty:
            (root / "tools/harness_evidence/extra.py").write_text("# dirty\n")
        result = command(root, env, "capabilities", "--json")
        assert result.returncode == 0, result.stderr
        view = json.loads(result.stdout)
        identity = json.loads(command(root, env, "version", "--json").stdout)["decoder"]
        assert view.pop("decoder") == identity
        assert view == json.loads(before[0])
    assert (artifact.read_bytes(), artifact.stat().st_mtime_ns) == before


def test_artifact_covers_catalogue_hashes_and_keeps_provenance_separate():
    artifact = json.loads(ARTIFACT.read_bytes())
    catalogue = (FIXTURES / "CATALOGUE.toml").read_bytes()
    samples = tomllib.loads(catalogue.decode())["sample"]
    assert set(artifact) == {"schema", "decoder_version", "built_from", "evidence_rule", "harnesses"}
    assert artifact["built_from"] == {
        "catalogue_sha256": hashlib.sha256(catalogue).hexdigest(),
        "samples": {s["path"]: hashlib.sha256((FIXTURES / s["path"]).read_bytes()).hexdigest()
                    for s in samples},
    }
    assert len(samples) == 67
    for slug, harness in artifact["harnesses"].items():
        assert set(harness) == {"record_kinds", "fields", "labels", "versions", "exceptions"}
        assert harness["exceptions"] == []
        assert all(f["coverage_keys"] == [] for f in harness["fields"].values())
        for version, value in harness["versions"].items():
            assert set(value) == {"synthetic", "observed", "fields_seen"}
            assert value["observed"] == [] and value["fields_seen"]["observed"] == []
            assert value["synthetic"] == sorted(s["path"] for s in samples
                                                  if s["harness"] == slug and s["version"] == version)
    assert set(artifact["harnesses"]["codex"]["versions"]) == {"0.163.0", "0.164.0", "unknown"}
    assert ARTIFACT.read_text() == json.dumps(artifact, sort_keys=True, indent=1) + "\n"


def native_values(value, path):
    """Resolve documented dotted native paths, with [] denoting each array item."""
    if not path:
        return [value]
    key, _, rest = path.partition(".")
    many = key.endswith("[]")
    child = value.get(key[:-2] if many else key) if isinstance(value, dict) else None
    return [v for item in (child if isinstance(child, list) else []) for v in native_values(item, rest)] \
        if many else [] if child is None else native_values(child, rest)


def test_every_declared_native_path_occurs_in_its_harness_samples():
    from harness_evidence.capabilities import DECLARED
    samples = tomllib.loads((FIXTURES / "CATALOGUE.toml").read_text())["sample"]
    for slug, fields in DECLARED.items():
        native = []
        for sample in samples:
            if sample["harness"] != slug:
                continue
            for line in (FIXTURES / sample["path"]).read_bytes().splitlines():
                try:
                    value = json.loads(line)
                except (ValueError, UnicodeError):
                    continue
                if isinstance(value, dict):
                    native.append(value)
        for field, paths in fields.items():
            assert paths, (slug, field)
            for path in paths:
                assert any(native_values(row, path) for row in native), (slug, field, path)


def test_fields_seen_require_native_evidence_but_keep_false_and_zero(tmp_path):
    from harness_evidence.capabilities import build
    samples = tmp_path / "samples"
    samples.mkdir()
    (samples / "one.jsonl").write_text(json.dumps({"type": "session_meta", "payload": {"id": "root"}}) + "\n")
    (samples / "two.jsonl").write_text("\n".join(json.dumps(row) for row in [
        {"type": "session_meta", "payload": {"id": "child", "source": {
            "subagent": {"thread_spawn": {"parent_thread_id": "root", "depth": 0}}}}},
        {"type": "response_item", "payload": {"type": "function_call_output", "call_id": "c",
                                               "output": {"success": True, "content": "ok"}}},
    ]) + "\n")
    catalogue = samples / "CATALOGUE.toml"
    catalogue.write_text('[[sample]]\npath="one.jsonl"\nharness="codex"\nversion="absent"\nprovenance="synthetic"\n'
                         '[[sample]]\npath="two.jsonl"\nharness="codex"\nversion="present"\nprovenance="observed"\n')
    versions = build(catalogue)["harnesses"]["codex"]["versions"]
    absent = versions["absent"]["fields_seen"]["synthetic"]
    present = versions["present"]["fields_seen"]["observed"]
    assert "header.depth" not in absent and "header.child" not in absent
    assert "turn_end_message" not in absent and "abort_reason" not in absent
    assert "call.is_error" in present and "header.depth" in present
    assert versions["present"]["synthetic"] == []


def test_header_defaults_cannot_borrow_native_evidence_from_later_metadata(tmp_path):
    from harness_evidence.capabilities import build
    (tmp_path / "one.jsonl").write_text("\n".join(json.dumps(row) for row in [
        {"type": "session_meta", "payload": {"id": "root"}},
        {"type": "session_meta", "payload": {"id": "inherited", "source": {
            "subagent": {"thread_spawn": {"parent_thread_id": "other", "agent_path": "/root/child", "depth": 2}}}}},
    ]) + "\n")
    catalogue = tmp_path / "CATALOGUE.toml"
    catalogue.write_text('[[sample]]\npath="one.jsonl"\nharness="codex"\nversion="test"\nprovenance="synthetic"\n')
    seen = build(catalogue)["harnesses"]["codex"]["versions"]["test"]["fields_seen"]["synthetic"]
    assert "header.depth" not in seen and "header.agent_path" not in seen


def test_absent_fork_marker_and_empty_origin_markers_remain_unobserved(tmp_path):
    from harness_evidence.capabilities import build
    (tmp_path / "one.jsonl").write_text(json.dumps({"type": "user", "sessionId": "s",
        "message": {"content": "plain text"}}) + "\n")
    catalogue = tmp_path / "CATALOGUE.toml"
    catalogue.write_text('[[sample]]\npath="one.jsonl"\nharness="claude-code"\nversion="test"\nprovenance="synthetic"\n')
    seen = build(catalogue)["harnesses"]["claude-code"]["versions"]["test"]["fields_seen"]["synthetic"]
    assert "header.forked" not in seen and "header.markers" not in seen
    assert "origin.markers" not in seen
    # Explicit false from source text still counts, unlike an empty marker/default list.
    assert "origin.unrecognized_tag.lead" in seen


def test_sidecars_and_uncatalogued_siblings_do_not_affect_build(tmp_path, monkeypatch):
    from harness_evidence.capabilities import build
    root, env = fixture_repo(tmp_path)
    before = build_in(root, env)
    fixtures = root / "tools/fixtures/session-logs"
    sidecar = next(fixtures.rglob("*.meta.json"))
    sidecar.write_text('{"toolUseId":"changed-unpinned-input"}\n')
    (sidecar.parent / "agent-uncatalogued.jsonl").write_text('{"type":"user","sessionId":"extra"}\n')
    assert build_in(root, env) == before
    catalogue = FIXTURES / "CATALOGUE.toml"
    allowed = {catalogue, *(FIXTURES / s["path"] for s in tomllib.loads(catalogue.read_text())["sample"])}
    read_bytes = Path.read_bytes

    def catalogued_bytes(path):
        assert path in allowed, f"uncatalogued read: {path}"
        return read_bytes(path)

    def no_discovery(*_args, **_kwargs):
        raise AssertionError("capability builds must not discover uncatalogued siblings")

    monkeypatch.setattr(Path, "read_bytes", catalogued_bytes)
    monkeypatch.setattr(Path, "glob", no_discovery)
    assert build(catalogue) == json.loads(before)


def test_nontext_content_does_not_establish_text_or_marker_fields(tmp_path):
    from harness_evidence.capabilities import build
    (tmp_path / "one.jsonl").write_text(json.dumps({"type": "user", "sessionId": "s",
        "message": {"content": [{"type": "image", "source": {"data": "example"}}]}}) + "\n")
    catalogue = tmp_path / "CATALOGUE.toml"
    catalogue.write_text('[[sample]]\npath="one.jsonl"\nharness="claude-code"\nversion="test"\nprovenance="synthetic"\n')
    seen = build(catalogue)["harnesses"]["claude-code"]["versions"]["test"]["fields_seen"]["synthetic"]
    assert "text" not in seen
    assert "origin.unrecognized_tag.lead" not in seen and "origin.unrecognized_tag.joined" not in seen


def test_text_view_is_a_table_and_never_claims_support(tmp_path):
    result = command(TOOLS.parent, environment(tmp_path), "capabilities")
    assert result.returncode == 0, result.stderr
    assert "supported" not in result.stdout.lower()
    assert "untested" in result.stdout.lower()
    assert "claude-code" in result.stdout and "codex" in result.stdout
    assert "provenance" in result.stdout and "catalogue_sha256" in result.stdout


def test_extracted_git_package_runs_every_command_without_checkout_or_fixtures(tmp_path):
    root, env = fixture_repo(tmp_path)
    archive = git(root, env, "archive", "HEAD", "tools/harness_evidence", "tools/harness-evidence")
    copy = tmp_path / "extracted"
    copy.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
        bundle.extractall(copy, filter="data")
    (copy / "tools/harness_evidence/REVISION").write_text("a" * 40 + "\n")
    sample_dir = tmp_path / "sources"
    sample_dir.mkdir()
    sample = sample_dir / "rollout-t-T.jsonl"
    shutil.copy2(FIXTURES / path_of("XA"), sample)
    # Remove the original checkout to catch accidental fallback reads.
    shutil.rmtree(root)
    assert not (copy / "tools/fixtures").exists() and not (copy / ".git").exists()
    for args in [("version", "--json"), ("capabilities", "--json"),
                 ("discover", "--root", f"codex={sample_dir}")]:
        result = command(copy, env, *args)
        assert result.returncode == 0, result.stderr
        rows = [json.loads(line) for line in result.stdout.splitlines()]
        assert all(row["decoder"]["revision"] == "a" * 40 for row in rows)
        assert all(row["decoder"]["version"] == "7" for row in rows)
        if args[0] == "discover":
            assert next(row for row in rows if row["object"] == "file")["filename_lookup"] == {
                "session_ids": ["T"], "basis": "convention", "rule": "rollout_name_lookup"}
    request = {"id": 1, "files": [{"path": str(sample), "size": sample.stat().st_size}], "roots": []}
    result = command(copy, env, "decode", stdin=json.dumps(request) + "\n")
    assert result.returncode == 0, result.stderr
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    assert rows[-1]["object"] == "request_end"
    assert next(row for row in rows if row["object"] == "file_end")["status"] == "ok"
    result = command(copy, env, "capabilities", "--build")
    assert result.returncode == 2 and "hq checkout" in result.stderr


def test_missing_artifact_fails_instead_of_building_from_fixtures(tmp_path):
    root, env = fixture_repo(tmp_path)
    (root / "tools/harness_evidence/capabilities.json").unlink()
    result = command(root, env, "capabilities", "--json")
    assert result.returncode == 2 and "capabilities" in result.stderr
    assert result.stdout == ""
