def normalize_player(raw_player: dict) -> dict:
    return {
        'player_id': raw_player['player_id'],
        'full_name': raw_player['first_name'] + ' ' + raw_player['last_name'],
        'first_name': raw_player['first_name'],
        'last_name': raw_player['last_name']
    }

def normalize_player_game_stats(raw_player: dict, game_context: dict) -> dict:
    # Determine home/away
    is_home = raw_player['team_id'] == game_context['home_team_id']
    
    # Get team's point differential from game_context
    point_diff = game_context.get('point_differential', {}).get(raw_player['team_id'], 0)
    
    # Determine win/loss
    is_win = None
    if point_diff > 0:
        is_win = True
    elif point_diff < 0:
        is_win = False
    # point_diff == 0 means tie, leave as None
    
    return {
        'game_id': raw_player['game_id'],
        'player_id': raw_player['player_id'],
        'team_id': raw_player['team_id'],
        'opponent_team_id': game_context['away_team_id'] if is_home else game_context['home_team_id'],
        'is_win': is_win,
        'point_differential': point_diff,
        'is_home': is_home,
        'minutes': raw_player['minutes'],
        'pts': raw_player['pts'],
        'reb': raw_player['reb'],
        'oreb': raw_player['oreb'],
        'dreb': raw_player['dreb'],
        'ast': raw_player['ast'],
        'stl': raw_player['stl'],
        'blk': raw_player['blk'],
        'tov': raw_player['tov'],
        'fgm': raw_player['fgm'],
        'fga': raw_player['fga'],
        'fg3a': raw_player['fg3a'],
        'fg3m': raw_player['fg3m'],
        'fta': raw_player['fta'],
        'ftm': raw_player['ftm'],
        'plus_minus': raw_player['plus_minus'],
        'fouls': raw_player['fouls']
    }

def normalize_team(raw_team: dict) -> dict:
    return {
        'team_id': raw_team['team_id'],
        'abbreviation': raw_team['team_abbreviation'],
        'full_name': raw_team['team_name'],
        'city': raw_team['team_city']
    }


def normalize_team_game_stats(raw_team: dict, game_context: dict) -> dict:
    team_points = raw_team['points']
    point_diff = raw_team['diff']
    opponent_points = team_points + point_diff
    
    # Determine win/loss
    is_win = None
    if point_diff > 0:
        is_win = True
    elif point_diff < 0:
        is_win = False
    # point_diff == 0 means tie, leave as None
    
    # Determine home/away
    is_home = raw_team['team_id'] == game_context['home_team_id']
    
    return {
        'game_id': raw_team['game_id'],
        'team_id': raw_team['team_id'],
        'opponent_team_id': game_context['away_team_id'] if is_home else game_context['home_team_id'],
        'is_win': is_win,
        'point_differential': point_diff,
        'is_home': is_home,
        'pf': team_points,
        'pa': opponent_points,
        'reb': raw_team['reb'],
        'oreb': raw_team['oreb'],
        'dreb': raw_team['dreb'],
        'ast': raw_team['ast'],
        'tov': raw_team['tov'],
        'fouls': raw_team['fouls'],
        'fgm': raw_team['fgm'],
        'fga': raw_team['fga'],
        'fg3a': raw_team['fg3a'],
        'fg3m': raw_team['fg3m'],
        'fta': raw_team['fta'],
        'ftm': raw_team['ftm'],
        'stl': raw_team['steals'],
        'blk': raw_team['blocks']
    }

def normalize_game(raw_game: dict, team_stats: list = None) -> dict:
    # Extract scores from team stats if provided
    home_score = None
    away_score = None
    
    if team_stats:
        for team in team_stats:
            if team['team_id'] == raw_game['home_team_id']:
                home_score = team['points']
            elif team['team_id'] == raw_game['away_team_id']:
                away_score = team['points']
    
    return {
        'game_id': raw_game['game_id'],
        'game_date': raw_game['game_date'],
        'season': raw_game['season'],
        'season_type': raw_game['season_type'],
        'home_team_id': raw_game['home_team_id'],
        'away_team_id': raw_game['away_team_id'],
        'home_score': home_score,
        'away_score': away_score,
        'status': raw_game['status']
    }


