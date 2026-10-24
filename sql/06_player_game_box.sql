-- player_game_box: box-score production per player per regular-season game he appeared in.
-- Grain: one row per player per game.
--
-- A game counts as "appeared" if the player took an offensive snap or was credited with a play
-- (the same rule as player_season). nflverse's weekly player_stats only has a row when the player
-- recorded a stat, so a game with no box-score row (e.g. a TE who only blocked) is filled with zeros.
-- Without that, a quiet game would vanish and inflate per-game averages and consistency.

CREATE OR REPLACE TABLE player_game_box AS
WITH appearances AS (
    SELECT gsis_id, game_id, any_value(season) AS season, any_value(week) AS week, any_value(team) AS team
    FROM (
        SELECT gsis_id, game_id, season, week, team FROM player_games
        UNION ALL
        SELECT gsis_id, game_id, season, week, team FROM player_plays
    )
    GROUP BY gsis_id, game_id
),

box AS (
    SELECT
        player_id AS gsis_id,
        game_id,
        passing_yards,
        passing_tds,
        carries,
        rushing_yards,
        targets,
        receptions,
        receiving_yards
    FROM player_stats
    WHERE season_type = 'REG'
),

game_epa AS (
    SELECT gsis_id, game_id, sum(epa) AS epa
    FROM player_plays
    GROUP BY gsis_id, game_id
)

SELECT
    a.gsis_id,
    a.season,
    a.week,
    a.game_id,
    a.team,
    coalesce(b.passing_yards, 0)   AS passing_yards,
    coalesce(b.passing_tds, 0)     AS passing_tds,
    coalesce(b.carries, 0)         AS carries,
    coalesce(b.rushing_yards, 0)   AS rushing_yards,
    coalesce(b.targets, 0)         AS targets,
    coalesce(b.receptions, 0)      AS receptions,
    coalesce(b.receiving_yards, 0) AS receiving_yards,
    coalesce(b.rushing_yards, 0) + coalesce(b.receiving_yards, 0) AS scrimmage_yards,
    coalesce(e.epa, 0)             AS epa
FROM appearances AS a
LEFT JOIN box      AS b USING (gsis_id, game_id)
LEFT JOIN game_epa AS e USING (gsis_id, game_id);
