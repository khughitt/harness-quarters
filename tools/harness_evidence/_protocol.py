"""Shared request validation for reader and incremental index transports."""
import re


class ProtocolError(Exception):
    """The request, rather than a source file, violates the wire contract."""


def _fields(value, allowed, required=()):
    if not isinstance(value, dict) or value.keys() - set(allowed) or set(required) - value.keys():
        raise ProtocolError("invalid object fields")


def _integer(value, minimum):
    if type(value) is not int or value < minimum:
        raise ProtocolError("expected an integer in range")


def _path(value):
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ProtocolError("expected a nonempty path string")


def validate(value):
    """Reject the complete request before any response for it is emitted."""
    _fields(value, {"id", "files", "roots", "context", "cross_file", "text", "raw", "extract"}, {"id", "files"})
    if type(value["id"]) is not int:
        raise ProtocolError("id must be an integer")
    if not isinstance(value["files"], list):
        raise ProtocolError("files must be an array")
    index = value.get("extract") == "index"
    if "extract" in value and not index:
        raise ProtocolError("unsupported extraction profile")
    if index and (value.get("cross_file", False) or value.get("raw", False) or value.get("context")):
        raise ProtocolError("index extraction requires cross_file:false, raw:false and no context")
    for file in value["files"]:
        allowed = {"path", "read_path", "size", "state"} | ({"identity"} if index else set())
        _fields(file, allowed, {"path", "size"} | ({"identity"} if index else set()))
        if index:
            _fields(file["identity"], {"device", "inode"}, {"device", "inode"})
            for number in file["identity"].values():
                _integer(number, 0)
        _path(file["path"])
        if file.get("read_path") is not None:
            _path(file["read_path"])
        _integer(file["size"], 0)
        state = file.get("state")
        if state is not None:
            state_fields = {"next_line", "next_offset", "digest"} | ({"index"} if index else set())
            _fields(state, state_fields, state_fields)
            if index and not isinstance(state["index"], dict):
                raise ProtocolError("opaque index state must be an object")
            _integer(state["next_line"], 1)
            _integer(state["next_offset"], 0)
            if not isinstance(state["digest"], str) or re.fullmatch("[0-9a-f]{64}", state["digest"]) is None:
                raise ProtocolError("invalid checkpoint digest")
    roots = value.get("roots")
    if roots is not None:
        if not isinstance(roots, list):
            raise ProtocolError("roots must be an array or null")
        for root in roots:
            _fields(root, {"harness", "path"}, {"harness", "path"})
            if root["harness"] not in ("claude-code", "codex"):
                raise ProtocolError("unsupported root harness")
            _path(root["path"])
    if not isinstance(value.get("context", []), list):
        raise ProtocolError("context must be an array")
    for path in value.get("context", []):
        _path(path)
    for key in ("cross_file", "text", "raw"):
        if type(value.get(key, False)) is not bool:
            raise ProtocolError(f"{key} must be boolean")
    return value
