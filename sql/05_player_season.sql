-- player_season: the modeling table. One row per player per regular season,
-- QB/RB/WR/TE only, with at least 200 offensive snaps, joined to the contract
-- in force that season.
--
-- Inputs: player_plays (production), player_games (snaps), rosters (position, age),
--         player_contracts (pay). Regular season only: playoff games would give
--         players on good teams extra opportunities that others never had.

CREATE OR REPLACE TABLE player_season AS
WITH

-- 1) On-field production from play-by-play.
production AS (
    SELECT
        gsis_id,
        season,
        count(*)                                                     AS plays,
        count(*) FILTER (WHERE role = 'dropback')                    AS dropbacks,
        count(*) FILTER (WHERE role = 'rush')                        AS rushes,
        count(*) FILTER (WHERE role = 'target')                      AS targets,
        sum(complete_pass)                                           AS receptions,
        sum(epa)                                                     AS total_epa,
        avg(epa)                                                     AS epa_per_play,
        avg(success)                                                 AS success_rate,
        avg(cpoe) FILTER (WHERE role = 'dropback')                   AS cpoe,
        sum(air_yards)                                               AS air_yards,
        sum(yards_after_catch) FILTER (WHERE complete_pass = 1)      AS yards_after_catch
    FROM player_plays
    GROUP BY gsis_id, season
),

-- 2) Every game a player appeared in: a game with snaps, or with a play credited to him.
--    (Using both sources means a missing snap-count row can't silently drop his targets.)
appearances AS (
    SELECT gsis_id, season, game_id, team FROM player_games
    UNION
    SELECT DISTINCT gsis_id, season, game_id, team FROM player_plays
),

player_game_targets AS (
    SELECT gsis_id, game_id, count(*) AS targets, sum(air_yards) AS air_yards
    FROM player_plays
    WHERE role = 'target'
    GROUP BY gsis_id, game_id
),

team_game_targets AS (
    SELECT game_id, team, count(*) AS team_targets, sum(air_yards) AS team_air_yards
    FROM player_plays
    WHERE role = 'target'
    GROUP BY game_id, team
),

-- 3) Usage: snaps and shares, measured only over games the player appeared in,
--    so a player isn't penalized for games he missed or before he was traded to a team.
usage AS (
    SELECT
        a.gsis_id,
        a.season,
        count(*)                                                        AS games_played,
        sum(g.offense_snaps)                                            AS offense_snaps,
        sum(g.offense_snaps) / sum(g.team_offense_snaps)                AS snap_pct,
        sum(coalesce(pt.targets, 0))   / nullif(sum(tt.team_targets), 0)   AS target_share,
        sum(coalesce(pt.air_yards, 0)) / nullif(sum(tt.team_air_yards), 0) AS air_yards_share
    FROM appearances AS a
    LEFT JOIN player_games        AS g  USING (gsis_id, game_id)
    LEFT JOIN player_game_targets AS pt USING (gsis_id, game_id)
    LEFT JOIN team_game_targets   AS tt ON tt.game_id = a.game_id AND tt.team = a.team
    GROUP BY a.gsis_id, a.season
),

-- 4) Team: traded players get the team they played the most snaps for, plus a count of teams.
teams AS (
    SELECT
        gsis_id,
        season,
        arg_max(team, team_snaps) AS team,
        count(*)                  AS n_teams
    FROM (
        SELECT a.gsis_id, a.season, a.team, sum(coalesce(g.offense_snaps, 0)) AS team_snaps
        FROM appearances AS a
        LEFT JOIN player_games AS g USING (gsis_id, game_id)
        GROUP BY a.gsis_id, a.season, a.team
    )
    GROUP BY gsis_id, season
),

-- 5) Assemble, adding name/position/age from rosters (players table as fallback).
seasons AS (
    SELECT
        u.gsis_id,
        u.season,
        coalesce(r.full_name, p.display_name)                        AS player_name,
        coalesce(r.position, p.position)                             AS position,
        t.team,
        t.n_teams,
        -- age on Sept 1 of the season, roughly kickoff
        date_diff('day', coalesce(r.birth_date, try_cast(p.birth_date AS DATE)), make_date(u.season, 9, 1)) / 365.25 AS age,
        u.games_played,
        u.offense_snaps,
        u.snap_pct,
        pr.plays,
        pr.dropbacks,
        pr.rushes,
        pr.targets,
        pr.receptions,
        pr.total_epa,
        pr.epa_per_play,
        pr.success_rate,
        -- QBs only: a WR's one trick-play pass shouldn't produce a CPOE
        CASE WHEN coalesce(r.position, p.position) = 'QB' THEN pr.cpoe END AS cpoe,
        u.target_share,
        u.air_yards_share,
        pr.air_yards,
        pr.yards_after_catch
    FROM usage AS u
    JOIN production   AS pr USING (gsis_id, season)
    JOIN teams        AS t  USING (gsis_id, season)
    LEFT JOIN rosters AS r  USING (gsis_id, season)
    LEFT JOIN players AS p  USING (gsis_id)
)

-- 6) Attach the contract in force: ASOF JOIN picks, for each player-season, the most
--    recent contract with year_signed <= season. Extensions replace older deals.
SELECT
    s.*,
    c.year_signed       AS contract_year_signed,
    c.years              AS contract_years,
    c.contract_type,
    c.apy,
    c.apy_cap_pct,
    c.is_rookie_contract
FROM seasons AS s
ASOF LEFT JOIN player_contracts AS c
    ON s.gsis_id = c.gsis_id
    AND s.season >= c.year_signed
WHERE s.position IN ('QB', 'RB', 'WR', 'TE')
  AND s.offense_snaps >= 200;
