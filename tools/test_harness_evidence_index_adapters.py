"""The index adapter registry leaves Claude's index output unchanged.

The golden digests in fixtures/harness-evidence/claude-index-digests-3e346e26.json were
computed at hq 3e346e26, the Stage 3a base, before the registry existed. Every catalogued
index sample is framed through index_stream.objects with text on and off. A sample that
completes is digested whole; a catalogued index_error sample is checked for its exception
and the digest of what it emitted before raising. Only transport values that depend on the
checkout or host are normalized; native evidence is compared as emitted.

Regenerate (only at a deliberate behaviour change, never to make this test pass):
    python3 tools/test_harness_evidence_index_adapters.py --write
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tomllib

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from harness_evidence import DECODER_VERSION, SCHEMA, index_stream  # noqa: E402

CATALOGUE = TOOLS / "fixtures/session-logs/CATALOGUE.toml"
DIGESTS = TOOLS / "fixtures/harness-evidence/claude-index-digests-3e346e26.json"
CAPABILITIES = TOOLS / "harness_evidence/capabilities.json"
RULES = ("decoder", "catalogue_path", "identity")
# Fields added after the base, projected out before comparison and asserted null for Claude.
ADDED_RESULT_FIELDS = ("exit_code",)
ADDED_FILE_START_FIELDS = ("side_inputs",)
ADDED_PROVENANCE = ("results[].exit_code",)
# Compaction keys added after the base; null on every base sample (none holds a boundary).
ADDED_COMPACTION_KEYS = ("id", "trigger", "reason")
# Declarations widened after the base: field -> (current, base).
CHANGED_PROVENANCE = {"compaction": (
    ["isCompactSummary", "subtype", "uuid", "parentUuid", "compactMetadata.trigger", "content"],
    ["isCompactSummary"])}
# Samples catalogued after the base, with the capability evidence they alone add.
ADDED_SAMPLES = ("index/compaction-reasons.jsonl",)
ADDED_SAMPLE_VERSIONS = ("2.1.325",)
ADDED_RECORD_KINDS = ("system/compact_boundary", "system/informational")
# Index reads declared after the base for compaction pairing: kind -> path -> (current, base),
# base None when the read is new.
CHANGED_UNWATCHED = {
    "user": {"uuid": ("dimension", None), "parentUuid": ("dimension", None)},
    "attachment": {"uuid": ("dimension", None), "parentUuid": ("dimension", None)},
    "system": {"uuid": (["applied:turn_end", "dimension"], "applied:turn_end"),
               "parentUuid": ("dimension", None), "compactMetadata.trigger": ("dimension", None),
               "content": ("dimension", None)},
}


def canonical(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def samples():
    catalogue = tomllib.loads(CATALOGUE.read_text(encoding="utf-8"))["sample"]
    return [s for s in catalogue if s.get("profile") == "index" and s["harness"] == "claude-code"]


class Normalizer:
    """Replace checkout- and host-dependent transport values only; count each rule."""

    def __init__(self):
        self.prefix = str(CATALOGUE.parent.resolve()) + "/"
        self.matched = dict.fromkeys(RULES, 0)

    def __call__(self, value):
        if isinstance(value, dict):
            return {key: self._member(key, item) for key, item in value.items()}
        if isinstance(value, list):
            return [self(item) for item in value]
        if isinstance(value, str) and self.prefix in value:
            self.matched["catalogue_path"] += 1
            return value.replace(self.prefix, "")
        return value

    def _member(self, key, item):
        """The envelope's and the checkpoint's `decoder`, and a file `identity`, by key."""
        if key == "decoder" and isinstance(item, dict) and item.keys() == {"version", "revision"}:
            self.matched["decoder"] += 1
            return {"version": "<version>", "revision": "<revision>"}
        if key == "identity" and isinstance(item, dict) and item.keys() == {"device", "inode"}:
            self.matched["identity"] += 1
            return {"device": "<device>", "inode": "<inode>"}
        return self(item)


def project(obj: dict) -> tuple[dict, list]:
    """Remove the post-base additions; return the removed values for the null check."""
    obj, removed = copy.deepcopy(obj), []
    if obj["object"] == "file_start":
        for key in ADDED_FILE_START_FIELDS:
            removed.append(obj.pop(key))
        for field in ADDED_PROVENANCE:
            obj["provenance_defaults"].pop(field)
        for field, (current, base) in CHANGED_PROVENANCE.items():
            assert obj["provenance_defaults"][field]["native_paths"] == current, field
            obj["provenance_defaults"][field]["native_paths"] = base
    if obj["object"] == "index_event":
        for result in obj.get("results") or []:
            for key in ADDED_RESULT_FIELDS:
                removed.append(result.pop(key))
        for field in ADDED_PROVENANCE:  # Claude never overrides an added field's default.
            assert field not in obj["provenance"], field
        if obj["compaction"] is not None:
            for key in ADDED_COMPACTION_KEYS:
                removed.append(obj["compaction"].pop(key))
    return obj, removed


def frame(path: Path, text: bool):
    """Yield framed objects for one file; the caller collects until any raise."""
    info = path.stat()
    request = {"id": 1, "extract": "index", "roots": [], "cross_file": False, "text": text,
               "raw": False, "files": [{"path": str(path), "size": info.st_size,
                                        "identity": {"device": info.st_dev, "inode": info.st_ino}}]}
    from harness_evidence import revision
    envelope = {"schema": SCHEMA, "decoder": {"version": DECODER_VERSION, "revision": revision()}}
    return index_stream.objects(request, envelope)


def observe(normalize: Normalizer):
    """Every index sample, text on and off: completing digests and expected failures."""
    completing, failing, removed = {}, {}, []
    for sample in samples():
        name = sample["path"]
        path = CATALOGUE.parent / name
        for text in (True, False):
            raw, error = [], None
            try:
                for obj in frame(path, text):
                    raw.append(obj)
            except Exception as raised:  # noqa: BLE001 - the catalogue names the expected type
                error = raised
            emitted = []
            for obj in raw:  # Projection runs outside the decode so its faults are not samples'.
                obj, gone = project(obj)
                if name not in ADDED_SAMPLES:  # An added sample's values are its own tests'.
                    removed.extend(gone)
                emitted.append(normalize(obj))
            mode = "text" if text else "notext"
            if error is None:
                completing.setdefault(name, {})[mode] = canonical(emitted)
            else:
                failing.setdefault(name, {})[mode] = {"type": type(error).__name__,
                                                      "prefix": canonical(emitted)}
    return completing, failing, removed


# The capabilities fields entry each post-base addition creates for Claude.
ADDED_CAPABILITY_FIELDS = {"results[].exit_code": {"coverage_keys": [], "provenance": []}}


def claude_capability_blocks():
    """The whole Claude harness block, with the post-base fields entries projected out."""
    claude = json.loads(CAPABILITIES.read_text(encoding="utf-8"))["harnesses"]["claude-code"]
    for field, entry in ADDED_CAPABILITY_FIELDS.items():
        assert claude["fields"].pop(field) == entry, field
    for field, (current, base) in CHANGED_PROVENANCE.items():
        assert claude["fields"][field]["provenance"] == sorted(current), field
        claude["fields"][field]["provenance"] = sorted(base)
    for version in ADDED_SAMPLE_VERSIONS:
        assert claude["versions"].pop(version)["synthetic"] == list(ADDED_SAMPLES), version
    for kind in ADDED_RECORD_KINDS:
        claude["record_kinds"].remove(kind)
    for kind, paths in CHANGED_UNWATCHED.items():
        unwatched = claude["index"]["unwatched"][kind]
        for path, (current, base) in paths.items():
            assert unwatched.pop(path) == current, (kind, path)
            if base is not None:
                unwatched[path] = base
    return {"index": canonical(claude["index"]), "header": canonical(claude["header"]),
            "harness": canonical(claude)}


def compute():
    normalize = Normalizer()
    completing, failing, removed = observe(normalize)
    return {"base": "3e346e267d6230ccee3c90f4ebc618c44449c0d5",
            "normalization": list(RULES), "completing": completing, "failing": failing,
            "capabilities": claude_capability_blocks()}, normalize, removed


def _all_strings(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _all_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _all_strings(item)
    elif isinstance(value, str):
        yield value


def test_catalogue_partitions_index_samples_into_completing_and_expected_failures():
    expected = [s for s in samples() if s.get("index_error")]
    assert len(samples()) - len(expected) > 0 and expected
    observed, _, _ = compute()
    for sample in samples():
        name = sample["path"]
        if sample.get("index_error"):
            assert name not in observed["completing"], name
            for mode in ("text", "notext"):
                assert observed["failing"][name][mode]["type"] == sample["index_error"], (name, mode)
        else:
            assert name not in observed["failing"], name
            assert set(observed["completing"][name]) == {"text", "notext"}


def test_claude_index_stream_matches_base_digests():
    golden = json.loads(DIGESTS.read_text(encoding="utf-8"))
    observed, normalize, removed = compute()
    assert observed["normalization"] == golden["normalization"]
    assert all(normalize.matched[rule] for rule in RULES), normalize.matched
    # An added sample has no base digest; its own tests cover its stream.
    assert {k: v for k, v in observed["completing"].items() if k not in ADDED_SAMPLES} \
        == golden["completing"]
    assert observed["failing"] == golden["failing"]
    assert observed["capabilities"] == golden["capabilities"]
    assert all(value is None for value in removed)


def test_normalized_stream_holds_no_checkout_or_home_path():
    normalize = Normalizer()
    checkout, home = str(TOOLS.parent.resolve()), os.path.expanduser("~")
    for sample in samples():
        path = CATALOGUE.parent / sample["path"]
        raw = []
        try:
            for obj in frame(path, True):
                raw.append(obj)
        except Exception:  # noqa: BLE001 - expected failures are checked above
            pass
        emitted = [normalize(project(obj)[0]) for obj in raw]
        for value in _all_strings(emitted):
            assert checkout not in value and home not in value, (sample["path"], value)


def test_registry_refuses_a_harness_without_an_adapter():
    import pytest
    from harness_evidence import index_adapters
    from harness_evidence._protocol import ProtocolError
    assert sorted(index_adapters.ADAPTERS) == ["agy", "claude-code"]
    home = CATALOGUE.parent / "home"
    codex = home / ".codex/sessions/2026/10/08"
    path = next(codex.glob("rollout-*.jsonl"))
    info = path.stat()
    request = {"id": 1, "extract": "index", "cross_file": False, "text": False, "raw": False,
               "roots": [{"harness": "codex", "path": str(home / ".codex/sessions")}],
               "files": [{"path": str(path), "size": info.st_size,
                          "identity": {"device": info.st_dev, "inode": info.st_ino}}]}
    envelope = {"schema": SCHEMA, "decoder": {"version": DECODER_VERSION, "revision": "r"}}
    with pytest.raises(ProtocolError, match="^no index adapter for codex$"):
        list(index_stream.objects(request, envelope))


def test_claude_declares_the_shared_additions_absent():
    from harness_evidence.index_adapters import ADAPTERS
    declaration = ADAPTERS["claude-code"].provenance_defaults()["results[].exit_code"]
    assert declaration == {"native_paths": [], "coverage_keys": [], "basis": "native",
                           "rule": "absent:not_decoded"}
    sample = CATALOGUE.parent / "index/sizes.jsonl"
    out = list(frame(sample, True))
    assert out[0]["object"] == "file_start" and out[0]["side_inputs"] is None
    results = [r for o in out if o["object"] == "index_event" for r in o.get("results") or []]
    assert results and all(r["exit_code"] is None for r in results)


if __name__ == "__main__":
    if sys.argv[1:] != ["--write"]:
        sys.exit("usage: test_harness_evidence_index_adapters.py --write")
    value, normalize, _ = compute()
    if not all(normalize.matched.values()):
        sys.exit(f"a normalization rule matched nothing: {normalize.matched}")
    DIGESTS.write_text(json.dumps(value, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    print(f"{len(value['completing'])} completing, {len(value['failing'])} failing -> {DIGESTS}")
