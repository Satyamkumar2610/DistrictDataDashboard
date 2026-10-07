# UI audit and overhaul plan

Date: 2026-10-07. Scope: the web platform (`web/`), all ten routes, at 1360×860 and 390×844 (phone),
light and dark. Evidence: full-page screenshots of every route at both widths, axe-core 4 on every
route, a scan for text under 12 px and controls under 32 px tall, load timings against the local
server, and the production bundle sizes. Every finding below comes from those measurements.

## What the audit found

### 1. Navigation and wayfinding

| Finding | Evidence |
|---|---|
| Eight equal top-level links. On a phone they become a sideways strip cut off mid-word ("Crossw") with no sign that it scrolls | phone screenshots, every route |
| The header search disappears below 1,100 px, so a phone user can only search from the home page | `.topsearch { display: none }` at ≤1100 px |
| Nothing groups the links by what a visitor wants to do: explore, use the data, or understand the method | nav markup |
| The District page is 3,227 px tall on desktop and 5,465 px on a phone, with no way to jump to a section | `scrollHeight` |

### 2. Visual hierarchy

| Finding | Evidence |
|---|---|
| Every block is the same white box with the same border. A chart, a caveat and a download table carry equal weight, so nothing leads | all desktop screenshots |
| Small text: 59 text elements under 12 px on Data, 31 on District, 14 on States, mostly 11 px mono labels and source lines | small-text scan |
| Raw row hashes in user-facing captions (`district_relationship 75c910b2b6…`) on the State and District pages | State and District screenshots |
| Chart colours do not follow their meaning: "districts on the map" is drawn in the colour that elsewhere means *new district* | Overview, States |
| The State page shows the whole of India with the state as a speck | State screenshot |
| Harmonize opens on an unstyled native file input; nothing invites a drop | Harmonize screenshot |

### 3. Interaction

| Finding | Evidence |
|---|---|
| Controls under 32 px tall: 48–50 on District, 47 on Data, 33–41 on States (year buttons, inline links, chips) | tap-target scan; 44 px is the usual touch minimum |
| On a phone the Atlas controls cover about 40% of the map and cannot be folded away | phone Atlas screenshot |
| Loading states are the word "Loading…"; panels jump as data arrives | every route on first load |

### 4. Accessibility (axe-core 4)

| Rule | Impact | Where |
|---|---|---|
| label-content-name-mismatch | serious | District: history buttons labelled "Show the 1961 map" but reading "1951 → 1961" (9 nodes) |
| color-contrast | serious | Open questions: muted text on the selected card's tint, 4.03:1 (`--muted` on `--accent-soft`; the token test only checks `--bg` and `--surface`) |
| scrollable-region-focusable | serious | Data: two scrolling tables a keyboard cannot reach |
| heading-order | moderate | Home, States, Open questions: headings skip a level |

### 5. Performance

Loads take 0.5–1.2 s against the local server. The map chunk is 1.03 MB, the chart chunk 607 KB and
the map worker 510 KB before gzip. Both are already loaded only on routes that use them, so this round
changes nothing here.

## Plan

Ordered by how much each item improves a visit. Each item names its acceptance check.

1. **Foundations.**
   - Body text to 15 px, nothing under 12 px, labels at 12 px.
   - Three surface levels: page, section and card. Sections carry no border by default, so cards
     stand out where they matter.
   - The spacing scale from the design system; a focus ring on every control.
   - Chart colours that follow meaning: neutral counts in ink, new districts blue, land out orange,
     land in green.
   - *Check:* the small-text scan reports no text under 12 px apart from map labels; the contrast
     test also covers `--accent-soft`.
2. **Navigation.**
   - Three groups: *Explore* (Atlas, States), *Use the data* (Crosswalk, Harmonize, Downloads) and
     *About* (How it works, Open questions).
   - On a phone, a menu button opens a panel with every link and the search.
   - *Check:* no clipped links at 390 px; search reachable on every route at every width.
3. **District page.**
   - A sticky section bar: History, Area, Family, Events, Statistics.
   - Row hashes move out of the visible text into the source line's tooltip. The table name stays
     visible.
   - *Check:* every section reachable in one click; no 32-character hashes in visible text.
4. **State page.**
   - The map fits the state.
   - A history built like the District one.
   - Counts drawn in a neutral colour.
   - *Check:* the state fills the map frame.
5. **Atlas on a phone.**
   - The controls fold into one bar.
   - The district panel is reachable.
   - *Check:* at least 60% of the phone viewport shows map.
6. **Harmonize.**
   - A drop zone with an obvious button.
   - Example and column help beside it.
   - *Check:* drag-and-drop works; the e2e tests still drive the file input.
7. **Loading.** Skeleton blocks the size of what they replace. *Check:* no layout jump when the figures
   arrive.
8. **Accessibility.** Fix all four axe rules. *Check:* axe reports no serious or critical violations
   on any route.
9. **Touch targets.** Controls at least 36 px tall, 44 px on touch screens. *Check:* the tap-target
   scan on a phone drops to inline links in running text only.

Not in this round: the map and chart bundle sizes, which are already loaded only where used, and new
data features. Nothing in the overhaul changes a number on the site; the e2e tests that assert values
read from the warehouse must keep passing unchanged.

## Results

The same measurements, rerun after the overhaul against the same server and routes.

| Check | Before | After |
|---|---|---|
| axe serious or critical violations | 4 routes (13 nodes) | **0** on all 10 routes |
| Text elements under 12 px (all routes, desktop) | 134 | **0** |
| Controls under 32 px on a phone, other than links inside sentences or table cells | brand link, map zoom, "How to read this", contents links, year and section buttons | **0** |
| Sideways scroll at 390 px | 0 (after the previous pass) | **0**, including the new section bar and phone Atlas |
| Search reachable on a phone | home page only | every page, from the menu |
| State page map | all of India, state a speck | fitted to the state (API returns its bounds) |
| Phone Atlas | controls covered roughly 40% of the map (estimated from the screenshot, not measured) | map over 60% of screen height (tested); folded by default, only the year bar and one button overlay it |

Links inside sentences and table cells remain under 32 px tall. WCAG 2.2 AA (2.5.8) accepts them: inline
targets are exempt, and table rows are more than 24 px apart.

Tests that hold these results: `web/e2e/overhaul.spec.ts` (axe on every route, no text under 12 px, the
phone menu and its search, phone Atlas map share, section bar, no row hashes in visible text) and
`tests/test_theme_contrast.py` (text on the selection tint). `axe-core` is pinned as a dev dependency.

A regression found while measuring, and fixed: the phone rule for the Atlas year bar (`nowrap`) also applied
to the District page's year bar and made that page 161 px too wide; it is now scoped to the Atlas.

## Second round: 3D and depth

The home page leads with a 3D map built from the release (`web/src/components/Map3D.tsx`, data from
`/api/shapes/{year}`). Rules it keeps, so the effect never outruns the data:

- **One encoding.** Height and colour mean one thing: the district first appears on this map (`is_new`, the field
  the Atlas uses). Every other district has the same height; their slight shade differences come from the key's
  last digit and only separate neighbours.
- **Same counts as the rest of the site.** The caption and the map's `data-count` / `data-new` equal
  `/api/overview` on all nine maps; `web/e2e/map3d.spec.ts` checks it.
- **Drawing geometry only.** Shapes are simplified to 0.04° for drawing; every area shown comes from the release
  tables, never from these shapes.
- **Accessible.** The canvas is hidden from assistive technology; the caption is a polite live region; play and
  year controls are buttons with names. Reduced motion stops autoplay, drift and the rise animation. Without
  WebGL the panel links to the Atlas.
- **Weight.** three.js loads as a separate 143 KB (gzipped) chunk on the home page only.

Site-wide: glass panels (translucent surface, blur) where controls sit over the map; a layered shadow and a 2 px
lift for cards under the pointer; pages settle in by 10 px. Motion is transform only, so axe's contrast checks
see final colours; axe still reports no serious or critical violation on any route.
