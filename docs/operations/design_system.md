# The design system

The web platform's visual language — colours, type, spacing, radii — lives in one file,
`web/src/theme.css`. Everything else is derived from it:

| Where | What | Kept in sync by |
|---|---|---|
| `web/src/theme.css` | the tokens themselves, as CSS custom properties, light and dark | the source of truth |
| `tests/test_theme_contrast.py` | the contrast rules, parsed straight from that file | runs on every build |
| Design System artifact | the same tokens with a usage note each, the brand book, the fonts, a cover | republished by hand when tokens change |
| Design (canvas) artifact | the eight screens as a clickable prototype, built on those tokens | redrawn by hand when the layout changes |

The artifacts are private to the repository owner's Claude account. They are a design aid, not a build
input: nothing in the pipeline or the web app reads them, so they can go stale without breaking
anything — but a stale system is worse than none, so republish it in the same change that moves a
token.

## The rules the tokens must keep

`tests/test_theme_contrast.py` enforces two bars, because the tokens do two jobs:

- **4.5:1 — anything the UI sets text in** (`ink`, `ink-2`, `muted`, `accent`, `good`, `warn`,
  `crit`), measured on both grounds text actually sits on: `--bg` and `--surface`, in both themes.
  Status colours count: `.chip.good/.warn/.crit` colour their *label*, not just their border.
- **3:1 — a fill or swatch that carries meaning** (`new`, `out`, `in`, `gain`, `loss`, `ochre`),
  measured on `--surface`, where their legend swatch and chart series are read.

Two tokens are deliberately exempt, and the test records why:

- `neutral` is the *absence* of a classification — the map fill for a district no rule matched. It is
  meant to recede, and nothing is read from it alone.
- `gain` and `loss` sit at near-equal lightness **on purpose**. It is a diverging scale: hue carries
  the direction, lightness the magnitude, through a neutral midpoint. Darkening one to manufacture a
  lightness difference would break the scale. The test simulates deuteranopia, protanopia and
  tritanopia instead and requires the pair to stay at least 60 of 255 apart per channel (measured:
  113–162).

## Changing a token

1. Edit `web/src/theme.css`.
2. `pytest tests/test_theme_contrast.py`. If it fails, hold the hue and saturation and lower the
   lightness until it passes — the four corrections in 4.0.0 were all of that shape, so the palette
   still reads as the same palette.
3. Rebuild the app (`npm run build` in `web/`) and run the browser tests.
4. Republish the Design System artifact so its tokens and its measured ratios match the file again.

A new token needs a usage note saying what it *means*, not where it is used — the existing ones name a
fact about a district (`new` = first appearance, `out` = land leaving, `ochre` = restored after a gap).
A token nobody can write that sentence for is a colour, not a token.
