# NBA Chatbot Capability Documentation

This document describes the basketball questions the NBA stats chatbot can answer. It focuses only on chatbot capabilities, not project setup or deployment.

The chatbot answers questions from the structured NBA data available in the application database. It can reason over player game stats, team game stats, game dates, seasons, season types, opponents, wins/losses, home/away context, point differential, and player presence or absence. It can also combine multiple query results when a question requires comparison, records, multiple leaderboards, or a cohort defined by another query.

## Core Data Coverage

The chatbot supports two main statistical scopes:

- Player game statistics: individual player box-score rows for games in which the player logged minutes.
- Team game statistics: team-level box-score rows for each game.

It can answer questions about NBA players, teams, opponents, and league-wide rankings. It recognizes common team names, cities, abbreviations, and aliases such as `Warriors`, `Golden State`, `GSW`, `Lakers`, `Cavs`, `Sixers`, and `Dubs`. It can also resolve player names, partial names, and common variants when the database can identify them. If a name is ambiguous, the conversation endpoint can ask for clarification.

## Supported Time and Competition Filters

Questions may include these time and game-type constraints:

- Specific season, such as `2025-26`
- Season type, including `Regular Season`, `Playoffs`, `Play-In`, `Pre Season`, `All-Star`, and `In-Season Tournament`
- Date ranges
- Last N games
- Home or away games
- Wins or losses
- Games decided by a point-differential range
- Clutch games, interpreted as games decided by 5 points or fewer
- Close games, interpreted as games decided by 10 points or fewer
- Blowout games, interpreted as games decided by 15 points or more

Format:

- `What did [player/team] average in [season/season type]?`
- `What were [player/team]'s last [N] games?`
- `How did [player/team] perform between [date] and [date]?`
- `How did [player/team] perform in [wins/losses/home games/away games/close games/clutch games/blowouts]?`

Examples:

- `What were Steph Curry's last 5 regular season games in 2025-26?`
- `What were the Warriors' regular season team games between 2026-01-01 and 2026-02-15?`
- `How did LeBron James perform in Lakers wins this season?`
- `What did the Celtics average in close games?`
- `How did the Knicks perform in blowout wins?`

## Player Statistical Questions

The chatbot can answer player-level questions using raw game logs or aggregated statistics.

Supported raw and aggregate player stats include:

- Points, rebounds, assists, steals, blocks, turnovers
- Made/attempted field goals, threes, and free throws
- Offensive rebounds, defensive rebounds
- Minutes, fouls, plus-minus
- Games played/counts
- Minimum, maximum, average, sum, and standard deviation

Format:

- `What are [player]'s [stats] in [timeframe]?`
- `How many [stat] did [player] have in [timeframe/context]?`
- `What were [player]'s best/worst/highest/lowest [stat] games?`
- `What is [player]'s average/min/max/total/std dev for [stat]?`

Examples:

- `What were Steph Curry's average points, rebounds, assists, and turnovers in the 2025-26 regular season?`
- `How many threes did LeBron make against the Cavs?`
- `What was Nikola Jokic's highest assist game this season?`
- `What was Jayson Tatum's standard deviation in points in the regular season?`
- `Show Kevin Durant's games with at least 30 points.`

## Player Recent-Game Questions

For recent-game questions, the chatbot can return both a summary and game-by-game rows when individual game data is available.

Format:

- `What were [player]'s last [N] games?`
- `What has [player] averaged over the last [N] games?`
- `Show [player]'s recent games against [team/opponent].`

Examples:

- `What were Steph Curry's last 5 regular season games in 2025-26?`
- `What were Luka Doncic's stats over his last 10 games?`
- `Show Anthony Edwards' last 3 games against the Nuggets.`

## Player Opponent Splits

The chatbot can break down one player's performance by opponent or against a specific opponent.

Format:

- `How does [player] perform against [team]?`
- `How did [player] perform against each opponent?`
- `Against which opponents did [player] have the highest [stat/metric]?`

Examples:

- `What were Steph Curry's averages against the Spurs in the 2025-26 regular season?`
- `How did Steph Curry perform against each opponent in the 2025-26 regular season?`
- `Which opponents did Steph Curry score the most total points against?`
- `Against which opponents did Steph Curry have the highest true shooting percentage?`

## Team Statistical Questions

The chatbot can answer team-level offensive questions using team box-score data.

Supported team stats include:

- Points for, points allowed
- Rebounds, offensive rebounds, defensive rebounds
- Assists, steals, blocks, turnovers, fouls
- Made/attempted field goals, threes, and free throws
- Games played/counts
- Minimum, maximum, average, sum, and standard deviation

Format:

- `What did [team] average in [timeframe]?`
- `How many [team stat] did [team] have in [context]?`
- `What were [team]'s last [N] games?`
- `How did [team] perform in [wins/losses/home/away/close games/blowouts]?`

Examples:

- `What were the Warriors' average points for, points allowed, rebounds, assists, and turnovers in the 2025-26 regular season?`
- `What were the Warriors' last 5 regular season team games in 2025-26?`
- `How many rebounds did the Lakers average at home?`
- `What was the Nuggets' record in close games?`

## Defensive, Allowed, and Forced Team Questions

The chatbot can answer defensive questions by using opponent-perspective team stats.

Format:

- `How many [stats] did [team] allow?`
- `Which teams allowed the most/fewest [stat]?`
- `Which teams forced the most turnovers?`
- `What shooting percentages did [team] allow?`

Examples:

- `How many points, rebounds, assists, and turnovers did the Warriors allow on average in the 2025-26 regular season?`
- `How many turnovers and steals did the Warriors force on average?`
- `Which teams forced the most turnovers in the 2025-26 regular season?`
- `Which teams allowed the fewest points per game?`
- `What shooting percentages did the Warriors allow?`
- `Which teams allowed the lowest effective field goal percentage?`

## Player Leaderboards

The chatbot can rank players across the league, within a team, or against a specific opponent/team.

Format:

- `Which players had the highest/lowest [stat/metric] in [timeframe]?`
- `Which [team] players averaged the most [stat]?`
- `Which opposing players averaged the most [stat] against [team]?`
- `Which players had the highest/lowest standard deviation in [stat]?`

Examples:

- `Which players had the highest scoring averages in the 2025-26 regular season?`
- `Which Warriors players averaged the most points, rebounds, and assists?`
- `Which opposing players averaged the most points against the Warriors?`
- `Which players had the lowest standard deviation in points with a minimum of 40 games played?`
- `Among players who average at least 15 points per game, who had the lowest standard deviation in points?`

## Team Leaderboards

The chatbot can rank teams across offensive, defensive, rebounding, ball-control, and shooting categories.

Format:

- `Which teams had the most/fewest [stat/metric] in [timeframe]?`
- `Which teams scored/allowed/forced the most [stat]?`
- `Which teams had the best/worst [shooting metric]?`

Examples:

- `Which teams scored the most points per game in the 2025-26 regular season?`
- `Which teams averaged the most rebounds, offensive rebounds, and defensive rebounds?`
- `Which teams allowed the fewest rebounds per game?`
- `Which teams had the best offensive shooting percentages?`
- `Which teams had the lowest defensive rating?`

## Multiple Independent Leaderboards

If a user asks for several separate rankings, the chatbot can run one leaderboard per requested stat and synthesize the results.

Format:

- `Who leads in [stat A], [stat B], and [stat C] against [team/context]?`
- `Top teams in [stat A], [stat B], and [stat C].`

Examples:

- `Who scores, rebounds, and assists the most against the Warriors?`
- `Top teams in points, rebounds, and assists this season.`
- `Which Warriors players lead the team in points, assists, and rebounds?`

## Comparisons

The chatbot can compare players, teams, and contextual splits when the needed data can be represented by one or more supported queries.

Format:

- `Compare [player A] and [player B] in [timeframe].`
- `Compare [team A] and [team B] in [timeframe].`
- `How does [player/team] perform in [context A] versus [context B]?`
- `How does [team] perform with [player] versus without [player]?`

Examples:

- `Compare Steph Curry and LeBron James this season.`
- `Compare Warriors vs Lakers stats in the 2025-26 regular season.`
- `How does Jalen Brunson perform in wins vs losses?`
- `How do the Warriors perform with Steph Curry versus without Steph Curry?`

## Team Records

The chatbot can calculate records by counting wins and losses, including contextual records.

Format:

- `What is [team]'s record in [timeframe/context]?`
- `What is [team]'s record with/without [player]?`
- `What is [team]'s record in [home/away/close/blowout] games?`

Examples:

- `What is the Warriors' record this season?`
- `What is the Warriors' record this season without Steph Curry?`
- `What is the Celtics' record in close games?`
- `What is the Lakers' home record in the regular season?`

## Player Presence and Absence Questions

The chatbot can filter games based on whether one or more players played. Player rows with zero minutes do not count as played games.

Format:

- `How does [team/player] perform when [player] plays?`
- `How does [team/player] perform when [player] does not play?`
- `Compare [team/player] with [player] versus without [player].`

Examples:

- `What is the Warriors' record without Steph Curry?`
- `How do the Grizzlies perform when Ja Morant plays?`
- `How does Anthony Davis average when LeBron James does not play?`
- `Compare the Lakers' points per game with LeBron versus without LeBron.`

## Stat Threshold Questions

The chatbot can filter individual games by stat thresholds.

Format:

- `Show [player/team] games with at least [number] [stat].`
- `How often did [player] have at least [number] [stat]?`
- `What did [player/team] average in games where [stat threshold] was met?`

Examples:

- `Show Steph Curry's 30+ point games this season.`
- `How did Giannis Antetokounmpo perform in games with at least 10 rebounds?`
- `What did the Nuggets average in games where they had 30 or more assists?`
- `Show players who had at least 10 points and 10 rebounds.`

## Aggregate Threshold Questions

The chatbot can filter grouped leaderboards by aggregate thresholds such as average, total, minimum, maximum, count, or standard deviation.

Format:

- `Among players/teams who average at least [threshold], who has the highest/lowest [stat/metric]?`
- `Among players whose season high was at least [threshold], who had the highest/lowest [stat/metric]?`
- `Which players with at least [N] games had the highest/lowest [stat/metric]?`

Examples:

- `Among players who average at least 15 points per game, which players had the lowest standard deviation in points?`
- `Among players whose season high was at least 40 points, who had the lowest standard deviation in points?`
- `Which players with at least 60 games had the highest three-point percentage?`
- `Among players who averaged more than 2 steals plus blocks, who had the highest three-point percentage?`

## Season High and Best-Against-Team Questions

The chatbot can compare a player's season maximum against their maximum versus a specific team.

Format:

- `Which players had their season high in [stat] against [team]?`
- `Which players scored their season high versus [team]?`

Examples:

- `Which players scored their season high vs the Warriors this season?`
- `Which players had their best rebounding game against the Lakers?`

## Derived Cohort Questions

The chatbot can answer questions where one query defines a group, then another query analyzes performance against that group.

Format:

- `How does [player/team] perform against the top [N] teams/players that [criterion]?`
- `How does [player/team] perform against teams that allow/force/score the most [stat]?`

Examples:

- `How does Steph Curry play against the 10 teams that force the most turnovers?`
- `How do the Warriors perform against the top 5 defenses?`
- `How does Luka Doncic perform against the teams that allow the fewest points?`

## All-Players-in-a-Game Questions

For questions about the top performer in a team's game, the chatbot can combine that team's players and the opponent's players from the same game.

Format:

- `Who had the most [stat] in the last [team] game?`
- `Who led the [team] game in [stat]?`

Examples:

- `Who scored the most points in the last Lakers game?`
- `Who had the most rebounds in the Warriors' last game?`
- `Who led the last Knicks game in assists?`

## Shooting Percentage Questions

The chatbot can calculate shooting percentages for players and teams from made/attempted shot components.

Supported shooting metrics:

- Field goal percentage
- Three-point percentage
- Free throw percentage
- Effective field goal percentage
- True shooting percentage

Format:

- `What were [player/team]'s shooting percentages in [timeframe]?`
- `Which players/teams had the highest/lowest [shooting metric]?`
- `What shooting percentages did [team] allow?`

Examples:

- `What were Steph Curry's true shooting percentage, effective field goal percentage, field goal percentage, three-point percentage, and free throw percentage?`
- `Against which opponents did Steph Curry have the highest true shooting percentage?`
- `Which teams had the best offensive shooting percentages?`
- `What shooting percentages did the Warriors allow?`

## Advanced Player Metrics

The chatbot can answer player questions using these derived metrics when the required box-score components are available:

- True shooting percentage
- Effective field goal percentage
- Field goal percentage
- Three-point percentage
- Free throw percentage
- Usage rate
- Assist percentage
- Rebound percentage
- Offensive rebound percentage
- Defensive rebound percentage
- Turnover percentage
- Steal percentage
- Block percentage
- Game Score
- Assist-to-turnover ratio
- Points + rebounds
- Points + assists
- Points + rebounds + assists
- Rebounds + assists
- Steals + blocks
- Fantasy score

Some advanced player metrics are simplified calculations based on available box-score columns. Composite prop-style metrics such as points + rebounds, PRA, steals + blocks, and fantasy score are calculated from the selected rows' component stats.

Format:

- `What is [player]'s [advanced metric] in [timeframe/context]?`
- `Which players had the highest/lowest [advanced metric]?`
- `How did [player] perform by [advanced metric] against each opponent?`

Examples:

- `Which Warriors players have the highest usage rate in the last 10 games?`
- `What was Steph Curry's game score average this season?`
- `Which players had the highest assist-to-turnover ratio?`
- `What was Brandon Ingram's fantasy score in wins?`
- `Which players had the highest points + rebounds + assists?`

## Advanced Team Metrics

The chatbot can answer team questions using these derived metrics when the required team box-score components are available:

- Pace
- Offensive rating
- Defensive rating
- Net rating
- Assist ratio
- Team offensive rebound percentage
- Team defensive rebound percentage
- Team turnover percentage
- Shooting percentages listed above

Format:

- `What is [team]'s [advanced metric] in [timeframe/context]?`
- `Which teams had the highest/lowest [advanced metric]?`
- `How did [team] rank by [advanced metric]?`

Examples:

- `What was the Warriors' net rating in the regular season?`
- `Which teams had the best offensive rating?`
- `Which teams had the lowest defensive rating?`
- `What was the Celtics' pace over their last 10 games?`
- `Which teams had the best team turnover percentage?`

## Supported Sorting and Result Limits

Questions can ask for highest, lowest, most, fewest, top N, or bottom N results.

Format:

- `Top [N] [players/teams] by [stat/metric].`
- `Which [players/teams] had the highest/lowest [stat/metric]?`
- `Show the [N] best/worst [players/teams] for [stat/metric].`

Examples:

- `Top 10 players by points per game this regular season.`
- `Which teams had the fewest turnovers per game?`
- `Show the 15 Warriors players with the most points per game.`
- `Which players had the highest points standard deviation?`

## Conversational Capabilities

The conversation endpoint can keep recent context and previously resolved entities. This allows follow-up questions that use shorter references after a player or team has already been resolved.

Format:

- First message: `What are Steph Curry's stats this season?`
- Follow-up: `How about against the Lakers?`
- Follow-up: `What about his last 5 games?`

It can also return clarification information when a player or team mention is ambiguous.

Example:

- User: `What are Anthony's stats?`
- Chatbot behavior: asks which Anthony is intended if multiple matching players exist.

## Capability Boundaries

The chatbot should not be documented as supporting capabilities outside the structured data and query planner. In particular, do not assume support for:

- Live scores unless those games have already been ingested into the database
- Future schedules
- Injury reports
- Betting odds, lines, spreads, or sportsbook markets
- Player contracts, salaries, trades, draft picks, standings, or roster transactions
- Play-by-play, shot charts, lineup data, on/off ratings by exact lineup, or tracking data
- Natural-language questions that require external web search or current NBA news
- Non-NBA sports questions
- Arbitrary SQL or unsupported custom formulas

If a requested stat, filter, entity, or time range is not present in the database, the chatbot may return an empty result or an error rather than inventing an answer.
