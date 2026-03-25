/*
-- lucro total
SELECT SUM(profit) AS total_profit
FROM bets;

-- stake total
SELECT SUM(stake) AS total_stake
FROM bets;

-- roi total
SELECT
    ROUND(((SUM(profit) / SUM(stake)) * 100)::numeric, 2) AS roi_percent
FROM bets;

-- hit rate
SELECT
    ROUND(
        (
            COUNT(*) FILTER (WHERE status = 'win')::numeric
            / COUNT(*)
        ) * 100,
        2
    ) AS hit_rate_percent
FROM bets
WHERE status IN ('win', 'loss', 'void');

-- lucro por esporte
SELECT
    sport,
    ROUND(SUM(profit)::numeric, 2) AS total_profit
FROM bets
GROUP BY sport
ORDER BY total_profit DESC;