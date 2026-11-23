"""palette.toml: its reader, its ties to the harness manifest, and its legibility floor."""
import sys
import tomllib
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import harness_stores  # noqa: E402
import palette  # noqa: E402
import pytest  # noqa: E402
from hq_cli import color  # noqa: E402

DARK, LIGHT = (30, 30, 30), (255, 255, 255)
FLOOR = 3.0
PALETTE = palette.load()


def coloured():
    yield from (("harness", k, c) for k, c in PALETTE.harnesses.items())
    yield from (("vendor", name, c) for name, c in PALETTE.vendors.values())
    yield from (("model", k, c) for k, c in PALETTE.models.items())
    yield from (("role", k, r.colour) for k, r in PALETTE.roles.items() if r.colour)


def luminance(rgb):
    def linear(channel):
        v = channel / 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (linear(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(x, y):
    high, low = sorted((luminance(x), luminance(y)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def xterm_rgb(index):
    if index >= 232:
        gray = 8 + 10 * (index - 232)
        return gray, gray, gray
    steps = (0, 95, 135, 175, 215, 255)
    index -= 16
    return steps[index // 36], steps[index // 6 % 6], steps[index % 6]


@pytest.mark.parametrize("raw,expect,how", PALETTE.cases, ids=[c[0] or "empty" for c in PALETTE.cases])
def test_every_case_resolves_as_recorded(raw, expect, how):
    match = PALETTE.model(raw)
    assert (match.key or "", match.how) == (expect, how)
    assert (match.colour is None) == (how == "none")


def test_cases_cover_every_family_and_each_kind_of_match():
    families = {expect for _, expect, how in PALETTE.cases if how == "family"}
    assert families == set(PALETTE.models)
    assert {how for _, _, how in PALETTE.cases} == set(palette.MATCHES)


def test_harnesses_are_declared_and_aliases_follow_the_store_adapters():
    declared = tomllib.loads((TOOLS.parent / "harnesses.toml").read_text())["harnesses"]
    assert set(PALETTE.harnesses) <= set(declared)
    for adapter in harness_stores.ADAPTERS:
        assert PALETTE.harness(adapter.alias) == PALETTE.harness(adapter.slug) is not None
    assert PALETTE.harness("opencode") is None and PALETTE.harness("unknown") is None


def test_harness_colours_keep_the_existing_hq_identities():
    current = {"claude-code": color.CLAUDE, "codex": color.CODEX, "agy": color.AGY, "pi": color.PI}
    assert {k: (c.rgb, c.xterm) for k, c in PALETTE.harnesses.items()} == {
        k: (c.rgb, c.index) for k, c in current.items()}


@pytest.mark.parametrize("kind,name,colour", list(coloured()), ids=lambda v: v if isinstance(v, str) else "")
def test_rgb_matches_oklch_and_both_values_are_legible(kind, name, colour):
    assert colour.rgb == color.oklch(*colour.oklch)
    for rgb in (colour.rgb, xterm_rgb(colour.xterm)):
        assert min(contrast(rgb, DARK), contrast(rgb, LIGHT)) >= FLOOR


def test_xterm_stand_ins_are_distinct():
    indices = [c.xterm for _, _, c in coloured()]
    assert len(indices) == len(set(indices))


@pytest.mark.parametrize("edit,message", [
    (("version = 1", "version = 2"), "version 2"),
    (('rgb = "#d97e38"', 'rgb = "#D97E38"'), "is not #rrggbb"),
    (('vendor = "anthropic"', 'vendor = "acme"'), "unknown vendor"),
    (('family = "opus"', 'family = "sonnet"'), "is not claude-sonnet"),
    (('aliases = ["claude"]', 'aliases = ["claude"]\nshade = 1'), "unknown ['shade']"),
    (('match = "family"', 'match = "fuzzy"'), "is not one of"),
])
def test_load_refuses_a_file_that_breaks_the_contract(tmp_path, edit, message):
    text = palette.PATH.read_text()
    assert edit[0] in text
    path = tmp_path / "palette.toml"
    path.write_text(text.replace(edit[0], edit[1], 1))
    with pytest.raises(palette.PaletteError, match=message.replace("[", r"\[").replace("]", r"\]")):
        palette.load(path)
