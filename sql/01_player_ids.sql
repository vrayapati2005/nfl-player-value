-- player_ids: crosswalk from Pro Football Reference IDs (pfr_id, the only ID in
-- snap_counts) to nflverse gsis_id (the ID used by pbp, rosters and contracts).
-- Grain: one row per pfr_id that appears in snap_counts and could be matched.
--
-- Step 1: nflverse's master `players` table, which links pfr_id <-> gsis_id 1:1.
--         (We don't use rosters.pfr_id: it's missing for ~half of rows and has
--         a few wrong IDs, e.g. Tyler Conklin carries Ryan Izzo's pfr_id.)
-- Step 2: for the few pfr_ids step 1 misses, match on exact name + team + season
--         against rosters, keeping only matches that point to exactly one player.

CREATE OR REPLACE TABLE player_ids AS
WITH snap_players AS (
    SELECT DISTINCT
        pfr_player_id,
        player,
        season,
        CASE team WHEN 'OAK' THEN 'LV' ELSE team END AS team  -- PFR still says OAK for 2019 Raiders
    FROM snap_counts
),

via_players AS (
    SELECT pfr_id, gsis_id
    FROM players
    WHERE pfr_id IS NOT NULL AND gsis_id IS NOT NULL
),

via_name AS (
    SELECT
        s.pfr_player_id AS pfr_id,
        any_value(r.gsis_id) AS gsis_id
    FROM snap_players AS s
    JOIN rosters AS r
        ON lower(r.full_name) = lower(s.player)
        AND (CASE r.team WHEN 'OAK' THEN 'LV' ELSE r.team END) = s.team
        AND r.season = s.season
    WHERE s.pfr_player_id NOT IN (SELECT pfr_id FROM via_players)
      AND r.gsis_id NOT IN (SELECT gsis_id FROM via_players)  -- never steal an ID step 1 already used
    GROUP BY s.pfr_player_id
    HAVING count(DISTINCT r.gsis_id) = 1                       -- ambiguous names are left unmatched
)

SELECT pfr_id, gsis_id, 'players_table' AS match_method
FROM via_players
WHERE pfr_id IN (SELECT pfr_player_id FROM snap_players)

UNION ALL

SELECT pfr_id, gsis_id, 'name_team_season' AS match_method
FROM via_name;
