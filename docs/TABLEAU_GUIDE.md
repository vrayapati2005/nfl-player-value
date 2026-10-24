# Tableau Public dashboard guide

A click-by-click build of one dashboard, **"Who's worth their contract?"**, in the Tableau Public desktop app for Mac.
It uses the v2 exports: `exports/player_value.csv` (one row per player-season, 2024–2025) and `exports/team_value.csv`
(one row per team-season).

The finished dashboard has four sheets:

| Sheet | What it shows |
|---|---|
| **Player lookup** | Pay vs fair value, gap, both labels, availability, durability, production score |
| **Reasons** | The 3 plain-English SHAP reasons for the player in the lookup |
| **Value scatter** | Fair value vs actual cap %, with a diagonal "paid exactly fair value" line; clicking a point fills the lookup |
| **Team value** | Net value in $M per team, with a Season / 3-year toggle |

The reasons get their own small sheet because Tableau text tables get very wide with long sentences in them.
On the dashboard it sits directly under the lookup, so the two read as one panel.

---

## 0. Before you start: what the columns mean

| Column | Meaning | Units |
|---|---|---|
| `actual_pct_of_cap`, `fair_pct_of_cap` | Contract APY and model fair value as a share of the salary cap | already in percent: `3.2` means 3.2% |
| `actual_musd`, `fair_musd` | The same in millions of dollars | $M |
| `gap_musd` | `actual_musd − fair_musd`. **Positive = paid more than the production is worth** | $M |
| `label_season` | Overpaid / Fair / Underpaid / Limited sample / Rookie contract (per-game value; missed games don't count against a player) | text |
| `label_3yr` | Same labels from availability-adjusted value over 3 seasons | text |
| `availability`, `availability_3yr` | Games played ÷ games possible | fraction: `0.76` means 76% |
| `durability_concern` | `True` if availability was under 75% in 2+ of the last 3 seasons | True/False |
| `production_score` | 0–100 composite of per-game percentiles within position | score |
| `reason_1`, `reason_2`, `reason_3` | Top 3 SHAP drivers of fair value, in plain English | text |
| `net_value_musd`, `net_value_3yr_musd` (team file) | Underpaid surplus + rookie surplus − overpaid excess. **Positive = good for the team** | $M |

---

## 1. Connect the data

1. Open **Tableau Public**. On the start page, under **Connect → To a File**, click **Text file**.
2. Select `exports/player_value.csv` → **Open**. The Data Source page opens.
3. Check the type icon above these columns, and click the icon to change any that are wrong:
   - `season` → **String**. It's a category here, and you don't want Tableau summing it.
   - `gsis_id`, `player_name`, `position`, `team`, `label_season`, `label_3yr`, `reason_1`–`reason_3` → **String** (Abc).
   - `durability_concern`, `is_rookie_contract` → **Boolean** if Tableau offers it, otherwise leave them as String.
     The guide works either way.
4. Add the second file: at the top left of the Data Source page, click **Add** (next to *Connections*) → **Text file**
   → `exports/team_value.csv`.
   - Tableau may try to relate it to the first file. **Don't join them.** If a relationship line appears, drag
     `team_value.csv` off the canvas.
   - Instead, open it as its own data source: **Data menu → New Data Source → Text file → team_value.csv**.
   - Set its `season` to **String** as well.
5. You now have two data sources in the Data pane, `player_value` and `team_value`. Click **Sheet 1** at the bottom to start.

### Number formats (do once, in the Data pane of `player_value`)
Right-click a field → **Default Properties → Number Format…**:

| Fields | Format |
|---|---|
| `actual_pct_of_cap`, `fair_pct_of_cap` | **Number (Custom)**, 1 decimal, **Suffix** `%`. Don't use *Percentage*: the values are already ×100 |
| `actual_musd`, `fair_musd`, `gap_musd` | **Currency (Custom)**, 1 decimal, Prefix `$`, Suffix `M` |
| `availability`, `availability_3yr` | **Percentage**, 0 decimals (these are fractions) |
| `production_score` | **Number (Custom)**, 0 decimals |

Do the same for `net_value_musd` and `net_value_3yr_musd` in `team_value` (Currency, 1 decimal, suffix `M`).

Optional: right-click a field → **Rename** to give it a readable display name, e.g. `gap_musd` → *Gap ($M, + = overpaid)*.
Renaming changes only what viewers see, not the CSV.

---

## 2. Colors for the labels (colorblind-safe)

These come from the Okabe-Ito palette, which was designed for color-vision deficiency. Every pair of colors was
checked with a colorblind-simulation validator: all pairs stay distinguishable under deuteranopia, protanopia and
tritanopia, and with normal vision.

| Label | Color | Hex | Why |
|---|---|---|---|
| Overpaid | vermillion | `#D55E00` | warm = cost to the team |
| Underpaid | blue | `#0072B2` | cool = surplus to the team |
| Fair | light gray | `#BDBDBD` | neutral middle, recedes so the extremes stand out |
| Limited sample | orange | `#E69F00` | "caution", distinct from Overpaid in all three color-vision types |
| Rookie contract | bluish green | `#009E73` | a separate category (cheap by rule, not by model) |

For team bars, use the same pair: **positive net value `#0072B2`**, **negative `#D55E00`**.

Two rules keep the design accessible:
- **Never rely on color alone.** The orange and the gray are low-contrast on a white background, so always keep the
  color legend visible, and add **shape** as a second cue on the scatter (step 4.6).
- To set a color: click the **Color** card → **Edit Colors…** → click a label on the left → click **…** under the
  palette (or double-click the swatch) → paste the hex code → **OK**.

---

## 3. Sheet 1: Player lookup

1. Double-click the **Sheet 1** tab and rename it **Player lookup**. Make sure the `player_value` data source is selected.
2. Drag these dimensions to **Rows**, in this order: `player_name`, `season`, `team`, `position`, `label_season`,
   `label_3yr`, `durability_concern`.
3. Drag **Measure Names** (bottom of the Data pane) to **Columns**, and **Measure Values** to the **Text** box on the Marks card.
4. A **Measure Values** card appears below the Marks card. Remove every measure on it (drag each one off) until it's empty, then drag in, in order:
   `actual_musd`, `fair_musd`, `gap_musd`, `actual_pct_of_cap`, `fair_pct_of_cap`, `availability`, `availability_3yr`,
   `production_score`.
   - Each is a single row per player-season, so **SUM** is just the value. Leave it as SUM.
5. **Search box for player name.**
   1. Drag `player_name` to the **Filters** shelf. In the dialog, open the **Wildcard** tab → choose **Contains** → leave
      the text empty → **OK**.
   2. Right-click `player_name` on the Filters shelf → **Show Filter**. The filter card on the right is a text box.
      Type "Allen" and the table narrows to every Allen.
6. **Season and position filters.**
   1. Drag `season` to Filters → **All** → **OK**. Right-click it → **Show Filter**. On the filter card's ▾ menu,
      choose **Single Value (dropdown)** or **Multiple Values (list)**.
   2. Repeat for `position`.
   3. For each of the three filters: filter card ▾ → **Apply to Worksheets → All Using This Data Source**. Searching
      and filtering then also drives the Reasons sheet and the scatter.
7. Color the label cells (optional but helps): drag `label_season` to **Color** on the Marks card, set the colors
   from section 2, then Marks dropdown → **Square**. This colors each row's cells by its season label.
   If it looks too heavy, skip it; the label text is already in the row.
8. **Format → Shading** → Row Banding: on, light. **Format → Borders** → Row Divider: thin.

## 4. Sheet 2: Reasons (companion to the lookup)

1. New sheet (the icon right of the sheet tabs) → rename **Reasons**.
2. Drag `player_name` and `season` to **Rows**. Set the Marks dropdown to **Text**.
3. Drag `reason_1`, `reason_2`, `reason_3` onto **Text** on the Marks card.
4. Click **Text** → **…** to open the Edit Label dialog. Replace the contents with three lines:
   ```
   Why this fair value:
   1. <reason_1>
   2. <reason_2>
   3. <reason_3>
   ```
   (Insert the fields with the **Insert** button so they stay live.) Then click **Text → Alignment → Left**.
5. The filters from step 3.6 already apply here because they're set to "All Using This Data Source".

## 5. Sheet 3: Value scatter

1. New sheet → rename **Value scatter**.
2. Drag `fair_pct_of_cap` to **Columns** and `actual_pct_of_cap` to **Rows**.
3. Drag `gsis_id`, `season` and `player_name` to **Detail** on the Marks card. You get one dot per player-season
   (otherwise Tableau sums everyone into a single dot).
4. Marks dropdown → **Circle**. Drag `label_season` to **Color**, and set the colors from section 2.
   Click **Color** → Opacity about 75%, Border → white, so overlapping dots stay readable.
5. **The diagonal "fair value" line (y = x).** Tableau reference lines are only horizontal or vertical, so build
   the diagonal with a trend line:
   1. **Analysis → Create Calculated Field…** Name it `Fair line`, formula `[fair_pct_of_cap]`, then **OK**.
   2. Drag `Fair line` to **Rows**, to the right of `actual_pct_of_cap`. Right-click the `Fair line` pill → **Dual Axis**.
   3. Right-click the right-hand axis → **Synchronize Axis**, then right-click it again → uncheck **Show Header**.
   4. On the Marks card, open the **SUM(Fair line)** tab. Remove `label_season` from Color on this tab only, set
      Opacity to **0%**, and make Size the smallest. The dots become invisible.
   5. **Analysis → Trend Lines → Show All Trend Lines.** Right-click the trend line → **Edit All Trend Lines…**:
      Model type **Linear**, uncheck **Allow a trend line per color**, uncheck **Show confidence bands**.
      In the **Allow trend lines on** section, keep only `Fair line`. Since Fair line *equals* fair value, the
      fitted line is exactly y = x.
   6. Right-click the trend line → **Format…** → dashed, dark gray, 1 pt.
   7. Points **above** the line are paid more than their fair value; points **below** are paid less.
6. **Shape as a second cue for color-blind and grayscale viewers.** On the **SUM(actual_pct_of_cap)** Marks tab,
   drag `label_season` to **Shape**. Click Shape and assign: Overpaid ▲, Underpaid ▼, Fair ●, Limited sample ◆,
   Rookie contract ■.
7. **Axis titles:** right-click each axis → **Edit Axis…** → title *Fair value (% of cap)* for the x axis and
   *Actual pay (% of cap)* for the y axis.
8. **Tooltip:** click **Tooltip** on the Marks card and replace the text with:
   ```
   <player_name>  ·  <position>, <team> <season>
   Paid <SUM(actual_musd)>  ·  Worth <SUM(fair_musd)>
   Gap <SUM(gap_musd)>  ·  <label_season>
   Click to see details
   ```
   (Drag `actual_musd`, `fair_musd`, `gap_musd`, `position` and `team` to **Tooltip** on the Marks card first, so
   you can insert them.)
9. Optional: a filter on `is_rookie_contract` lets viewers hide the 283 rookie-contract dots and focus on veterans.

## 6. Sheet 4: Team value with a Season / 3-year toggle

1. New sheet → rename **Team value**. In the Data pane, switch to the **team_value** data source.
2. **The toggle parameter.**
   1. In the Data pane, click the ▾ at the top → **Create Parameter…**
   2. Name `Value view`, Data type **String**, Allowable values **List**. Add two values, `Season` and `3-year`.
      Current value: `Season` → **OK**.
   3. Right-click `Value view` in the Parameters section → **Show Parameter**. Then, on its card ▾ → **Single Value List**
      (radio buttons).
3. **Calculated fields** (Analysis → Create Calculated Field…):
   - `Net value ($M)`:
     ```
     IF [Value view] = "Season" THEN SUM([net_value_musd])
     ELSE SUM([net_value_3yr_musd])
     END
     ```
     Format it as Currency, 1 decimal, suffix `M` (right-click → Default Properties → Number Format).
   - `Surplus or deficit`:
     ```
     IF [Net value ($M)] >= 0 THEN "Surplus" ELSE "Deficit" END
     ```
4. Drag `team` to **Rows** and `Net value ($M)` to **Columns**. Marks → **Bar**.
5. Sort: click the `team` pill ▾ → **Sort…** → By **Field**, Descending, `Net value ($M)`. The bars re-sort when the toggle changes.
6. Drag `Surplus or deficit` to **Color**: Surplus `#0072B2`, Deficit `#D55E00`.
7. Drag `Net value ($M)` to **Label** (Label → Show mark labels) so each bar shows its value, then format the labels in a muted gray.
8. Add a zero line: right-click the x axis → **Add Reference Line** → Constant `0` → line dark gray.
9. **Season filter:** drag `season` to Filters → All → Show Filter.
   - With both seasons selected, bars are 2024 + 2025 combined. To keep this filter in sync with the player sheets,
     open the filter card ▾ → **Apply to Worksheets → All Using Related Data Sources**. This works because both files
     have a field named `season`. If Tableau asks, check that `season` is linked under **Data → Edit Blend Relationships**.
10. Change the sheet title (double-click it) to: `Team net value, <Parameters.Value view> label ($M)`, so the title
    tells viewers which view they're looking at.
11. **Tooltip:** add `n_overpaid`, `n_underpaid`, `n_rookie`, `n_durability_concern` to Tooltip and write:
    `<team>: <AGG(Net value ($M))> net · <SUM(n_overpaid)> overpaid, <SUM(n_underpaid)> underpaid, <SUM(n_rookie)> on rookie deals`.

---

## 7. Build the dashboard

1. Click the **New Dashboard** icon (right of the sheet tabs). Rename the tab **Who's worth their contract?**
2. **Size** (left panel): **Fixed size → Custom**, 1400 × 950. A fixed size renders consistently on Tableau Public.
3. **Title:** check **Show dashboard title** at the bottom left. Double-click the title and type:
   **Who's worth their contract? NFL QB/RB/WR/TE value vs pay, 2024–2025**
4. **Takeaway:** drag a **Text** object (Objects section) under the title and type one sentence:
   > Across 2024–25, Denver got the most on-field value beyond its pay (+$116.9M net), while Cleveland got the least
   > (−$41.1M), driven by Deshaun Watson's contract.

   These numbers come from `exports/team_value.csv` (season label, both seasons summed). If you re-run the pipeline,
   re-check them there before publishing.
5. **Layout.** Drag sheets from the left panel onto the canvas:
   - **Left, about 60% width:** **Value scatter** on top, **Team value** below it.
   - **Right, about 40% width:** **Player lookup** on top, **Reasons** directly below it.
   - The filter cards (player search, season, position) and the **Value view** parameter appear automatically on
     the right. Drag the **player_name** search box and the **season**/**position** filters into one row above the lookup.
     Drag the **Value view** toggle right above the Team value chart.
   - Remove duplicate legends: keep one `label_season` color/shape legend next to the scatter, and close the others
     (click the legend → × in its top-right corner).
6. **Click a point → update the lookup.**
   1. **Dashboard → Actions… → Add Action ▸ → Filter…**
   2. Name: `Select player`. Source Sheets: only **Value scatter**. Run action on: **Select**.
   3. Target Sheets: **Player lookup** and **Reasons**.
   4. Clearing the selection will: **Show all values**.
   5. Filter: **Selected Fields** → add `gsis_id` and `season` (both source and target fields have the same name) → **OK**.
   6. Test it: click a dot, and the lookup and reasons show that one player-season. Click empty space and they reset.
      Note that the search box and the click both filter the lookup. If the search box has "Allen" in it and you
      click a non-Allen dot, the lookup goes blank. Clear the search box first.
7. Optional: **Dashboard → Actions → Add Action → Highlight**, Source **Player lookup**, Target **Value scatter**,
   Run on **Hover**. Hovering a lookup row then highlights that player's dot.
8. Click **Presentation mode** (the ▶ icon at the right end of the toolbar) and click around to test: search,
   filters, a scatter click, and the toggle.

---

## 8. Publish to Tableau Public

1. **File → Save to Tableau Public As…** (Tableau Public can only save to the web, not to your Mac).
2. Sign in to your Tableau Public account, or click **Create one now for free**.
3. Name the workbook **NFL Player Value Model** → **Save**. Tableau extracts the data and uploads it. When it finishes,
   your browser opens the published viz.
4. On the viz page, click the **gear / Edit Details** icon:
   - **Title:** NFL Player Value Model
   - **Description:** one paragraph. For example: *"Which NFL players produce more than their contracts pay for? An
     XGBoost model predicts each QB/RB/WR/TE's fair salary (% of cap) from per-game production; the gap to actual pay
     labels players Overpaid, Fair or Underpaid. Code: github.com/vrayapati2005/nfl-player-value"*
   - Turn **Show Sheets as Tabs** **off**, so viewers land on the dashboard and not on the raw sheets.
5. Copy the viz URL into the repo's README and `docs/RESULTS.md`.
6. To update later: change the CSVs, reopen the workbook (**File → Open from Tableau Public…**), and click
   **Data → Refresh All Extracts**. Then **File → Save to Tableau Public** again.

**Note:** everything saved to Tableau Public is public, and the CSV data can be downloaded from the viz page.
That's fine here: the exports contain only public nflverse/OverTheCap data.

---

## Checklist before sharing

- [ ] Search "Allen" → lookup narrows; clicking Josh Allen 2024's dot shows Fair / Fair and his 3 reasons.
- [ ] Toggle Season → 3-year: bars and sort order change (e.g. NYJ goes from positive to negative).
- [ ] Every color has a legend, and the scatter also uses shape.
- [ ] Percent columns read "3.2%", not "320%" (if not, see the number formats in section 1).
- [ ] The takeaway's numbers match `exports/team_value.csv`.
