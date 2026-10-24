-- player_availability: share of possible games played, per season and over a 3-season window.
-- Grain: one row per player per season he was with a team.
--
-- availability      = games played / games in that season (16 in 2019–2020, 17 from 2021)
-- availability_3yr  = total games / total possible games over the current and two prior seasons
-- durability_concern = availability under 75% in at least 2 of those seasons
--
-- A season counts toward the window if the player appeared in a game, or ended the season on a
-- team's active roster, injured reserve (RES), inactive list (INA) or PUP list. Seasons out of the
-- league, on a practice squad or after being cut don't count: they say nothing about injuries.
-- Our data starts in 2019, so 2019–2020 windows have fewer than three seasons.

CREATE OR REPLACE TABLE player_availability AS
WITH games AS (
    SELECT gsis_id, season, count(*) AS games
    FROM player_game_box
    GROUP BY gsis_id, season
),

with_team AS (
    SELECT gsis_id, season FROM rosters WHERE status IN ('ACT', 'RES', 'INA', 'PUP')
    UNION
    SELECT gsis_id, season FROM games
),

per_season AS (
    SELECT
        w.gsis_id,
        w.season,
        coalesce(g.games, 0)                         AS games,
        CASE WHEN w.season <= 2020 THEN 16 ELSE 17 END AS season_games,
        -- a player traded mid-season can appear in 18 games; cap at a full season
        least(coalesce(g.games, 0), CASE WHEN w.season <= 2020 THEN 16 ELSE 17 END)
            / (CASE WHEN w.season <= 2020 THEN 16 ELSE 17 END) AS availability
    FROM with_team AS w
    LEFT JOIN games AS g USING (gsis_id, season)
)

SELECT
    cur.gsis_id,
    cur.season,
    cur.games,
    cur.availability,
    count(*)                                              AS seasons_in_window,
    sum(least(win.games, win.season_games))               AS games_3yr,
    sum(win.season_games)                                 AS possible_games_3yr,
    sum(least(win.games, win.season_games)) / sum(win.season_games) AS availability_3yr,
    count(*) FILTER (WHERE win.availability < 0.75)       AS low_availability_seasons,
    count(*) FILTER (WHERE win.availability < 0.75) >= 2  AS durability_concern
FROM per_season AS cur
JOIN per_season AS win
    ON win.gsis_id = cur.gsis_id
    AND win.season BETWEEN cur.season - 2 AND cur.season
GROUP BY cur.gsis_id, cur.season, cur.games, cur.availability;
