"""Colour for `hq sessions`: class hues and a continuous age colormap.

Colours are defined in OKLCH and kept inside the lightness band where text reads at
3:1 or better on both a dark and a light terminal background. Output is 24-bit when
COLORTERM says the terminal takes it; otherwise each colour has a hand-picked xterm-256
stand-in from the entries that pass the same check. A project's colour comes from its
tasks config; its stand-in is derived by the source's rule (ops bin/project-colors): the
xterm-256 entry nearest in OKLab among those that pass that check."""
import math
import re
from dataclasses import dataclass

RGB = tuple[int, int, int]

# Age scale: log-spaced from a minute to 90 days; older rows take the oldest colour.
AGE_MIN_S = 60
AGE_MAX_S = 90 * 86_400
# One hue, newest vivid and lighter, oldest near gray and darker (OKLCH L, C).
AGE_HUE = 175
AGE_NEW = (0.65, 0.10)
AGE_OLD = (0.52, 0.015)


def oklch(lightness: float, chroma: float, hue: float) -> RGB:
    a = chroma * math.cos(math.radians(hue))
    b = chroma * math.sin(math.radians(hue))
    l_ = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    linear = (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
              -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
              -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)
    r, g, b = (round(255 * encode(min(1.0, max(0.0, c)))) for c in linear)
    return r, g, b


def encode(linear: float) -> float:
    return 12.92 * linear if linear <= 0.0031308 else 1.055 * linear ** (1 / 2.4) - 0.055


def decode(channel: int) -> float:
    c = channel / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def oklab(rgb: RGB) -> tuple[float, float, float]:
    r, g, b = (decode(c) for c in rgb)
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def contrast(a: RGB, b: RGB) -> float:
    def luminance(rgb: RGB) -> float:
        r, g, b = (decode(c) for c in rgb)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    low, high = sorted((luminance(a), luminance(b)))
    return (high + 0.05) / (low + 0.05)


DARK = (0x1E, 0x1E, 0x1E)
LIGHT = (0xFF, 0xFF, 0xFF)
CUBE = (0, 95, 135, 175, 215, 255)


def xterm256(index: int) -> RGB:
    if index >= 232:
        gray = 8 + 10 * (index - 232)
        return gray, gray, gray
    index -= 16
    return CUBE[index // 36], CUBE[index // 6 % 6], CUBE[index % 6]


LEGIBLE_256 = [i for i in range(16, 256)
               if contrast(xterm256(i), DARK) >= 3 and contrast(xterm256(i), LIGHT) >= 3]


def stand_in(rgb: RGB) -> int:
    """Nearest in OKLab, ties to the lower index, as the source derives it."""
    lab = oklab(rgb)
    return min(LEGIBLE_256, key=lambda i: (math.dist(lab, oklab(xterm256(i))), i))


@dataclass(frozen=True)
class Colour:
    rgb: RGB
    index: int   # the xterm-256 stand-in


def project_colour(text: str) -> Colour:
    """A project's `#rrggbb`, lowercase as tasks' JSON carries it; ValueError for anything else."""
    if not isinstance(text, str) or not re.fullmatch(r"#[0-9a-f]{6}", text):
        raise ValueError(f"{text!r} is not #rrggbb")
    rgb = (int(text[1:3], 16), int(text[3:5], 16), int(text[5:7], 16))
    return Colour(rgb, stand_in(rgb))


CLAUDE = Colour(oklch(0.68, 0.14, 55), 166)
CODEX = Colour(oklch(0.66, 0.12, 245), 32)
WORK = Colour(oklch(0.64, 0.16, 335), 169)
MISSING = Colour(oklch(0.62, 0.17, 25), 160)
# The age ramp in xterm-256, in equal steps of the log scale (under ~10m, 2h, 20h, 9d,
# older). No legible vivid teal there is lighter than the grays, so the ladder falls in
# chroma, from teal to gray, and the two grays fall in lightness. They are close (3.5
# OKLab dE), but the next darker gray, 241, is under 3:1 on a dark background.
AGE_LADDER = (29, 30, 66, 243, 242)


def age_position(age_s: float) -> float:
    """0 for a minute old or newer, 1 for AGE_MAX_S or older, log-linear between."""
    if age_s <= AGE_MIN_S:
        return 0.0
    return min(1.0, math.log(age_s / AGE_MIN_S) / math.log(AGE_MAX_S / AGE_MIN_S))


def age_colour(age_s: float) -> Colour:
    t = age_position(age_s)
    rgb = oklch(AGE_NEW[0] + t * (AGE_OLD[0] - AGE_NEW[0]), AGE_NEW[1] + t * (AGE_OLD[1] - AGE_NEW[1]), AGE_HUE)
    return Colour(rgb, AGE_LADDER[min(len(AGE_LADDER) - 1, int(t * len(AGE_LADDER)))])


DIM = "2"
BOLD = "1"


@dataclass(frozen=True)
class Painter:
    """Wraps text in SGR codes; `depth` None paints nothing."""
    depth: str | None   # None, "truecolor" or "256"

    def fg(self, colour: Colour) -> str:
        if self.depth == "truecolor":
            return "38;2;{};{};{}".format(*colour.rgb)
        return f"38;5;{colour.index}"

    def age(self, age_s: float) -> str:
        return self.fg(age_colour(age_s))

    def paint(self, text: str, *params: str) -> str:
        if self.depth is None or not text or not params:
            return text
        return f"\x1b[{';'.join(params)}m{text}\x1b[0m"


def painter(when: str, isatty: bool, environ: dict[str, str]) -> Painter:
    """`always` and `never` win; `auto` paints a terminal unless NO_COLOR is set."""
    on = when == "always" or (when == "auto" and isatty and not environ.get("NO_COLOR"))
    if not on:
        return Painter(None)
    return Painter("truecolor" if environ.get("COLORTERM") in ("truecolor", "24bit") else "256")
