from nba_api.stats.endpoints import scoreboardv3
from nba_api.stats.endpoints import boxscoretraditionalv3
from nba_api.stats.endpoints import boxscoresummaryv3
import os
import pandas as pd
import pprint


NBA_API_TIMEOUT_SECONDS = int(os.getenv("NBA_API_TIMEOUT_SECONDS", "90"))

def get_season_info_from_game_id(game_id: str) -> dict:
    season_year = int(game_id[3:5])
    season_start = 2000 + season_year
    season_end = season_start + 1

    season = f"{season_start}-{str(season_end)[-2:]}"

    game_type_code = game_id[2]

    season_type_map = {
        "1": "Pre Season",
        "2": "Regular Season",
        "3": "All-Star",
        "4": "Playoffs",
        "5": "Play-In",
        "6": "In-Season Tournament",
    }

    season_type = season_type_map.get(game_type_code, "Unknown")

    return {
        "season": season,
        "season_type": season_type
    }

def get_games_for_date(game_date: str) -> list[dict]:
    games = scoreboardv3.ScoreboardV3(
        game_date=game_date,
        timeout=NBA_API_TIMEOUT_SECONDS,
    )
    df =  games.line_score.get_data_frame()
    gameIds = list(df.gameId.unique())

    out = []

    for game_id in gameIds:
        game_out = {}

        one_game = df[df['gameId'] == game_id]
        team_ids = list(one_game.teamId)
        
        game_out['game_id'] = game_id
        game_out['game_date'] = game_date
        game_out['home_team_id'] = int(team_ids[0])
        game_out['away_team_id'] = int(team_ids[1])
        game_out['season'] = get_season_info_from_game_id(game_id)['season']
        game_out['season_type'] = get_season_info_from_game_id(game_id)['season_type']
        game_out['status'] = 'Final'

        out.append(game_out)

    return out

def get_boxscore_for_game(game_id: str) -> dict:
    boxscore = boxscoretraditionalv3.BoxScoreTraditionalV3(
        game_id=game_id,
        timeout=NBA_API_TIMEOUT_SECONDS,
    )
    game = boxscoresummaryv3.BoxScoreSummaryV3(
        game_id=game_id,
        timeout=NBA_API_TIMEOUT_SECONDS,
    )

    df_player = boxscore.player_stats.get_data_frame()
    df_team = boxscore.team_stats.get_data_frame()
    df_game_summary = game.game_summary.get_data_frame()
    df_game_info = game.game_info.get_data_frame()

    def safe_int(value):
        return None if pd.isna(value) else int(value)

    out = {}
    out['game'] = {
        'game_id': game_id,
        'status': df_game_summary['gameStatusText'].iloc[0],
        'home_team_id': safe_int(df_game_summary['homeTeamId'].iloc[0]),
        'away_team_id': safe_int(df_game_summary['awayTeamId'].iloc[0]),
        'game_date': df_game_info['gameDate'].iloc[0],
        'season': get_season_info_from_game_id(game_id)['season'],
        'season_type': get_season_info_from_game_id(game_id)['season_type']
    }

    out['player'] = []

    for _, one_player in df_player.iterrows():

        minutes_raw = one_player.get("minutes")
        minutes = (
            sum(int(x) / 60**i for i, x in enumerate(minutes_raw.split(":")))
            if isinstance(minutes_raw, str) and minutes_raw != ""
            else 0
        )

        one_player_boxscore = {
            "game_id": game_id,
            "player_id": safe_int(one_player["personId"]),

            "first_name": one_player['firstName'],
            "last_name": one_player['familyName'],
            "team_id": safe_int(one_player["teamId"]),
            "team_abbreviation": one_player["teamTricode"],

            "minutes": minutes,

            "pts": safe_int(one_player.get("points")),
            "reb": safe_int(one_player.get("reboundsTotal")),
            "ast": safe_int(one_player.get("assists")),
            "stl": safe_int(one_player.get("steals")),
            "blk": safe_int(one_player.get("blocks")),
            "tov": safe_int(one_player.get("turnovers")),
            "fouls": safe_int(one_player.get("foulsPersonal")),

            "fgm": safe_int(one_player.get("fieldGoalsMade")),
            "fga": safe_int(one_player.get("fieldGoalsAttempted")),
            "fg3m": safe_int(one_player.get("threePointersMade")),
            "fg3a": safe_int(one_player.get("threePointersAttempted")),
            "ftm": safe_int(one_player.get("freeThrowsMade")),
            "fta": safe_int(one_player.get("freeThrowsAttempted")),

            "oreb": safe_int(one_player.get("reboundsOffensive")),
            "dreb": safe_int(one_player.get("reboundsDefensive")),

            "plus_minus": safe_int(one_player.get("plusMinusPoints")),
        }

        out['player'].append(one_player_boxscore)

    out['team'] = []

    for _, one_team in df_team.iterrows():

        one_team_boxscore = {
            'game_id': game_id,
            'team_id': safe_int(one_team["teamId"]),
            'team_name': one_team.get('teamName'),
            'team_abbreviation': one_team.get('teamTricode'),
            'team_city': one_team.get('teamCity'),

            'points': safe_int(one_team.get('points')),
            'diff': safe_int(one_team.get('plusMinusPoints')),
            'reb': safe_int(one_team.get('reboundsTotal')),
            'oreb': safe_int(one_team.get('reboundsOffensive')),
            'dreb': safe_int(one_team.get('reboundsDefensive')),

            'ast': safe_int(one_team.get('assists')),
            'tov': safe_int(one_team.get('turnovers')),

            'fgm': safe_int(one_team.get('fieldGoalsMade')),
            'fga': safe_int(one_team.get('fieldGoalsAttempted')),
            'fg3m': safe_int(one_team.get('threePointersMade')),
            'fg3a': safe_int(one_team.get('threePointersAttempted')),

            'ftm': safe_int(one_team.get('freeThrowsMade')),
            'fta': safe_int(one_team.get('freeThrowsAttempted')),

            'steals': safe_int(one_team.get('steals')),
            'blocks': safe_int(one_team.get('blocks')),
            'fouls': safe_int(one_team.get('foulsPersonal')),
        }

        out['team'].append(one_team_boxscore)

    return out


if __name__ == '__main__':
    out = get_boxscore_for_game('0022500678')
    pprint.pprint(out)
