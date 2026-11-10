-- Original attempt (doesn't run):
--   Select SUM(c.fatalities),
--   FROM crash c LEFT JOIN
--   crash_carrier b on c.crash_id = b.crash_id
-- Problems:
--   1. trailing comma after SUM(...)
--   2. crash has no crash_id (its key is crash_key)
--   3. joining crash_carrier repeats a crash once per truck, so fatalities get counted 2-3x
--   4. no GROUP BY, so it returns one grand total instead of one row per state

-- Total fatalities by state (where the crash happened)
SELECT c.state,
       SUM(c.fatalities) AS total_fatalities
FROM crash c
GROUP BY c.state
ORDER BY total_fatalities DESC;

-- Same, with full state names and a few extra columns for context
SELECT s.state_name,
       COUNT(*)                                AS crashes,
       SUM(c.is_fatal::INT)                    AS fatal_crashes,
       SUM(c.fatalities)                       AS total_fatalities,
       ROUND(100.0 * SUM(c.fatalities) / COUNT(*), 2) AS fatalities_per_100_crashes
FROM crash c
JOIN dim_state s ON s.state = c.state
GROUP BY s.state_name
ORDER BY total_fatalities DESC;

-- Fatalities by state and year (stop at 2025: 2026 is a partial year)
SELECT c.state,
       c.report_year,
       SUM(c.fatalities) AS total_fatalities
FROM crash c
WHERE c.report_year <= 2025
GROUP BY c.state, c.report_year
ORDER BY c.state, c.report_year;
