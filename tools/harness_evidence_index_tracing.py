"""Parse transcript lines with every record wrapped, so each field read is logged as
(kind of the record the object came from, dotted path). List items add `[]`."""

import json
import types


class TracedDict(dict):
    def __init__(self, data, path, kind, log):
        super().__init__({key: _trace(value, _join(path, key), kind, log)
                          for key, value in data.items()})
        self._path, self._kind, self._log = path, kind, log

    def _read(self, key):
        self._log.add((self._kind, _join(self._path, key)))

    def get(self, key, default=None):
        self._read(key)
        return dict.get(self, key, default)

    def __getitem__(self, key):
        self._read(key)
        return dict.__getitem__(self, key)

    def __contains__(self, key):
        self._read(key)
        return dict.__contains__(self, key)


def _join(path, key):
    return f"{path}.{key}" if path else str(key)


def _trace(value, path, kind, log):
    if isinstance(value, dict):
        return TracedDict(value, path, kind, log)
    if isinstance(value, list):
        return [_trace(item, f"{path}[]", kind, log) for item in value]
    return value


def traced_extract(lines, state=None, *, place, text=True):
    """Trace actual extractor descendants, including labels and coverage reads."""
    from harness_evidence import index_events
    log = set()
    current = {"next_record": True, "kind": None}
    original = index_events.json

    def loads(value, **options):
        record = json.loads(value, **options)
        if not isinstance(record, dict):
            return record
        if current["next_record"]:
            current.update(next_record=False, kind=str(record.get("type")))
            traced = _trace(record, "", current["kind"], log)
            return traced
        # The extractor's JSON-valued native tool input is a descendant read too.
        return _trace(record, "message.content[].input", current["kind"], log)

    def traced_lines():
        for line in lines:
            current["next_record"] = True
            yield line

    index_events.json = types.SimpleNamespace(loads=loads, dumps=json.dumps,
                                              JSONDecodeError=json.JSONDecodeError)
    try:
        list(index_events.extract(traced_lines(), {} if state is None else state, place=place, text=text))
    finally:
        index_events.json = original
    return log


def covered(path, declared):
    """A read is covered by a declared path it equals, or by one it is a container of
    (read on the way to that path). A declared path never covers its descendants."""
    return any(path == item or item.startswith(path + ".") or item.startswith(path + "[]")
               for item in declared)


def declared(adapter, kind):
    spec = adapter.WATCHED.get(kind, {"sources": ()})
    return (*adapter.COMMON_READS, *spec["sources"], *adapter.UNWATCHED.get(kind, {}))


def feeds_valid(adapter):
    """Each `feeds` key is a source of its kind and each target an applied input."""
    targets = {f"applied:{site}/input:{name}" for site, names in adapter.APPLIED.items()
               for name in names}
    return [f"{kind} {path} -> {target}" for kind, spec in adapter.WATCHED.items()
            for path, feeds in spec.get("feeds", {}).items() for target in feeds
            if path not in spec["sources"] or target not in targets]


def reasons_valid(adapter):
    """Each unwatched read names a valid reason, or a tuple of them when the parser
    reads the path at more than one site."""
    allowed = {"dimension", "flag", *(f"applied:{site}" for site in adapter.APPLIED)}
    return [f"{kind} {path}: {reason}" for kind, paths in adapter.UNWATCHED.items()
            for path, reason in paths.items()
            if not set(reason if isinstance(reason, tuple) else (reason,)) <= allowed
            or reason == ()]
