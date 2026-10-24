-- player_games: offensive snaps per player per regular-season game, keyed by gsis_id.
-- Grain: one row per player per game where the player took at least one offensive snap.

CREATE OR REPLACE TABLE player_games AS
WITH snaps AS (
    SELECT
        game_id,
        season,
        week,
        CASE team WHEN 'OAK' THEN 'LV' ELSE team END AS team,  -- match pbp's team codes
        pfr_player_id,
        offense_snaps,
        offense_pct
    FROM snap_counts
    WHERE game_type = 'REG'
),

-- PFR gives each player's snaps and snap %, but not the team's total snaps.
-- Back it out as snaps / pct. The pct is rounded to 2 decimals, so use the player
-- with the most snaps in that game: the larger the count, the smaller the rounding error.
team_snaps AS (
    SELECT
        game_id,
        team,
        round(arg_max(offense_snaps / offense_pct, offense_snaps)) AS team_offense_snaps
    FROM snaps
    WHERE offense_pct > 0
    GROUP BY game_id, team
)

SELECT
    ids.gsis_id,
    s.season,
    s.week,
    s.game_id,
    s.team,
    s.offense_snaps,
    t.team_offense_snaps
FROM snaps AS s
JOIN player_ids AS ids ON ids.pfr_id = s.pfr_player_id
JOIN team_snaps AS t USING (game_id, team)
WHERE s.offense_snaps > 0;
