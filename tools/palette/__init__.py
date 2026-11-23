"""Reader for palette.toml, the guild's harness, model-family and status colours.

Contract: docs/palette.md. `load` validates the whole file and raises PaletteError on
anything it does not expect; lookups return None for an identity the palette does not
colour, never a guessed colour."""
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

__all__ = ["PATH", "Colour", "Match", "Palette", "PaletteError", "Role", "load"]

PATH = Path(__file__).resolve().parents[2] / "palette.toml"
VERSION = 1
MATCHES = ("family", "vendor", "none")


class PaletteError(ValueError):
    """palette.toml breaks its contract."""


@dataclass(frozen=True)
class Colour:
    rgb: tuple[int, int, int]
    xterm: int
    oklch: tuple[float, float, float]


@dataclass(frozen=True)
class Role:
    colour: Colour | None   # None for an SGR-only role
    sgr: str
    meaning: str


@dataclass(frozen=True)
class Match:
    """How a raw model id resolved: a family key, a vendor name, or nothing."""
    key: str | None
    how: str                # one of MATCHES
    colour: Colour | None


@dataclass(frozen=True)
class Palette:
    harnesses: dict[str, Colour]
    aliases: dict[str, str]                 # alias -> harness name
    vendors: dict[str, tuple[str, Colour]]  # prefix -> (vendor name, fallback colour)
    families: dict[str, str]                # family token -> model key
    models: dict[str, Colour]               # model key -> colour
    roles: dict[str, Role]
    cases: tuple[tuple[str, str, str], ...]  # (raw, expect, match)

    def harness(self, name: str) -> Colour | None:
        return self.harnesses.get(self.aliases.get(name, name))

    def model(self, raw: str | None) -> Match:
        """First token naming a vendor prefix selects the vendor, and the first later token
        naming one of its families selects the family; an id that starts with a family
        token (a renderer that stripped the vendor) selects that family."""
        tokens = (raw or "").lower().split("-")
        if tokens[0] in self.vendors:
            vendor, fallback = self.vendors[tokens[0]]
            for token in tokens[1:]:
                key = f"{tokens[0]}-{token}"
                if key in self.models:
                    return Match(key, "family", self.models[key])
            return Match(vendor, "vendor", fallback)
        if tokens[0] in self.families:
            key = self.families[tokens[0]]
            return Match(key, "family", self.models[key])
        return Match(None, "none", None)


def load(path: Path = PATH) -> Palette:
    try:
        data = tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise PaletteError(f"{path}: {error}") from None
    _keys(data, "palette", required={"version", "harness", "vendor", "model", "role", "case"})
    if data["version"] != VERSION:
        raise PaletteError(f"version {data['version']!r} is not {VERSION}")
    harnesses, aliases = {}, {}
    for name, entry in data["harness"].items():
        _keys(entry, f"harness.{name}", required={"aliases", "rgb", "xterm", "oklch"})
        harnesses[name] = _colour(entry, f"harness.{name}")
        for alias in _strings(entry["aliases"], f"harness.{name}.aliases"):
            if alias in aliases or alias in data["harness"]:
                raise PaletteError(f"harness alias {alias!r} is not unique")
            aliases[alias] = name
    vendors, names = {}, {}
    for name, entry in data["vendor"].items():
        _keys(entry, f"vendor.{name}", required={"prefix", "rgb", "xterm", "oklch"})
        prefix = _token(entry["prefix"], f"vendor.{name}.prefix")
        if prefix in vendors:
            raise PaletteError(f"vendor prefix {prefix!r} is not unique")
        vendors[prefix] = (name, _colour(entry, f"vendor.{name}"))
        names[name] = prefix
    families, models = {}, {}
    for key, entry in data["model"].items():
        _keys(entry, f"model.{key}", required={"vendor", "family", "rgb", "xterm", "oklch"})
        if entry["vendor"] not in names:
            raise PaletteError(f"model.{key}: unknown vendor {entry['vendor']!r}")
        family = _token(entry["family"], f"model.{key}.family")
        if key != f"{names[entry['vendor']]}-{family}":
            raise PaletteError(f"model.{key}: key is not {names[entry['vendor']]}-{family}")
        if family in families or family in vendors:
            raise PaletteError(f"model family {family!r} is not unique")
        families[family] = key
        models[key] = _colour(entry, f"model.{key}")
    roles = {}
    for name, entry in data["role"].items():
        colour_keys = {"rgb", "xterm", "oklch"}
        has_colour = bool(colour_keys & entry.keys())
        _keys(entry, f"role.{name}", required={"sgr", "meaning"} | (colour_keys if has_colour else set()))
        if not re.fullmatch(r"(\d+(;\d+)*)?", entry["sgr"]) or not (has_colour or entry["sgr"]):
            raise PaletteError(f"role.{name}: sgr {entry['sgr']!r} is not SGR parameters")
        roles[name] = Role(_colour(entry, f"role.{name}") if has_colour else None, entry["sgr"],
                           _strings([entry["meaning"]], f"role.{name}.meaning")[0])
    cases = []
    for index, entry in enumerate(data["case"]):
        _keys(entry, f"case[{index}]", required={"raw", "expect", "match"})
        raw, expect, how = _strings([entry["raw"], entry["expect"], entry["match"]], f"case[{index}]")
        if how not in MATCHES:
            raise PaletteError(f"case[{index}]: match {how!r} is not one of {MATCHES}")
        cases.append((raw, expect, how))
    return Palette(harnesses, aliases, vendors, families, models, roles, tuple(cases))


def _keys(entry: object, where: str, required: set[str]) -> None:
    if not isinstance(entry, dict):
        raise PaletteError(f"{where} is not a table")
    if missing := required - entry.keys():
        raise PaletteError(f"{where}: missing {sorted(missing)}")
    if extra := entry.keys() - required:
        raise PaletteError(f"{where}: unknown {sorted(extra)}")


def _strings(values: object, where: str) -> list[str]:
    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
        raise PaletteError(f"{where} is not a list of strings")
    return values


def _token(value: object, where: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9.]+", value):
        raise PaletteError(f"{where}: {value!r} is not a lowercase token without '-'")
    return value


def _colour(entry: dict, where: str) -> Colour:
    rgb, xterm, oklch = entry["rgb"], entry["xterm"], entry["oklch"]
    if not isinstance(rgb, str) or not re.fullmatch(r"#[0-9a-f]{6}", rgb):
        raise PaletteError(f"{where}: rgb {rgb!r} is not #rrggbb")
    if type(xterm) is not int or not 16 <= xterm <= 255:
        raise PaletteError(f"{where}: xterm {xterm!r} is not an integer in 16..255")
    if (not isinstance(oklch, list) or len(oklch) != 3
            or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in oklch)):
        raise PaletteError(f"{where}: oklch {oklch!r} is not [lightness, chroma, hue]")
    return Colour((int(rgb[1:3], 16), int(rgb[3:5], 16), int(rgb[5:7], 16)), xterm,
                  (float(oklch[0]), float(oklch[1]), float(oklch[2])))
