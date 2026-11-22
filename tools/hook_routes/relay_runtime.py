"""Run exported relay operations against one binding's pinned installation."""
import json
import os
from pathlib import Path
import subprocess

__all__ = ["call", "package_for", "budget_payload"]


def package_for(table, version, home):
    runtime = table.runtimes[version]
    _, filename = runtime.argv(home)
    script = Path(filename)
    if not script.is_file():
        raise ValueError(f"missing relay runtime {script}")
    package = script.parent.parent
    manifest = json.loads((package / "package.json").read_bytes())
    if (manifest["name"] != "relay" or f"v{manifest['version']}" != version
            or package / manifest["bin"]["relay"] != script):
        raise ValueError(f"{script}: expected the {version} relay package bin")
    lock = package.parents[1] / "package-lock.json"
    installed = json.loads(lock.read_bytes())["packages"]["node_modules/relay"]
    if (installed["resolved"].rpartition("#")[2] != runtime.commit
            or f"v{installed['version']}" != version):
        raise ValueError(f"{lock}: installed relay identity differs from {version} at {runtime.commit}")
    return package


def budget_payload(home, binding, line, data, *, tool=None):
    return dict(harness=home.harness, event=line.relay_event or binding.event, outerMs=line.outer_ms,
                config=json.loads(data), tool=tool)


def call(runtime: Path, op: str, payload: dict, *, timeout_s: float = 10) -> dict:
    try:
        result = subprocess.run(
            ["/usr/bin/node", Path(__file__).with_name("relay_call.mjs"), runtime, op],
            input=json.dumps(payload), capture_output=True, text=True, timeout=timeout_s,
            env={"PATH": os.defpath, "HOME": str(Path.home())},
        )
    except subprocess.TimeoutExpired as error:
        raise ValueError(f"relay {op} exceeded {timeout_s} seconds") from error
    if result.returncode:
        raise ValueError(f"relay {op}: {result.stderr.strip() or result.returncode}")
    return json.loads(result.stdout)
