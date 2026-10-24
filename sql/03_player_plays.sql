-- player_plays: every regular-season offensive play credited to each skill player involved.
-- Grain: one row per player per play per role. A completed pass appears twice:
-- once for the QB (role = 'dropback') and once for the receiver (role = 'target').
-- That's intentional: both players share credit for the play's EPA.
--
-- Roles:
--   dropback  QB pass plays, including sacks and scrambles (pbp's passer_id covers all three)
--   rush      designed runs (pbp's rush = 1 excludes scrambles, which belong to the dropback)
--   target    the intended receiver on a pass attempt

CREATE OR REPLACE TABLE player_plays AS
WITH plays AS (
    SELECT *
    FROM pbp
    WHERE season_type = 'REG'
      AND play_type IN ('pass', 'run')             -- drops penalties-only plays, kneels, spikes, kicks
      AND coalesce(two_point_attempt, 0) = 0
      AND epa IS NOT NULL
)

SELECT passer_id AS gsis_id, 'dropback' AS role,
       season, week, game_id, play_id, posteam AS team,
       epa, success, cpoe,
       NULL::DOUBLE AS air_yards, NULL::DOUBLE AS yards_after_catch, NULL::DOUBLE AS complete_pass
FROM plays
WHERE qb_dropback = 1 AND passer_id IS NOT NULL

UNION ALL

SELECT rusher_id, 'rush',
       season, week, game_id, play_id, posteam,
       epa, success, NULL,
       NULL, NULL, NULL
FROM plays
WHERE rush = 1 AND rusher_id IS NOT NULL

UNION ALL

SELECT receiver_id, 'target',
       season, week, game_id, play_id, posteam,
       epa, success, NULL,
       air_yards, yards_after_catch, complete_pass
FROM plays
WHERE pass_attempt = 1 AND receiver_id IS NOT NULL;
