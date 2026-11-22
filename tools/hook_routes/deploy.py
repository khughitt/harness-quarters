"""Publish immutable subscriber bytes below a host's private relay config base."""
from hashlib import sha256
import os
from pathlib import Path
import re
import tempfile

from .render import render_next, subscriber_address, subscriber_bytes
from .table import expand_path

__all__ = ["deploy", "live_files", "review_files", "reconcile_base"]

_ADDRESS = re.compile(r"(v\d+\.\d+\.\d+)(?:-([0-9a-f]{12}))?/relay/subscribers\.json")


def reconcile_base(table, home):
    source = table.subscriber_files[table.reconciliation_file]
    file = Path(expand_path(source.path, home))
    address = file.relative_to(home / ".config/relay").as_posix()
    if not _ADDRESS.fullmatch(address):
        raise ValueError(f"invalid reconciliation path: {file}")
    return file.parents[1]


def live_files(table, home):
    names = {table.reconciliation_file}
    names.update(line.subscriber_file for _, _, _, binding in table.bindings()
                 for line in binding.lines if line.kind == "relay")
    files = {}
    for name in sorted(names):
        source = table.subscriber_files[name]
        data = subscriber_bytes(table, source, home)
        address = subscriber_address(source, data, home)
        if address in files and files[address] != data:
            raise ValueError(f"conflicting subscriber files at {address}")
        files[address] = data
    return files


def review_files(table, home, directory):
    rendered = render_next(table, home)
    for name, data in rendered.items():
        path = directory / name
        if not path.resolve().is_relative_to(directory.resolve()) or path.read_bytes() != data:
            raise ValueError(f"{path}: reviewed bytes differ from render next")
    # Rendered settings and live templates never become deployment destinations.
    names = {line.subscriber_file for _, _, _, binding in table.bindings()
             for line in binding.target if line.kind == "relay"}
    names.add(table.reconciliation_next)
    files = {}
    for name in names & table.target_files.keys():
        source = table.target_files[name]
        data = subscriber_bytes(table, source, home)
        address = subscriber_address(source, data, home)
        files[address] = rendered[address]
    return files


def _private_directory(directory):
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError(f"invalid relay config directory: {directory}")
    if directory.stat().st_mode & 0o777 != 0o700:
        directory.chmod(0o700)


def deploy(files: dict[str, bytes], home: Path) -> list[Path]:
    root = home / ".config/relay"
    paths = []
    for address, data in files.items():
        match = _ADDRESS.fullmatch(address)
        if not match or (match[2] and match[2] != sha256(data).hexdigest()[:12]):
            raise ValueError(f"invalid subscriber address for these bytes: {address}")
        paths.append(root / address)
    for path, data in zip(paths, files.values()):
        root.parent.mkdir(mode=0o700, exist_ok=True)
        for directory in (root, path.parents[1], path.parent):
            _private_directory(directory)
        if not path.exists():
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".subscribers-") as pending:
                pending.write(data)
                pending.flush()
                try:
                    os.link(pending.name, path)
                except FileExistsError:
                    pass  # A concurrent publication must agree byte for byte.
        if path.is_symlink() or not path.is_file() or path.read_bytes() != data:
            raise ValueError(f"refusing to overwrite {path} with different content")
        if path.stat().st_mode & 0o777 != 0o600:
            path.chmod(0o600)
    return paths
