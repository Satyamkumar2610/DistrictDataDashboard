"""The web platform's colour tokens must stay legible in both themes.

Two bars, because WCAG sets two and the app uses its tokens for two different jobs:

- **Text (4.5:1).** Tokens the UI renders words in, read on either ground: the page (`--bg`) or a
  raised surface (`--surface`: the topbar, panels, inputs, the atlas side panel). Status colours
  count -- `.chip.good/.warn/.crit` colour their *label*, not just their border.
- **Meaningful graphics (3:1).** Tokens that encode a fact in a map fill, a chart series or a legend
  swatch, read against `--surface` (the legend box and chart panels are surface-filled).

Deliberately not checked:

- `neutral` is the *absence* of a classification -- the map fill for a district no rule matched. It
  is meant to recede, and nothing is read from it alone, so a contrast floor would be wrong.
- `line` / `line-strong` are hairlines, not text and not meaning-bearing: the app never encodes a
  fact in a border alone (a chip states its status in words beside the colour).
- `gain` vs `loss` sit at near-equal lightness by design: it is a diverging scale, where hue carries
  the direction (gained/lost) and lightness carries the magnitude, through a neutral midpoint.
  Checked instead by `test_the_diverging_map_scale_survives_colour_blindness`.
"""

from __future__ import annotations

import re

import pytest

from district_evolution import core

THEME_CSS = core.PROJECT_ROOT / "web" / "src" / "theme.css"
AA_TEXT = 4.5
AA_GRAPHIC = 3.0
TEXT_TOKENS = ["ink", "ink-2", "muted", "accent", "good", "warn", "crit"]
GRAPHIC_TOKENS = ["new", "out", "in", "gain", "loss", "ochre"]
GROUNDS = ["bg", "surface"]
THEMES = ["light", "dark"]

# Viénot (1999) dichromat simulation matrices, applied in linear RGB.
DICHROMATS = {
    "deuteranopia": ((0.625, 0.375, 0.0), (0.7, 0.3, 0.0), (0.0, 0.3, 0.7)),
    "protanopia": ((0.1115, 0.8885, 0.0), (0.1115, 0.8885, 0.0), (0.004, 0.0, 0.996)),
    "tritanopia": ((0.95, 0.05, 0.0), (0.0, 0.433, 0.567), (0.0, 0.475, 0.525)),
}
# A gained/lost district must stay tellable apart for a dichromat: this is the smallest
# per-channel difference (0-255) we accept after simulation. Measured on 4.0.0: 113-162.
MIN_DICHROMAT_SEPARATION = 60


def _channel(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _rgb(hex_colour: str) -> tuple[int, int, int]:
    h = hex_colour.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def luminance(hex_colour: str) -> float:
    r, g, b = _rgb(hex_colour)
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def simulate(hex_colour: str, matrix) -> str:
    """The colour as a dichromat sees it (linear-RGB transform, back to sRGB hex)."""
    def to_linear(c: float) -> float:
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    def to_srgb(c: float) -> int:
        c = min(1.0, max(0.0, c))
        return round(255 * (12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055))

    v = [to_linear(c) for c in _rgb(hex_colour)]
    return "#" + "".join(f"{to_srgb(sum(row[i] * v[i] for i in range(3))):02x}" for row in matrix)


def separation(a: str, b: str) -> int:
    return max(abs(x - y) for x, y in zip(_rgb(a), _rgb(b), strict=True))


def themes() -> dict[str, dict[str, str]]:
    """{theme: {token: '#hex'}} from the `:root` and `:root[data-theme="dark"]` blocks."""
    css = THEME_CSS.read_text(encoding="utf-8")
    out: dict[str, dict[str, str]] = {}
    for selector, theme in ((r":root\s*\{", "light"), (r':root\[data-theme="dark"\]\s*\{', "dark")):
        block = re.search(selector + r"([^}]*)\}", css)
        assert block, f"no {theme} token block in {THEME_CSS}"
        out[theme] = dict(re.findall(r"--([a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{6})", block.group(1)))
    return out


@pytest.fixture(scope="module")
def tokens() -> dict[str, dict[str, str]]:
    return themes()


def test_both_themes_define_every_token(tokens):
    assert set(tokens["light"]) == set(tokens["dark"]), "a token is missing from one theme"
    named = set(TEXT_TOKENS) | set(GRAPHIC_TOKENS) | set(GROUNDS)
    assert named <= set(tokens["light"]), f"not defined: {sorted(named - set(tokens['light']))}"


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("ground", GROUNDS)
@pytest.mark.parametrize("token", TEXT_TOKENS)
def test_text_reaches_aa_on_every_ground(tokens, theme, ground, token):
    fg, bg = tokens[theme][token], tokens[theme][ground]
    ratio = contrast(fg, bg)
    assert ratio >= AA_TEXT, f"--{token} ({fg}) on --{ground} ({bg}), {theme}: {ratio:.2f}:1 < {AA_TEXT}:1"


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("token", GRAPHIC_TOKENS)
def test_meaningful_graphics_reach_the_non_text_bar(tokens, theme, token):
    """A legend swatch or chart series is read against the surface it sits on."""
    fg, bg = tokens[theme][token], tokens[theme]["surface"]
    ratio = contrast(fg, bg)
    assert ratio >= AA_GRAPHIC, f"--{token} ({fg}) on --surface ({bg}), {theme}: {ratio:.2f}:1 < {AA_GRAPHIC}:1"


@pytest.mark.parametrize("theme", THEMES)
def test_text_on_an_accent_filled_surface_reaches_aa(tokens, theme):
    """The primary button fills with --accent and labels it --accent-ink."""
    ratio = contrast(tokens[theme]["accent-ink"], tokens[theme]["accent"])
    assert ratio >= AA_TEXT, f"--accent-ink on --accent, {theme}: {ratio:.2f}:1"


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("kind", sorted(DICHROMATS))
def test_the_diverging_map_scale_survives_colour_blindness(tokens, theme, kind):
    """Gained vs lost area is the one place the map asks a reader to tell two hues apart."""
    gain = simulate(tokens[theme]["gain"], DICHROMATS[kind])
    loss = simulate(tokens[theme]["loss"], DICHROMATS[kind])
    apart = separation(gain, loss)
    assert apart >= MIN_DICHROMAT_SEPARATION, (
        f"--gain/--loss in {theme} under {kind}: {gain} vs {loss}, {apart} apart "
        f"(< {MIN_DICHROMAT_SEPARATION}); the atlas change scale would read as one colour")
