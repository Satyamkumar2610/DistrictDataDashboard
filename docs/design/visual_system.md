# Visual system

The platform presents research data, so it should look like a statistical publication, not a product landing page.
This document records the system the stylesheet (`web/src/theme.css`) implements and why. It complements the
measured audit in `ui_overhaul.md`, which established the information architecture, contrast floors and touch targets.
None of those floors changed: `tests/test_theme_contrast.py` still enforces them.

## Principles

1. **Colour belongs to the data.** The interface is neutral ink on a warm off-white page, with one navy accent for
   links, focus and the current selection. Every other colour on screen encodes something in a chart or map.
2. **Rules, not boxes.** Hierarchy comes from type, spacing and hairline rules. Surfaces are flat: no drop shadows,
   no glow, no translucency. A shadow appears only on things that float above the page (menus, search results,
   tooltips), because there it tells you the element is temporary.
3. **Type leads.** IBM Plex Sans throughout. Headlines state the finding ("District count rose from 316 to 733"), not
   the topic. IBM Plex Mono is kept for identifiers, table names and codes; it is no longer used for labels.
4. **Motion only answers an action.** Page changes and the theme switch crossfade; the year selector glides to the
   chosen year. Nothing animates on its own, and reduced motion turns all of it off.

## What changed, and why

| Before | After | Reason |
|---|---|---|
| Radial teal glow behind the hero, frosted-glass search, captions and map controls | Flat surfaces with a hairline border | Glow and glass are decoration that reads as a template; translucency also lowers text contrast over the map |
| Every block a white card with a drop shadow; cards lift on hover | Hairline borders, no shadows; links underline on hover | A shadow implies elevation; on a page of figures it made everything compete equally |
| Key figures as boxed tiles | A ruled strip (2 px ink rule above, hairline dividers) with large proportional numerals | The convention of statistical bulletins; tabular figures are kept for table columns only |
| Mono uppercase "eyebrow" labels everywhere | Sans labels; the eyebrow is a short accent line above a headline | Tracked mono caps on every label is the most recognisable generated-UI pattern |
| Pill-shaped active nav, pill segmented buttons | Tab-style nav with a 2 px underline on the current page; rectangular segmented controls | Reads as navigation rather than as tags |
| ◐ glyph as the theme toggle | Sun / moon line icon with a stable accessible name and `aria-pressed` | A recognisable control, announced with its state |
| Circular "spreading" theme reveal | 180 ms crossfade | The reveal drew attention to the switch rather than the content |
| Shimmering gradient skeleton | Flat placeholder with a gentle opacity pulse | Same purpose, less motion |
| Inverted (ink) tooltips | Surface-coloured tooltip, hairline border, text colours | Matches the page in both themes; the series swatch carries identity, not the text colour |
| Charts only readable by hovering | Every figure offers **Show the data** (the same numbers as a table) | WCAG: no information only on hover; also the print and screen-reader form |

## Tokens

| Role | Light | Dark |
|---|---|---|
| Page (`--bg`) | `#f6f6f4` | `#0f1215` |
| Surface (`--surface`) | `#ffffff` | `#16191d` |
| Ink / secondary / muted | `#15181c` / `#454a51` / `#60666e` | `#e8eaed` / `#b9bec5` / `#8e959e` |
| Hairline / strong hairline | `#e1e1dc` / `#c4c4bd` | `#2a2f35` / `#3d434a` |
| Accent (links, focus, selection) | `#1f4f8a` | `#8db6ec` |
| Chart grid / axis | `#ecece8` / `#c4c4bd` | `#23272c` / `#3d434a` |
| Radius | 4 px controls, 6 px panels | same |

Status colours (`--good`, `--warn`, `--crit`) and the map's semantic colours (`--new`, `--out`, `--in`, `--gain`,
`--loss`) keep their values; they already passed the contrast and colour-blindness tests.

## Charts

Series colours are assigned by role, never cycled:

| Token | Light | Dark | Use |
|---|---|---|---|
| `--series-1` … `--series-4` | `#2a78d6` `#eb6834` `#6250d6` `#eda100` | `#3987e5` `#d95926` `#9085e9` `#c98500` | Categorical, in this order |
| `--series-base` | `#8a9097` | `#6e757d` | The context series when one series is the story (grey everything else); ≥ 3:1 on the surface, deliberately without chroma |
| `--ord-1` … `--ord-3` | `#184f95` `#3987e5` `#86b6ef` | `#cde2fb` `#5598e7` `#1c5cab` | Ordered categories, e.g. how exactly an event's area is known |

Validated with the colour-vision validator (adjacent pairs, OKLab ΔE ×100):

- Lineage kinds (slots 1–4): pass in both themes; worst adjacent CVD ΔE 24.7 (light) and 26.0 (dark); normal-vision
  ΔE ≥ 27. Slot 4 (yellow) is below 3:1 on the light surface, so the table view is the required relief.
- Event certainty (ordinal ramp): monotone lightness, single hue, light end ≥ 2:1 in both themes.
- The previous lineage palette **failed**: it used the critical-status red for "merged into", which sat ΔE 3.4 from
  the adjacent ochre for deuteranopes and borrowed a status colour for a series.

Mark specification (`components/Chart.tsx`, applied to every chart):

- Bars at most 28 px wide (18 px horizontal), 4 px rounded data end, square on the baseline; in a stack only the
  outermost segment is rounded.
- A 2 px gap in the surface colour between stacked segments and neighbouring bars, never a border.
- Lines 2 px; markers (8 px) appear on hover only.
- Hairline grid one shade off the surface, quiet axis line, no ticks, 12 px muted axis labels.
- One legend, top left, 10 px square swatches. Direct labels are selective and use text colours.
- Tooltips enhance; they never gate. The same values are in the figure's table view.
