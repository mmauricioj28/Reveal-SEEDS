Select c.fatalities 
FROM crash c LEFT JOIN 
crash_carrier b on c.crash_id = b.crash_id
