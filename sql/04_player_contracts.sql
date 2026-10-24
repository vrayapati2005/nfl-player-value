-- player_contracts: cleaned OverTheCap contracts, keyed by gsis_id.
-- Grain: one row per player per year_signed.
--
-- Cleaning steps:
--   * fill missing gsis_id, in order: (1) the contract's own gsis_id, (2) the players
--     table's otc_id (OverTheCap's own ID), (3) exact name + date of birth, which
--     both tables carry (in different formats) and never matches two people here
--   * drop placeholder rows (year_signed = 0) and rows without an APY
--   * look up each contract's type ('Drafted', 'Extension', 'UFA', ...) in its
--     contract_history list; 'Drafted' = rookie-scale contract
--   * a player can have several contracts signed in the same year (practice squad,
--     released and re-signed, franchise tag then extension) and the raw table has
--     exact duplicate rows. Keep the largest APY that year: it is usually the deal
--     that replaced the others (the extension, not the tag).

CREATE OR REPLACE TABLE player_contracts AS
WITH otc_to_gsis AS (
    SELECT otc_id, gsis_id
    FROM players
    WHERE otc_id IS NOT NULL AND gsis_id IS NOT NULL
),

name_dob_to_gsis AS (
    SELECT lower(display_name) AS name, try_cast(birth_date AS DATE) AS dob, any_value(gsis_id) AS gsis_id
    FROM players
    WHERE gsis_id IS NOT NULL AND birth_date IS NOT NULL
    GROUP BY 1, 2
    HAVING count(DISTINCT gsis_id) = 1   -- skip any name + birthday shared by two players
),

typed AS (
    SELECT
        coalesce(c.gsis_id, o.gsis_id, nd.gsis_id) AS gsis_id,
        c.player,
        c.position AS contract_position,
        c.team AS contract_team,
        c.year_signed,
        c.years,
        c.value,
        c.apy,
        c.guaranteed,
        c.apy_cap_pct,
        c.draft_year,
        c.draft_round,
        -- contract_history lists every contract the player has signed; pick this one's entry
        list_filter(
            c.contract_history,
            lambda h: h.year_signed = c.year_signed AND h.team = c.team AND h.apy = c.apy
        )[1].contract_type AS contract_type
    FROM contracts AS c
    LEFT JOIN otc_to_gsis AS o ON o.otc_id::VARCHAR = c.otc_id::VARCHAR  -- stored as text in one table, integer in the other
    LEFT JOIN name_dob_to_gsis AS nd
        ON nd.name = lower(c.player)
        AND nd.dob = try_strptime(c.date_of_birth, '%B %d, %Y')::DATE  -- OTC writes 'July 26, 1995'
    WHERE c.year_signed > 0
      AND c.apy IS NOT NULL
)

SELECT
    *,
    -- fall back to "signed in his draft year as a drafted player" if the type is missing
    coalesce(contract_type = 'Drafted', year_signed = draft_year AND draft_round IS NOT NULL)
        AS is_rookie_contract
FROM typed
WHERE gsis_id IS NOT NULL
QUALIFY row_number() OVER (
    PARTITION BY gsis_id, year_signed
    ORDER BY apy DESC, value DESC
) = 1;
