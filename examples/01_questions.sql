-- Questions the release answers, in plain SQL. Run from data/release:
--   duckdb -c ".read load.sql" -c ".read ../../examples/01_questions.sql"
-- Every query reads only the release tables (data/release/tables) through load.sql's views.

-- 1. How many districts are on each map, and how many identities first appear on it?
SELECT o.year, count(*) AS districts,
       count(*) FILTER (WHERE r.established_year = o.year AND r.origin_kind = 'NEW') AS new_identities
FROM ck_observation o JOIN ck_registry r USING (canonical_key)
GROUP BY o.year ORDER BY o.year;

-- 2. One district through every map: Kangra's name, state and area.
SELECT o.year, o.district_name, o.state, round(o.area_km2) AS km2
FROM ck_observation o JOIN ck_registry r USING (canonical_key)
WHERE r.latest_name = 'Kangra' ORDER BY o.year;

-- 3. The ten largest carve-outs: new identities formed from an existing district's land.
SELECT p.latest_name AS from_district, c.latest_name AS new_district, c.latest_state AS state,
       d.year_a || '–' || d.year_b AS between_maps, round(d.transfer_km2) AS km2
FROM district_relationship d
JOIN ck_registry p ON p.canonical_key = d.from_ck JOIN ck_registry c ON c.canonical_key = d.to_ck
WHERE d.relationship_type = 'FORMED_FROM'
ORDER BY d.transfer_km2 DESC, d.rel_id LIMIT 10;

-- 4. Where did a 1951 district's land go? Malabar's shares among the 2025 districts.
SELECT t.latest_name AS district_2025, t.latest_state AS state, round(x.area_km2) AS km2,
       round(100 * x.share_of_source, 1) AS pct_of_malabar
FROM crosswalk_to_reference x
JOIN ck_registry s ON s.canonical_key = x.source_ck JOIN ck_registry t ON t.canonical_key = x.target_ck
WHERE x.year = 1951 AND s.latest_name = 'Malabar' AND x.share_of_source >= 0.001
ORDER BY x.area_km2 DESC;

-- 5. How many administrative events could be measured in km², and why not the rest?
--    An event is MEASURED only if every district it touched had no other event between the two maps
--    (so the km² that moved belongs to it alone); with no accounting row at all it is NOT_MEASURABLE.
SELECT status, count(*) AS events FROM (
  SELECT e.event_id,
         CASE WHEN count(a.event_id) = 0 THEN 'NOT_MEASURABLE'
              WHEN bool_and(a.measurement_status = 'MEASURED') THEN 'MEASURED'
              ELSE 'UNIDENTIFIED_MULTI_EVENT_WINDOW' END AS status
  FROM boundary_event e LEFT JOIN event_accounting a USING (event_id) GROUP BY e.event_id)
GROUP BY status ORDER BY events DESC;
