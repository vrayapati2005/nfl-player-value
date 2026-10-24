-- player_season_pergame: per-game production, consistency, and a 2-season weighted average of each.
-- Grain: one row per QB/RB/WR/TE per regular season with at least one game (no snap minimum here,
-- so a short prior season can still feed the weighted average).
--
-- Every production stat is per game played, so missing games never lowers it.
-- Consistency (RB/WR/TE only):
--   good_game_share = share of games over a threshold: WR/TE 50+ receiving yards, RB 60+ scrimmage yards
--   floor_yards     = 25th percentile of weekly yards (receiving for WR/TE, scrimmage for RB)
-- Weighted average (w_ columns): 2/3 current season + 1/3 prior season; current only if there's no prior season.
-- A prior season only counts with 4+ games: a 1-game season (e.g. Aaron Rodgers' 2023 Achilles tear after
-- four snaps, 0 yards) would otherwise get a full third of the weight and drag the average down.

-- 2/3 current + 1/3 prior; falls back to the current value when the prior is missing
CREATE OR REPLACE TEMP MACRO wavg(cur, prev) AS
    CASE WHEN prev IS NULL THEN cur ELSE (2 * cur + prev) / 3 END;

CREATE OR REPLACE TABLE player_season_pergame AS
WITH positions AS (
    SELECT g.gsis_id, g.season, coalesce(r.position, p.position) AS position
    FROM (SELECT DISTINCT gsis_id, season FROM player_game_box) AS g
    LEFT JOIN rosters AS r USING (gsis_id, season)
    LEFT JOIN players AS p USING (gsis_id)
),

-- the weekly yardage that consistency is measured on
games AS (
    SELECT
        b.*,
        pos.position,
        CASE WHEN pos.position = 'RB' THEN b.scrimmage_yards ELSE b.receiving_yards END AS consistency_yards,
        CASE WHEN pos.position = 'RB' THEN 60 ELSE 50 END                              AS good_game_threshold
    FROM player_game_box AS b
    JOIN positions AS pos USING (gsis_id, season)
    WHERE pos.position IN ('QB', 'RB', 'WR', 'TE')
),

rates AS (
    SELECT
        gsis_id,
        season,
        avg(success)                                AS success_rate,
        avg(epa)                                    AS epa_per_play,
        avg(cpoe) FILTER (WHERE role = 'dropback')  AS cpoe
    FROM player_plays
    GROUP BY gsis_id, season
),

per_season AS (
    SELECT
        g.gsis_id,
        g.season,
        any_value(g.position)          AS position,
        count(*)                       AS games,
        avg(g.passing_yards)           AS pass_yds_pg,
        avg(g.passing_tds)             AS pass_td_pg,
        avg(g.rushing_yards)           AS rush_yds_pg,
        avg(g.carries)                 AS carries_pg,
        avg(g.receiving_yards)         AS rec_yds_pg,
        avg(g.receptions)              AS rec_pg,
        avg(g.targets)                 AS targets_pg,
        avg(g.scrimmage_yards)         AS scrim_yds_pg,
        avg(g.epa)                     AS epa_pg,
        avg((g.consistency_yards >= g.good_game_threshold)::INT) AS good_game_share,
        quantile_cont(g.consistency_yards, 0.25)                 AS floor_yards
    FROM games AS g
    GROUP BY g.gsis_id, g.season
),

seasons AS (
    SELECT
        s.*,
        r.success_rate,
        r.epa_per_play,
        CASE WHEN s.position = 'QB' THEN r.cpoe END AS cpoe,
        -- consistency is defined for RB/WR/TE only
        CASE WHEN s.position <> 'QB' THEN s.good_game_share END AS good_game_share_skill,
        CASE WHEN s.position <> 'QB' THEN s.floor_yards END     AS floor_yards_skill
    FROM per_season AS s
    LEFT JOIN rates AS r USING (gsis_id, season)
)

SELECT
    cur.gsis_id,
    cur.season,
    cur.position,
    cur.games,
    prev.gsis_id IS NOT NULL AS has_prior_season,
    -- single-season per-game stats
    cur.pass_yds_pg, cur.pass_td_pg, cur.rush_yds_pg, cur.carries_pg, cur.rec_yds_pg, cur.rec_pg,
    cur.targets_pg, cur.scrim_yds_pg, cur.epa_pg, cur.success_rate, cur.epa_per_play, cur.cpoe,
    cur.good_game_share_skill AS good_game_share,
    cur.floor_yards_skill     AS floor_yards,
    -- 2-season weighted versions (these feed the model)
    wavg(cur.pass_yds_pg,  prev.pass_yds_pg)            AS w_pass_yds_pg,
    wavg(cur.pass_td_pg,   prev.pass_td_pg)             AS w_pass_td_pg,
    wavg(cur.rush_yds_pg,  prev.rush_yds_pg)            AS w_rush_yds_pg,
    wavg(cur.carries_pg,   prev.carries_pg)             AS w_carries_pg,
    wavg(cur.rec_yds_pg,   prev.rec_yds_pg)             AS w_rec_yds_pg,
    wavg(cur.rec_pg,       prev.rec_pg)                 AS w_rec_pg,
    wavg(cur.targets_pg,   prev.targets_pg)             AS w_targets_pg,
    wavg(cur.scrim_yds_pg, prev.scrim_yds_pg)           AS w_scrim_yds_pg,
    wavg(cur.epa_pg,       prev.epa_pg)                 AS w_epa_pg,
    wavg(cur.success_rate, prev.success_rate)           AS w_success_rate,
    wavg(cur.epa_per_play, prev.epa_per_play)           AS w_epa_per_play,
    wavg(cur.cpoe,         prev.cpoe)                   AS w_cpoe,
    wavg(cur.good_game_share_skill, prev.good_game_share_skill) AS w_good_game_share,
    wavg(cur.floor_yards_skill,     prev.floor_yards_skill)     AS w_floor_yards
FROM seasons AS cur
LEFT JOIN seasons AS prev
    ON prev.gsis_id = cur.gsis_id
    AND prev.season = cur.season - 1
    AND prev.games >= 4;
