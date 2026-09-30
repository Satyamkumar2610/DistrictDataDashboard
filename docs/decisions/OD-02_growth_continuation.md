# OD-02: A district that keeps its land and name and grows keeps its identity

Status: **decided** (4.0.0). Config: `identity.growth_continues`, `identity.growth_min_h`.

## Question

The identity rule (REVAMP_PLAN_V3 §3.3) continues a district i into its successor j only if i supplies
most of j (h ≥ 0.50). What should happen when i is essentially intact in j (r ≥ 0.90) and j keeps i's
name, but j also absorbed more land from neighbours than i had (h < 0.50)?

## What the data showed (4.0.0, before this rule)

Ten such cases, each closed as `BREAK_NO_CORE` with a new identity minted for j:

| Window | District | Area before → after (km²) | r | h |
|---|---|---|---|---|
| 1981→1991 | Una | 945 → 2,114 | 1.000 | 0.447 |
| 1991→2001 | Gandhinagar | 675 → 2,128 | 1.000 | 0.317 |
| 1991→2001 | Hyderabad | 85 → 201 | 0.999 | 0.424 |
| 1991→2001 | Kanpur Nagar | 1,053 → 2,999 | 1.000 | 0.351 |
| 2011→2021 | Chennai | 178 → 438 | 0.995 | 0.404 |
| 2011→2021 | Mumbai | 77 → 142 | 0.921 | 0.499 |
| 2011→2021 | Punch | 1,796 → 4,282 | 0.967 | 0.406 |
| 2011→2021 | New Delhi | 36 → 157 | 0.961 | 0.219 |
| 2021→2025 | Champhai | 1,578 → 3,401 | 0.998 | 0.463 |
| 2021→2025 | Kolkata | 99 → 185 | 0.929 | 0.494 |

The project's identity question is *is this the same administrative entity?* In every case the
district is still there, whole and under its own name; it has grown. Several are enlargements of city
districts. Some come from how a map edition draws a boundary rather than from a change on the ground:
Una's 1991 and 2001 polygon (2,114 km²) disagrees with the 2011, 2021 and SOI 2025 maps (1,543–1,560
km²), and Champhai's 2025 polygon includes districts SOI has not yet split out
(`known_geometry_gaps.csv`). Either way, starting a new identity misstates the history: it says the
district ended.

## Decision

Rule 1b: **i continues as j** (`GROWTH_NAME_RETAINED`) when
1. i is essentially intact in j (r ≥ `identity.strong`, 0.90),
2. the names agree (as in §3.3),
3. no other district continues into j (applied after rules 1–2, so continuity stays one-to-one; the
   stage asserts it), and
4. h ≥ `identity.growth_min_h` (0.15, mirroring `name_retained`; the smallest measured case is 0.219).

The land j gained from its neighbours is recorded as measured transfers between continuing
identities, as for any other boundary change.

## Why this does not weaken the rule

h ≥ 0.50 existed to make continuity one-to-one. Condition 3 keeps that. Conditions 1 and 2 need both
kinds of evidence, geometry (i is whole inside j) and name, so a small district cannot hand its identity
to an unrelated unit that happens to contain it.

## Effect

Keys change (MAJOR), folded into 4.0.0 because 4.0.0 was not released; every 3.x key resolves through
`data/reference/ck_migration_v3_to_v4.csv`. Setting `identity.growth_continues: false` restores the
3.x behaviour.
