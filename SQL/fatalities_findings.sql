WITH state_fatalities AS (
    SELECT
        c.state,
        CASE
            WHEN c.state IN ('CT','ME','MA','NH','RI','VT','NJ','NY','PA') THEN 'Northeast'
            WHEN c.state IN ('IL','IN','MI','OH','WI','IA','KS','MN','MO','NE','ND','SD') THEN 'Midwest'
            WHEN c.state IN ('DE','DC','FL','GA','MD','NC','SC','VA','WV','AL','KY','MS','TN','AR','LA','OK','TX') THEN 'South'
            ELSE 'West'
        END AS region,
        SUM(c.fatalities) FILTER (WHERE c.report_year = 2015) AS fatalities_2015,
        SUM(c.fatalities) FILTER (WHERE c.report_year = 2024) AS fatalities_2024,
        SUM(c.fatalities) FILTER (WHERE c.report_year BETWEEN 2015 AND 2017) / 3.0 AS avg_2015_2017,
        SUM(c.fatalities) FILTER (WHERE c.report_year BETWEEN 2022 AND 2024) / 3.0 AS avg_2022_2024
    FROM crash c
    JOIN dim_state d ON d.state = c.state
    WHERE d.is_50_states_dc
      AND c.report_year BETWEEN 2015 AND 2025
    GROUP BY c.state, region
)

SELECT
    region,
    state,
    fatalities_2015,
    fatalities_2024,
    ROUND(avg_2015_2017, 1)                          AS avg_2015_2017,
    ROUND(avg_2022_2024, 1)                          AS avg_2022_2024,
    ROUND(avg_2022_2024 - avg_2015_2017, 1)          AS change,
    ROUND(100 * (avg_2022_2024 / avg_2015_2017 - 1), 1) AS pct_change
FROM state_fatalities
ORDER BY region, pct_change DESC;



SELECT report_year,
       SUM(fatalities) FILTER (WHERE state IN ('CT','ME','MA','NH','RI','VT','NJ','NY','PA'))                    AS northeast,
       SUM(fatalities) FILTER (WHERE state IN ('IL','IN','MI','OH','WI','IA','KS','MN','MO','NE','ND','SD'))     AS midwest,
       SUM(fatalities) FILTER (WHERE state IN ('DE','DC','FL','GA','MD','NC','SC','VA','WV','AL','KY','MS','TN','AR','LA','OK','TX')) AS south,
       SUM(fatalities) FILTER (WHERE state IN ('AZ','CO','ID','MT','NV','NM','UT','WY','AK','CA','HI','OR','WA')) AS west,
       SUM(fatalities) AS us_total
FROM crash
WHERE report_year BETWEEN 2015 AND 2025
GROUP BY report_year
ORDER BY report_year;



-- Census Bureau regions used above: each region with its states (50 states + DC)
WITH region_states AS (
    SELECT state,
           CASE
               WHEN state IN ('CT','ME','MA','NH','RI','VT','NJ','NY','PA') THEN 'Northeast'
               WHEN state IN ('IL','IN','MI','OH','WI','IA','KS','MN','MO','NE','ND','SD') THEN 'Midwest'
               WHEN state IN ('DE','DC','FL','GA','MD','NC','SC','VA','WV','AL','KY','MS','TN','AR','LA','OK','TX') THEN 'South'
               ELSE 'West'
           END AS region
    FROM dim_state
    WHERE is_50_states_dc
)
SELECT r.region,
       COUNT(*)                                          AS state_count,
       STRING_AGG(d.state_name, ', ' ORDER BY d.state_name) AS states
FROM region_states r
JOIN dim_state d ON d.state = r.state
GROUP BY r.region
ORDER BY r.region;

