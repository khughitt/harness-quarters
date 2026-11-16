"""agy discovery, the conversation_summaries side input, and the agy header (spec rev 2 §4.2, §4.6).

The fixture store is synthetic. Each test copies it under its own temporary HOME and builds
conversation_summaries.db there from the committed SQL text; no live store is read.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import pytest

TOOLS = Path(__file__).resolve().parent
STORE = TOOLS / "fixtures/session-logs/agy/.gemini/antigravity-cli"
A = "a9000000-0000-4000-8000-0000000000a1"   # root conversation, summary row present
B = "a9000000-0000-4000-8000-0000000000b1"   # subagent of A, row with an encoded workspace URI
C = "a9000000-0000-4000-8000-0000000000c1"   # no summary row
COLUMNS = ["conversation_id", "parent_conversation_id", "workspace_uris", "agent_name"]


def canonical_sha256(value) -> str:
    """Spec §4.2's fingerprint, computed independently of the decoder."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode()).hexdigest()


def build_store(tmp_path):
    """A private copy of the fixture store with its summaries database built from SQL."""
    root = tmp_path / "home/.gemini/antigravity-cli"
    shutil.copytree(STORE, root)
    with sqlite3.connect(root / "conversation_summaries.db") as connection:
        connection.executescript((root / "conversation_summaries.sql").read_text())
    connection.close()
    return root


@pytest.fixture
def store(tmp_path):
    """The decoder never writes the database: its bytes and mtime are unchanged afterwards."""
    root = build_store(tmp_path)
    before = database_state(root)
    yield root
    assert database_state(root) == before


@pytest.fixture
def mutable_store(tmp_path):
    """For the tests that damage or extend the database themselves."""
    return build_store(tmp_path)


def environment(tmp_path):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(home),
            "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}


def run(tmp_path, args, stdin=None, cwd=None):
    return subprocess.run([sys.executable, str(TOOLS / "harness-evidence"), *args], input=stdin,
                          capture_output=True, text=True, timeout=60, env=environment(tmp_path), cwd=cwd)


def discover(tmp_path, root):
    proc = run(tmp_path, ["discover", "--root", f"agy={root / 'brain'}"])
    assert proc.returncode == 0, proc.stderr
    return [json.loads(line) for line in proc.stdout.splitlines()]


def files(objs):
    return {Path(o["path"]).parts[-4] + "/" + Path(o["path"]).name: o
            for o in objs if o["object"] == "file"}


def transcript(root, conversation, name="transcript_full.jsonl"):
    return root / "brain" / conversation / ".system_generated/logs" / name


def held(path):
    info = path.stat()
    return {"path": str(path), "size": info.st_size,
            "identity": {"device": info.st_dev, "inode": info.st_ino}}


def database_state(root):
    path = root / "conversation_summaries.db"
    return path.read_bytes(), path.stat().st_mtime_ns


def test_discover_lists_full_transcripts_and_labels_each_mirror(tmp_path, store):
    (transcript(store, A).parent / "chunks/transcript_full").mkdir(parents=True)
    shutil.copy(transcript(store, A), transcript(store, A).parent / "chunks/transcript_full/00000000.jsonl")
    before = database_state(store)
    objs = discover(tmp_path, store)
    assert database_state(store) == before
    root = objs[0]
    assert (root["object"], root["harness"], root["home"], root["profile"], root["store"],
            root["files"]) == ("root", "agy", "agy", "personal", "live", 4)
    rows = files(objs)
    assert sorted(rows) == sorted([f"{A}/transcript_full.jsonl", f"{A}/transcript.jsonl",
                                   f"{B}/transcript_full.jsonl", f"{C}/transcript_full.jsonl"])
    for name, row in rows.items():
        conversation = name.split("/")[0]
        assert row["harness"] == "agy"
        assert row["place"] == {"harness": "agy", "home": "agy", "profile": "personal", "store": "live",
                                "relpath": f"brain/{conversation}/.system_generated/logs/{name.split('/')[1]}"}
        assert row["filename_identity"] == {"conversation": conversation, "basis": "convention"}
        if name.endswith("/transcript.jsonl"):
            assert row["copy"] == {"label": "truncated_mirror", "basis": "convention",
                                   "full": str(transcript(store, conversation))}
        else:
            assert row["copy"] is None


def test_a_mirror_without_its_full_transcript_names_no_full_file(tmp_path, store):
    transcript(store, A).unlink()
    row = files(discover(tmp_path, store))[f"{A}/transcript.jsonl"]
    assert row["copy"] == {"label": "truncated_mirror", "basis": "convention", "full": None}


def test_discover_resolves_summary_facts_once_per_row(tmp_path, store):
    rows = files(discover(tmp_path, store))
    a, b, c = (rows[f"{x}/transcript_full.jsonl"] for x in (A, B, C))
    facts_a = {"parent": None, "subagent": False, "cwd": "/w/alpha", "agent_name": ""}
    facts_b = {"parent": A, "subagent": True, "cwd": "/w/alpha beta", "agent_name": "task-2"}
    for row, facts in ((a, facts_a), (b, facts_b)):
        assert {k: row["path_facts"][k] for k in facts} == facts
        assert row["path_facts"]["reason"] is None
        assert row["path_facts"]["basis"] == "native"
        assert row["path_facts"]["rule"] == "agy_conversation_summaries"
        assert row["side_inputs"] == {"agy_conversation_summaries": canonical_sha256(facts)}
    assert {k: c["path_facts"][k] for k in facts_a} == dict.fromkeys(facts_a)
    assert c["path_facts"]["reason"] == "no_summary_row"
    assert c["side_inputs"] == {"agy_conversation_summaries": canonical_sha256({"status": "no_summary_row"})}
    mirror = rows[f"{A}/transcript.jsonl"]
    assert mirror["path_facts"] == a["path_facts"] | {"ref": mirror["path_facts"]["ref"]}
    assert mirror["side_inputs"] == a["side_inputs"]


@pytest.mark.parametrize("damage", ["missing", "not_a_database", "unreadable"])
def test_unreadable_summaries_null_every_fact(tmp_path, mutable_store, damage):
    store = mutable_store
    database = store / "conversation_summaries.db"
    if damage == "missing":
        database.unlink()
    elif damage == "not_a_database":
        database.write_bytes(b"this is not sqlite\n" * 64)
    else:
        if os.geteuid() == 0:
            pytest.skip("root reads a mode-0 file")
        database.chmod(0)
    before = listing(store), damaged_state(database)
    rows = files(discover(tmp_path, store))
    assert (listing(store), damaged_state(database)) == before
    for name, row in rows.items():
        assert row["path_facts"]["reason"] == "summaries_unreadable", name
        assert all(row["path_facts"][k] is None for k in ("parent", "subagent", "cwd", "agent_name"))
        assert row["side_inputs"] == {
            "agy_conversation_summaries": canonical_sha256({"status": "summaries_unreadable"})}
    assert damage == "missing" or not (store / "conversation_summaries.db-journal").exists()


def damaged_state(database):
    """Bytes and mtime where readable; the mtime alone for a mode-0 file; None when missing."""
    if not database.exists():
        return None
    info = database.stat()
    return (database.read_bytes() if info.st_mode & 0o444 else None), info.st_mtime_ns


def test_a_row_added_between_discover_calls_changes_the_fingerprint(tmp_path, mutable_store):
    store = mutable_store
    first = files(discover(tmp_path, store))[f"{C}/transcript_full.jsonl"]
    with sqlite3.connect(store / "conversation_summaries.db") as connection:
        connection.execute("INSERT INTO conversation_summaries (conversation_id, last_modified_time,"
                           " workspace_uris, agent_name, parent_conversation_id, last_user_input_time)"
                           " VALUES (?, '2026-11-02 10:00:07', '[\"file:///w/gamma\"]', '', '',"
                           " '2026-11-02 10:00:05')", (C,))
    connection.close()
    before = database_state(store)
    second = files(discover(tmp_path, store))[f"{C}/transcript_full.jsonl"]
    assert database_state(store) == before
    facts = {"parent": None, "subagent": False, "cwd": "/w/gamma", "agent_name": ""}
    assert first["side_inputs"] != second["side_inputs"]
    assert second["side_inputs"] == {"agy_conversation_summaries": canonical_sha256(facts)}
    assert (second["device"], second["inode"], second["size"], second["mtime_ns"]) == (
        first["device"], first["inode"], first["size"], first["mtime_ns"])


def set_workspace(store, conversation, value):
    with sqlite3.connect(store / "conversation_summaries.db") as connection:
        connection.execute("UPDATE conversation_summaries SET workspace_uris = ? WHERE conversation_id = ?",
                           (value, conversation))
    connection.close()


def test_an_empty_workspace_value_is_a_resolved_row_without_cwd(tmp_path, mutable_store):
    # agy writes '' for a session started with no workspace (as harness_stores/agy.py reads it).
    set_workspace(mutable_store, B, "")
    row = files(discover(tmp_path, mutable_store))[f"{B}/transcript_full.jsonl"]
    facts = {"parent": A, "subagent": True, "cwd": None, "agent_name": "task-2"}
    assert {k: row["path_facts"][k] for k in facts} == facts and row["path_facts"]["reason"] is None
    assert row["side_inputs"] == {"agy_conversation_summaries": canonical_sha256(facts)}


@pytest.mark.parametrize("value", ['["file://otherhost/w/alpha"]', '["https://example.org/w"]', '["file://[x/y"]',
                                   '["file:relative/path"]', '{"not": "a list"}', "not json"])
def test_a_workspace_value_agy_does_not_write_reads_as_unreadable(tmp_path, mutable_store, value):
    set_workspace(mutable_store, B, value)
    rows = files(discover(tmp_path, mutable_store))
    assert rows[f"{B}/transcript_full.jsonl"]["path_facts"]["reason"] == "summaries_unreadable"
    assert rows[f"{A}/transcript_full.jsonl"]["path_facts"]["reason"] is None


def test_a_relative_root_resolves_the_same_facts(tmp_path, store):
    absolute = files(discover(tmp_path, store))
    proc = run(tmp_path, ["discover", "--root", "agy=.gemini/antigravity-cli/brain"], cwd=store.parent.parent)
    assert proc.returncode == 0, proc.stderr
    relative = files([json.loads(line) for line in proc.stdout.splitlines()])
    assert sorted(relative) == sorted(absolute)
    for name, row in relative.items():
        assert row["path_facts"]["reason"] == absolute[name]["path_facts"]["reason"], name
        assert row["side_inputs"] == absolute[name]["side_inputs"], name


def listing(root):
    return sorted(p.name for p in root.iterdir())


def test_a_wal_database_is_read_without_creating_files(tmp_path, mutable_store):
    store = mutable_store  # Switching the journal mode rewrites the header; the check starts after.
    with sqlite3.connect(store / "conversation_summaries.db") as connection:
        assert connection.execute("PRAGMA journal_mode=wal").fetchone() == ("wal",)
    connection.close()
    before, state = listing(store), database_state(store)
    assert "conversation_summaries.db-wal" not in before
    rows = files(discover(tmp_path, store))
    assert rows[f"{A}/transcript_full.jsonl"]["path_facts"]["reason"] is None
    proc = header(tmp_path, store, transcript(store, A))
    assert proc.returncode == 0, proc.stderr
    assert listing(store) == before and database_state(store) == state


def test_a_wal_database_with_a_live_writer_shows_uncheckpointed_rows(tmp_path, mutable_store):
    store = mutable_store
    database = store / "conversation_summaries.db"
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA journal_mode=wal")
    connection.close()
    writer = sqlite3.connect(database)
    try:
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("INSERT INTO conversation_summaries (conversation_id, last_modified_time,"
                       " workspace_uris, agent_name, parent_conversation_id, last_user_input_time)"
                       " VALUES (?, '2026-11-02 10:00:07', '[\"file:///w/gamma\"]', '', '',"
                       " '2026-11-02 10:00:05')", (C,))
        writer.commit()
        before, main = listing(store), database.read_bytes()
        assert "conversation_summaries.db-wal" in before
        row = files(discover(tmp_path, store))[f"{C}/transcript_full.jsonl"]
        assert row["path_facts"]["cwd"] == "/w/gamma" and row["path_facts"]["reason"] is None
        assert listing(store) == before and database.read_bytes() == main
    finally:
        writer.close()


def test_a_rollback_journal_database_never_shows_an_uncommitted_row(tmp_path, mutable_store):
    # Only a WAL file may be read immutable; a rollback-mode file keeps SQLite's locking.
    store = mutable_store
    database = store / "conversation_summaries.db"
    writer = sqlite3.connect(database, isolation_level=None)
    try:
        writer.execute("BEGIN EXCLUSIVE")
        writer.execute("UPDATE conversation_summaries SET agent_name = 'uncommitted' WHERE conversation_id = ?", (B,))
        before = listing(store)
        row = files(discover(tmp_path, store))[f"{B}/transcript_full.jsonl"]
        assert row["path_facts"]["agent_name"] != "uncommitted"
        assert row["path_facts"]["reason"] == "summaries_unreadable"  # locked, not guessed
        assert listing(store) == before
    finally:
        writer.execute("ROLLBACK")
        writer.close()
    row = files(discover(tmp_path, store))[f"{B}/transcript_full.jsonl"]
    assert row["path_facts"]["agent_name"] == "task-2" and row["path_facts"]["reason"] is None


HOT_WRITER = """
import os, sqlite3, sys
connection = sqlite3.connect(sys.argv[1], isolation_level=None)
connection.execute("PRAGMA cache_size=2")  # Spill dirty pages into the database before commit.
connection.execute("BEGIN IMMEDIATE")
connection.execute("UPDATE conversation_summaries SET agent_name = 'uncommitted' WHERE conversation_id = ?",
                   (sys.argv[2],))
connection.execute("CREATE TABLE filler (value BLOB)")
connection.executemany("INSERT INTO filler VALUES (?)", ((os.urandom(4000),) for _ in range(200)))
os._exit(0)  # A writer that dies here leaves a hot journal and a half-written database.
"""


def test_a_hot_journal_reads_as_unreadable_and_is_left_in_place(tmp_path, mutable_store):
    store = mutable_store
    database = store / "conversation_summaries.db"
    journal = store / "conversation_summaries.db-journal"
    subprocess.run([sys.executable, "-c", HOT_WRITER, str(database), B], check=True, timeout=60,
                   env=environment(tmp_path))
    assert journal.stat().st_size > 0
    before = listing(store), database.read_bytes(), journal.read_bytes()
    row = files(discover(tmp_path, store))[f"{B}/transcript_full.jsonl"]
    assert row["path_facts"]["agent_name"] is None
    assert row["path_facts"]["reason"] == "summaries_unreadable"  # never the spilled page, never rolled back
    assert (listing(store), database.read_bytes(), journal.read_bytes()) == before


def header(tmp_path, store, *paths):
    request = {"id": 1, "roots": [{"harness": "agy", "path": str(store / "brain")}],
               "files": [held(path) for path in paths]}
    return run(tmp_path, ["header"], json.dumps(request) + "\n")


def test_header_reads_session_and_start_from_the_transcript_and_identity_from_the_snapshot(tmp_path, store):
    before = database_state(store)
    proc = header(tmp_path, store, transcript(store, A), transcript(store, B), transcript(store, C))
    assert proc.returncode == 0, proc.stderr
    assert database_state(store) == before
    rows = [json.loads(line) for line in proc.stdout.splitlines()]
    assert [r["object"] for r in rows] == ["header", "header", "header", "request_end"]
    assert all(r["harness"] == "agy" and r["status"] == "ok" for r in rows[:3])
    assert [r["header"] for r in rows[:3]] == [
        {"session": A, "start_ms": 1793524600000, "cwd": "/w/alpha", "parent": None, "subagent": False},
        {"session": B, "start_ms": 1793524620000, "cwd": "/w/alpha beta", "parent": A, "subagent": True},
        {"session": C, "start_ms": 1793613605000, "cwd": None, "parent": None, "subagent": None}]
    start = rows[2]["provenance"]["start_ms"]
    assert (start["native_paths"], start["basis"], start["line"]) == (["created_at"], "native", 2)
    assert start["ref"] == f"agy:brain/{C}/.system_generated/logs/transcript_full.jsonl#L2"
    assert rows[0]["provenance"]["session"]["basis"] == "convention"
    assert rows[2]["provenance"]["cwd"]["reason"] == "no_summary_row"


def steps_file(store, conversation, lines):
    path = transcript(store, conversation)
    path.parent.mkdir(parents=True)
    path.write_text("".join(json.dumps(line) + "\n" for line in lines))
    return path


def test_header_reads_start_only_within_fifty_lines(tmp_path, mutable_store):
    plain = {"step_index": 0, "source": "SYSTEM", "type": "SYSTEM_MESSAGE"}
    timed = {**plain, "created_at": "2026-11-02T10:00:05Z"}
    inside = steps_file(mutable_store, "a9000000-0000-4000-8000-0000000000d1", [plain] * 49 + [timed])
    beyond = steps_file(mutable_store, "a9000000-0000-4000-8000-0000000000e1", [plain] * 50 + [timed])
    proc = header(tmp_path, mutable_store, inside, beyond)
    assert proc.returncode == 0, proc.stderr
    rows = [json.loads(line) for line in proc.stdout.splitlines()]
    assert [r["header"]["start_ms"] for r in rows[:2]] == [1793613605000, None]
    assert rows[0]["provenance"]["start_ms"]["line"] == 50


def test_header_and_index_refuse_the_truncated_mirror(tmp_path, store):
    mirror = transcript(store, A, "transcript.jsonl")
    proc = header(tmp_path, store, mirror)
    assert proc.returncode == 2 and proc.stdout == ""
    assert proc.stderr.strip() == "protocol error: agy index reads transcript_full.jsonl"
    proc = decode_index(tmp_path, store, mirror)
    assert_refused(proc, "agy index reads transcript_full.jsonl")


def assert_refused(proc, message):
    """decode reports an in-stream protocol error as the typed exception, emitting nothing."""
    assert proc.returncode == 1 and proc.stdout == ""
    assert proc.stderr.splitlines()[-1] == "harness_evidence._protocol.ProtocolError: " + message


def decode_index(tmp_path, store, path):
    request = {"id": 1, "extract": "index", "cross_file": False, "text": False, "raw": False,
               "roots": [{"harness": "agy", "path": str(store / "brain")}], "files": [held(path)]}
    return run(tmp_path, ["decode"], json.dumps(request) + "\n")


def test_index_decode_runs_from_the_command_line(tmp_path, store):
    proc = decode_index(tmp_path, store, transcript(store, A))
    assert proc.returncode == 0, proc.stderr
    objs = [json.loads(line) for line in proc.stdout.splitlines()]
    assert [o["object"] for o in objs][0] == "file_start" and objs[-1]["object"] == "request_end"
    assert objs[0]["side_inputs"] == files(discover(tmp_path, store))[f"{A}/transcript_full.jsonl"]["side_inputs"]
    assert objs[-2]["status"] == "ok" and any(o["object"] == "index_event" for o in objs)


def test_reader_decode_reads_an_explicit_agy_file_as_unknown_and_skips_agy_context(tmp_path, store):
    loose = tmp_path / "loose.jsonl"
    shutil.copy(transcript(store, A), loose)
    claude = TOOLS / "fixtures/session-logs/index/sizes.jsonl"
    request = {"id": 1, "context": [str(transcript(store, B))],
               "roots": [{"harness": "agy", "path": str(store / "brain")}],
               "files": [{"path": str(loose), "size": loose.stat().st_size},
                         {"path": str(claude), "size": claude.stat().st_size}]}
    proc = run(tmp_path, ["decode"], json.dumps(request) + "\n")
    assert proc.returncode == 0, proc.stderr
    ends = [json.loads(line) for line in proc.stdout.splitlines() if json.loads(line)["object"] == "file_end"]
    assert [e["status"] for e in ends] == ["unknown_format", "ok"]  # as before agy was detected


def test_reader_decode_refuses_agy_sources(tmp_path, store):
    request = {"id": 1, "roots": [{"harness": "agy", "path": str(store / "brain")}],
               "files": [{"path": str(transcript(store, A)), "size": transcript(store, A).stat().st_size}]}
    proc = run(tmp_path, ["decode"], json.dumps(request) + "\n")
    assert_refused(proc, "agy supports only extract:index")
    empty = run(tmp_path, ["decode"], json.dumps({**request, "files": []}) + "\n")
    assert empty.returncode == 0, empty.stderr
    assert [json.loads(line)["object"] for line in empty.stdout.splitlines()] == ["request_end"]


def test_an_agy_root_must_be_the_brain_directory(tmp_path, store):
    # Refused where other invalid roots are: one line and exit 2, before any output.
    proc = run(tmp_path, ["discover", "--root", f"agy={store}"])
    assert proc.returncode == 2 and proc.stdout == ""
    assert "agy root must be a brain directory" in proc.stderr and "Traceback" not in proc.stderr
    request = {"id": 1, "extract": "index", "cross_file": False, "text": False, "raw": False,
               "roots": [{"harness": "agy", "path": str(store)}], "files": [held(transcript(store, A))]}
    proc = run(tmp_path, ["decode"], json.dumps(request) + "\n")
    assert proc.returncode == 2 and proc.stdout == ""
    assert proc.stderr == "protocol error: agy root must be a brain directory\n"
    proc = run(tmp_path, ["header"], json.dumps({"id": 1, "roots": request["roots"],
                                                 "files": request["files"]}) + "\n")
    assert proc.returncode == 2 and proc.stdout == ""
    assert "agy root must be a brain directory" in proc.stderr


def test_a_file_outside_the_transcript_layout_is_refused(tmp_path, store):
    stray = store / "brain" / A / "transcript_full.jsonl"
    shutil.copy(transcript(store, A), stray)
    proc = header(tmp_path, store, stray)
    assert proc.returncode == 2 and proc.stdout == ""
    assert proc.stderr.strip() == ("protocol error: agy index reads "
                                   "brain/<id>/.system_generated/logs/transcript_full.jsonl")
    assert_refused(decode_index(tmp_path, store, stray),
                   "agy index reads brain/<id>/.system_generated/logs/transcript_full.jsonl")


def test_default_roots_include_the_agy_home(tmp_path, store):
    proc = run(tmp_path, ["discover", "--home", str(store.parent.parent)])
    assert proc.returncode == 0, proc.stderr
    objs = [json.loads(line) for line in proc.stdout.splitlines()]
    agy = [o for o in objs if o["object"] == "root" and o["harness"] == "agy"]
    assert len(agy) == 1 and agy[0]["path"] == str(store / "brain") and agy[0]["files"] == 4


def test_capabilities_declare_the_side_input_and_the_agy_header(tmp_path):
    proc = subprocess.run([sys.executable, str(TOOLS / "harness-evidence"), "capabilities", "--json"],
                          capture_output=True, text=True, timeout=60,
                          env=environment(tmp_path))
    assert proc.returncode == 0, proc.stderr
    agy = json.loads(proc.stdout)["harnesses"]["agy"]
    assert agy["header"] == {"implemented": True, "line_limit": 50}
    assert agy["side_inputs"]["agy_conversation_summaries"]["columns"] == COLUMNS
    assert agy["side_inputs"]["agy_conversation_summaries"]["path"] == "conversation_summaries.db"
    assert agy["index"]["mode"] == "incremental" and agy["index"]["resume"] is True
