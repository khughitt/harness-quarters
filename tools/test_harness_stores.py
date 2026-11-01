"""The session-store adapter registry."""
import json
import os
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import harness_stores  # noqa: E402


def test_every_adapter_slug_is_a_declared_harness(tmp_path):
    clean_env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path)}
    declared = json.loads(subprocess.run([str(TOOLS / "harness-facts"), "list"], capture_output=True,
                                         text=True, check=True, env=clean_env).stdout)["harnesses"]
    assert {a.slug for a in harness_stores.ADAPTERS} <= set(declared)


def test_aliases_and_slugs_are_unique():
    assert len({a.alias for a in harness_stores.ADAPTERS}) == len(harness_stores.ADAPTERS)
    assert len({a.slug for a in harness_stores.ADAPTERS}) == len(harness_stores.ADAPTERS)


def test_claude_and_codex_order_and_values():
    assert [(a.alias, a.slug) for a in harness_stores.ADAPTERS[:2]] == [("claude", "claude-code"), ("codex", "codex")]
