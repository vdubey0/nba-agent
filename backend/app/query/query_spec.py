from app.db import SessionLocal
from app.models import Player, Team, PlayerGameStats, TeamGameStats, Game
from sqlalchemy import func, cast, Float, case
from sqlalchemy.orm import aliased
import pprint
import json


def validate_query_spec(query_spec: dict) -> dict:
    if type(query_spec) is not dict:
        return {
            "status": "failed",
            "message": "query_spec must be of type dict."
        }

    if 'scope' not in query_spec:
        return {
            "status": "failed",
            "message": "SCOPE not present in query_spec."
        }
    else:
        scope = query_spec['scope'].lower()
        if scope not in ['player_game_stats', 'team_game_stats']:
            return {
                "status": "failed",
                "message": f"Invalid scope {scope}. Valid scopes are: player_game_stats, team_game_stats."
            }

    perspective = query_spec.get('perspective', 'self')
    if type(perspective) is not str:
        return {
            "status": "failed",
            "message": "perspective must be of type str."
        }
    if perspective not in ['self', 'opponent']:
        return {
            "status": "failed",
            "message": "perspective must be one of 'self' or 'opponent'."
        }

    if 'subject' in query_spec:
        if type(query_spec['subject']) is not dict:
            return {
                "status": "failed",
                "message": "Subject field must be of type dict."
            }

        if 'type' not in query_spec['subject']:
            return {
                "status": "failed",
                "message": "Subject 'type' must be specified."
            }
        elif type(query_spec['subject']['type']) is not str:
            return {
                "status": "failed",
                "message": "Subject 'type' must be of type str."
            }
        elif query_spec['subject']['type'] not in ['player', 'team', 'league']:
            return {
                "status": "failed",
                "message": "Subject 'type' must be one of 'player', 'team', or 'league'."
            }

        if query_spec['subject']['type'] in ['player', 'team']:
            if 'id' not in query_spec['subject']:
                return {
                    "status": "failed",
                    "message": "Subject 'id' must be specified for subject types player and team."
                }
            elif type(query_spec['subject']['id']) is not int:
                return {
                    "status": "failed",
                    "message": "Subject 'id' must be of type int."
                }

        if scope == 'player_game_stats':
            if query_spec['subject']['type'] not in ['player', 'team', 'league']:
                return {
                    "status": "failed",
                    "message": "For player_game_stats scope, subject 'type' must be one of player, team, or league."
                }

            if perspective == 'opponent' and query_spec['subject']['type'] == 'player':
                return {
                    "status": "failed",
                    "message": "For player_game_stats, perspective='opponent' is not supported with subject type 'player'. Use subject type 'team' or 'league'."
                }

        elif scope == 'team_game_stats':
            if query_spec['subject']['type'] not in ['team', 'league']:
                return {
                    "status": "failed",
                    "message": "For team_game_stats scope, subject 'type' must be one of team or league."
                }

    allowed_filters = [
        'season',
        'opponent_team_id',
        'date_from',
        'date_to',
        'last_n_games',
        'season_type',
        'game_outcome',  # V2: win/loss filtering
        'is_home',  # V2: home/away filtering
        'min_point_differential',  # V2: close games, blowouts
        'max_point_differential',  # V2: close games, blowouts
        # V3: Category 2 - Conditional aggregations (stat thresholds)
        'min_pts', 'max_pts',
        'min_reb', 'max_reb',
        'min_ast', 'max_ast',
        'min_stl', 'max_stl',
        'min_blk', 'max_blk',
        'min_tov', 'max_tov',
        'min_fgm', 'max_fgm',
        'min_fga', 'max_fga',
        'min_fg3m', 'max_fg3m',
        'min_fg3a', 'max_fg3a',
        'min_ftm', 'max_ftm',
        'min_fta', 'max_fta',
        'min_minutes', 'max_minutes',
        # V3: Category 4 - Player presence/absence
        'present_player_ids',
        'absent_player_ids'
    ]

    if 'filters' in query_spec:
        if type(query_spec['filters']) is not dict:
            return {
                "status": "failed",
                "message": "Filters field must be of type dict."
            }

        for filter_key, filter_val in query_spec['filters'].items():
            if filter_key not in allowed_filters:
                return {
                    "status": "failed",
                    "message": f"Invalid filter '{filter_key}'. Allowed filters are: {allowed_filters}."
                }

            if filter_key == 'season':
                if type(filter_val) is not str:
                    return {
                        "status": "failed",
                        "message": "Filter 'season' must be of type str."
                    }

            elif filter_key == 'opponent_team_id':
                if type(filter_val) is not int:
                    return {
                        "status": "failed",
                        "message": "Filter 'opponent_team_id' must be of type int."
                    }

            elif filter_key == 'date_from':
                if type(filter_val) is not str:
                    return {
                        "status": "failed",
                        "message": "Filter 'date_from' must be of type str in YYYY-MM-DD format."
                    }

            elif filter_key == 'date_to':
                if type(filter_val) is not str:
                    return {
                        "status": "failed",
                        "message": "Filter 'date_to' must be of type str in YYYY-MM-DD format."
                    }

            elif filter_key == 'last_n_games':
                if type(filter_val) is not int:
                    return {
                        "status": "failed",
                        "message": "Filter 'last_n_games' must be of type int."
                    }
                elif filter_val <= 0:
                    return {
                        "status": "failed",
                        "message": "Filter 'last_n_games' must be greater than 0."
                    }

            elif filter_key == 'season_type':
                allowed_season_types = [
                    'Pre Season',
                    'Regular Season',
                    'All-Star',
                    'Playoffs',
                    'Play-In',
                    'In-Season Tournament'
                ]

                if type(filter_val) is not list:
                    return {
                        "status": "failed",
                        "message": "season_type must be of type list."
                    }

                for val in filter_val:
                    if val not in allowed_season_types:
                        return {
                            "status": "failed",
                            "message": f"Each season_type must be one of {allowed_season_types}"
                        }

            elif filter_key == 'game_outcome':
                allowed_outcomes = ['win', 'loss', 'all']
                if type(filter_val) is not str:
                    return {
                        "status": "failed",
                        "message": "Filter 'game_outcome' must be of type str."
                    }
                if filter_val not in allowed_outcomes:
                    return {
                        "status": "failed",
                        "message": f"Filter 'game_outcome' must be one of {allowed_outcomes}"
                    }

            elif filter_key == 'is_home':
                if type(filter_val) is not bool:
                    return {
                        "status": "failed",
                        "message": "Filter 'is_home' must be of type bool."
                    }

            elif filter_key == 'min_point_differential':
                if type(filter_val) is not int:
                    return {
                        "status": "failed",
                        "message": "Filter 'min_point_differential' must be of type int."
                    }

            elif filter_key == 'max_point_differential':
                if type(filter_val) is not int:
                    return {
                        "status": "failed",
                        "message": "Filter 'max_point_differential' must be of type int."
                    }

            # V3: Category 2 - Stat threshold filters
            elif filter_key in ['min_pts', 'max_pts', 'min_reb', 'max_reb', 'min_ast', 'max_ast',
                               'min_stl', 'max_stl', 'min_blk', 'max_blk', 'min_tov', 'max_tov',
                               'min_fgm', 'max_fgm', 'min_fga', 'max_fga', 'min_fg3m', 'max_fg3m',
                               'min_fg3a', 'max_fg3a', 'min_ftm', 'max_ftm', 'min_fta', 'max_fta']:
                if type(filter_val) not in [int, float]:
                    return {
                        "status": "failed",
                        "message": f"Filter '{filter_key}' must be of type int or float."
                    }

            elif filter_key in ['min_minutes', 'max_minutes']:
                if type(filter_val) not in [int, float]:
                    return {
                        "status": "failed",
                        "message": f"Filter '{filter_key}' must be of type int or float."
                    }

            # V3: Category 4 - Player presence/absence filters
            elif filter_key == 'present_player_ids':
                if type(filter_val) is not list:
                    return {
                        "status": "failed",
                        "message": "Filter 'present_player_ids' must be of type list."
                    }
                for player_id in filter_val:
                    if type(player_id) is not int:
                        return {
                            "status": "failed",
                            "message": "Each player_id in 'present_player_ids' must be of type int."
                        }
            
            elif filter_key == 'absent_player_ids':
                if type(filter_val) is not list:
                    return {
                        "status": "failed",
                        "message": "Filter 'absent_player_ids' must be of type list."
                    }
                for player_id in filter_val:
                    if type(player_id) is not int:
                        return {
                            "status": "failed",
                            "message": "Each player_id in 'absent_player_ids' must be of type int."
                        }

    allowed_group_by = ['player_id', 'team_id', 'opponent_team_id']

    if 'group_by' in query_spec:
        if type(query_spec['group_by']) is not list:
            return {
                "status": "failed",
                "message": "group_by field must be of type list."
            }

        if len(query_spec['group_by']) > 1:
            return {
                "status": "failed",
                "message": "For v1, group_by may contain at most one field."
            }

        for field in query_spec['group_by']:
            if type(field) is not str:
                return {
                    "status": "failed",
                    "message": "Each group_by field must be of type str."
                }
            if field not in allowed_group_by:
                return {
                    "status": "failed",
                    "message": f"Invalid group_by field '{field}'. Allowed values are: {allowed_group_by}."
                }
            if scope == 'team_game_stats' and field == 'player_id':
                return {
                    "status": "failed",
                    "message": "group_by field 'player_id' is not valid for team_game_stats scope."
                }

    allowed_agg_values = ['mean', 'sum', 'count', 'min', 'max']

    if 'aggregations' in query_spec:
        if type(query_spec['aggregations']) is not dict:
            return {
                "status": "failed",
                "message": "aggregations field must be of type dict."
            }

        for agg_field, agg_type in query_spec['aggregations'].items():
            if type(agg_field) is not str:
                return {
                    "status": "failed",
                    "message": "Each aggregation field name must be of type str."
                }
            if type(agg_type) is not str:
                return {
                    "status": "failed",
                    "message": f"Aggregation type for field '{agg_field}' must be of type str."
                }
            if agg_type not in allowed_agg_values:
                return {
                    "status": "failed",
                    "message": f"Invalid aggregation '{agg_type}' for field '{agg_field}'. Allowed values are: {allowed_agg_values}."
                }

    allowed_derived_metrics = [
        # Basic shooting percentages (player & team)
        'ts_pct', 'efg_pct', 'fg_pct', 'fg3_pct', 'ft_pct',
        # Advanced player metrics
        'usage_rate', 'ast_pct', 'reb_pct', 'tov_pct', 'stl_pct', 'blk_pct',
        'oreb_pct', 'dreb_pct', 'game_score', 'ast_to_ratio',
        # Advanced team metrics (team only)
        'pace', 'off_rating', 'def_rating', 'net_rating', 'ast_ratio',
        'oreb_pct_team', 'dreb_pct_team', 'tov_pct_team',
        # Betting/Fantasy metrics (player only)
        'pts_reb', 'pts_ast', 'pra', 'reb_ast', 'stl_blk', 'fantasy_score'
    ]

    if 'derived_metrics' in query_spec:
        if type(query_spec['derived_metrics']) is not list:
            return {
                "status": "failed",
                "message": "derived_metrics must be of type list."
            }

        for metric in query_spec['derived_metrics']:
            if type(metric) is not str:
                return {
                    "status": "failed",
                    "message": "Each derived metric must be of type str."
                }
            if metric not in allowed_derived_metrics:
                return {
                    "status": "failed",
                    "message": f"Invalid derived metric '{metric}'. Allowed values are: {allowed_derived_metrics}."
                }

    if 'sort' in query_spec and query_spec['sort'] is not None:
        if type(query_spec['sort']) is not dict:
            return {
                "status": "failed",
                "message": "sort field must be of type dict or None."
            }

        if 'by' not in query_spec['sort']:
            return {
                "status": "failed",
                "message": "sort.by must be specified when sort is present."
            }
        if 'direction' not in query_spec['sort']:
            return {
                "status": "failed",
                "message": "sort.direction must be specified when sort is present."
            }

        if type(query_spec['sort']['by']) is not str:
            return {
                "status": "failed",
                "message": "sort.by must be of type str."
            }

        if type(query_spec['sort']['direction']) is not str:
            return {
                "status": "failed",
                "message": "sort.direction must be of type str."
            }

        if query_spec['sort']['direction'] not in ['asc', 'desc']:
            return {
                "status": "failed",
                "message": "sort.direction must be one of 'asc' or 'desc'."
            }

    if 'limit' in query_spec and query_spec['limit'] is not None:
        if type(query_spec['limit']) is not int:
            return {
                "status": "failed",
                "message": "limit must be of type int or None."
            }
        if query_spec['limit'] <= 0:
            return {
                "status": "failed",
                "message": "limit must be greater than 0."
            }

    return {
        "status": "success",
        "message": "query_spec is valid."
    }


def run_query_spec(session, query_spec: dict) -> dict:
    validate_out = validate_query_spec(query_spec=query_spec)

    if validate_out['status'] == 'failed':
        return {
            'status': 'failed',
            'message': f"Invalid query spec: {validate_out['message']}"
        }

    scope_name = query_spec['scope'].lower()
    perspective = query_spec.get('perspective', 'self')

    base_scope = PlayerGameStats if scope_name == 'player_game_stats' else TeamGameStats

    filters = dict(query_spec.get('filters', {}))
    season_types = filters.get(
        'season_type',
        ['Regular Season', 'Play-In', 'Playoffs', 'In-Season Tournament']
    )

    subject = query_spec.get('subject')
    group_by = query_spec.get('group_by', [])
    aggregations = query_spec.get('aggregations', {})
    derived_metrics = query_spec.get('derived_metrics', [])

    has_group_by = len(group_by) > 0
    has_aggs = len(aggregations) > 0
    has_derived = len(derived_metrics) > 0

    # ---------------------------------------------------
    # STEP 1: build base query INCLUDING game_date column
    # ---------------------------------------------------
    base_query = (
        session.query(
            base_scope,
            Game.game_date.label("game_date")
        )
        .join(Game, base_scope.game_id == Game.game_id)
    )

    if subject:
        if scope_name == 'player_game_stats':
            if subject['type'] == 'player':
                base_query = base_query.filter(base_scope.player_id == subject['id'])
            elif subject['type'] == 'team':
                if perspective == 'self':
                    base_query = base_query.filter(base_scope.team_id == subject['id'])
                else:
                    base_query = base_query.filter(base_scope.opponent_team_id == subject['id'])
        else:
            if subject['type'] == 'team':
                base_query = base_query.filter(base_scope.team_id == subject['id'])

    if 'season' in filters:
        base_query = base_query.filter(Game.season == filters['season'])

    if 'opponent_team_id' in filters:
        base_query = base_query.filter(base_scope.opponent_team_id == filters['opponent_team_id'])

    if 'date_from' in filters:
        base_query = base_query.filter(Game.game_date >= filters['date_from'])

    if 'date_to' in filters:
        base_query = base_query.filter(Game.game_date <= filters['date_to'])

    base_query = base_query.filter(Game.season_type.in_(season_types))

    # V2: Add game outcome filters
    if 'game_outcome' in filters:
        outcome = filters['game_outcome']
        if outcome == 'win':
            base_query = base_query.filter(base_scope.is_win == True)
        elif outcome == 'loss':
            base_query = base_query.filter(base_scope.is_win == False)
        # 'all' means no filter

    if 'is_home' in filters:
        base_query = base_query.filter(base_scope.is_home == filters['is_home'])

    if 'min_point_differential' in filters:
        base_query = base_query.filter(base_scope.point_differential >= filters['min_point_differential'])

    if 'max_point_differential' in filters:
        base_query = base_query.filter(base_scope.point_differential <= filters['max_point_differential'])

    # V3: Category 2 - Apply stat threshold filters
    stat_threshold_filters = {
        'min_pts': ('pts', '>='), 'max_pts': ('pts', '<='),
        'min_reb': ('reb', '>='), 'max_reb': ('reb', '<='),
        'min_ast': ('ast', '>='), 'max_ast': ('ast', '<='),
        'min_stl': ('stl', '>='), 'max_stl': ('stl', '<='),
        'min_blk': ('blk', '>='), 'max_blk': ('blk', '<='),
        'min_tov': ('tov', '>='), 'max_tov': ('tov', '<='),
        'min_fgm': ('fgm', '>='), 'max_fgm': ('fgm', '<='),
        'min_fga': ('fga', '>='), 'max_fga': ('fga', '<='),
        'min_fg3m': ('fg3m', '>='), 'max_fg3m': ('fg3m', '<='),
        'min_fg3a': ('fg3a', '>='), 'max_fg3a': ('fg3a', '<='),
        'min_ftm': ('ftm', '>='), 'max_ftm': ('ftm', '<='),
        'min_fta': ('fta', '>='), 'max_fta': ('fta', '<='),
        'min_minutes': ('minutes', '>='), 'max_minutes': ('minutes', '<='),
    }
    
    for filter_key, (stat_col, operator) in stat_threshold_filters.items():
        if filter_key in filters:
            col = getattr(base_scope, stat_col, None)
            if col is not None:
                if operator == '>=':
                    base_query = base_query.filter(col >= filters[filter_key])
                else:  # operator == '<='
                    base_query = base_query.filter(col <= filters[filter_key])

    # V3: Category 4 - Filter for games where present players played
    if 'present_player_ids' in filters:
        present_ids = filters['present_player_ids']
        if len(present_ids) > 0:
            # Subquery to find game_ids where ALL present players have records
            for player_id in present_ids:
                games_with_player = (
                    session.query(PlayerGameStats.game_id)
                    .filter(PlayerGameStats.player_id == player_id)
                    .distinct()
                    .subquery()
                )
                # Include only games where this player played
                base_query = base_query.filter(base_scope.game_id.in_(
                    session.query(games_with_player.c.game_id)
                ))
    
    # V3: Category 4 - Filter out games where absent players played
    if 'absent_player_ids' in filters:
        absent_ids = filters['absent_player_ids']
        if len(absent_ids) > 0:
            # Subquery to find game_ids where any absent player has a record
            games_with_absent_players = (
                session.query(PlayerGameStats.game_id)
                .filter(PlayerGameStats.player_id.in_(absent_ids))
                .distinct()
                .subquery()
            )
            # Exclude those games
            base_query = base_query.filter(~base_scope.game_id.in_(
                session.query(games_with_absent_players.c.game_id)
            ))

    # ----------------------------------------------------
    # STEP 2: handle last_n_games via subquery if needed
    # ----------------------------------------------------
    if 'last_n_games' in filters:
        # First, get the last N game IDs (not rows, but actual games)
        last_n_game_ids_subq = (
            base_query
            .with_entities(base_scope.game_id, Game.game_date)
            .distinct()
            .order_by(Game.game_date.desc(), base_scope.game_id.desc())
            .limit(filters['last_n_games'])
            .subquery()
        )
        
        # Then get ALL player stats from those games
        limited_subq = (
            base_query
            .filter(base_scope.game_id.in_(
                session.query(last_n_game_ids_subq.c.game_id)
            ))
            .with_entities(
                *[getattr(base_scope, c.name).label(c.name) for c in base_scope.__table__.columns],
                Game.game_date.label("game_date")
            )
            .subquery()
        )

        subject_cols = limited_subq.c
        query = session.query(limited_subq)
        game_date_col = limited_subq.c.game_date
        using_subquery = True
    else:
        subject_cols = base_scope
        game_date_col = Game.game_date
        using_subquery = False

        query = session.query(base_scope).join(Game, base_scope.game_id == Game.game_id)

        if subject:
            if scope_name == 'player_game_stats':
                if subject['type'] == 'player':
                    query = query.filter(base_scope.player_id == subject['id'])
                elif subject['type'] == 'team':
                    if perspective == 'self':
                        query = query.filter(base_scope.team_id == subject['id'])
                    else:
                        query = query.filter(base_scope.opponent_team_id == subject['id'])
            else:
                if subject['type'] == 'team':
                    query = query.filter(base_scope.team_id == subject['id'])

        if 'season' in filters:
            query = query.filter(Game.season == filters['season'])

        if 'opponent_team_id' in filters:
            query = query.filter(base_scope.opponent_team_id == filters['opponent_team_id'])

        if 'date_from' in filters:
            query = query.filter(Game.game_date >= filters['date_from'])

        if 'date_to' in filters:
            query = query.filter(Game.game_date <= filters['date_to'])

        query = query.filter(Game.season_type.in_(season_types))

        # V2: Add game outcome filters (non-subquery path)
        if 'game_outcome' in filters:
            outcome = filters['game_outcome']
            if outcome == 'win':
                query = query.filter(base_scope.is_win == True)
            elif outcome == 'loss':
                query = query.filter(base_scope.is_win == False)

        if 'is_home' in filters:
            query = query.filter(base_scope.is_home == filters['is_home'])

        if 'min_point_differential' in filters:
            query = query.filter(base_scope.point_differential >= filters['min_point_differential'])

        if 'max_point_differential' in filters:
            query = query.filter(base_scope.point_differential <= filters['max_point_differential'])

        # V3: Category 2 - Apply stat threshold filters (non-subquery path)
        for filter_key, (stat_col, operator) in stat_threshold_filters.items():
            if filter_key in filters:
                col = getattr(base_scope, stat_col, None)
                if col is not None:
                    if operator == '>=':
                        query = query.filter(col >= filters[filter_key])
                    else:  # operator == '<='
                        query = query.filter(col <= filters[filter_key])

        # V3: Category 4 - Filter for games where present players played (non-subquery path)
        if 'present_player_ids' in filters:
            present_ids = filters['present_player_ids']
            if len(present_ids) > 0:
                # Subquery to find game_ids where ALL present players have records
                for player_id in present_ids:
                    games_with_player = (
                        session.query(PlayerGameStats.game_id)
                        .filter(PlayerGameStats.player_id == player_id)
                        .distinct()
                        .subquery()
                    )
                    # Include only games where this player played
                    query = query.filter(base_scope.game_id.in_(
                        session.query(games_with_player.c.game_id)
                    ))
        
        # V3: Category 4 - Filter out games where absent players played (non-subquery path)
        if 'absent_player_ids' in filters:
            absent_ids = filters['absent_player_ids']
            if len(absent_ids) > 0:
                # Subquery to find game_ids where any absent player has a record
                games_with_absent_players = (
                    session.query(PlayerGameStats.game_id)
                    .filter(PlayerGameStats.player_id.in_(absent_ids))
                    .distinct()
                    .subquery()
                )
                # Exclude those games
                query = query.filter(~base_scope.game_id.in_(
                    session.query(games_with_absent_players.c.game_id)
                ))

    # ----------------------------------------------------
    # STEP 3: aliases / joins for enrichment and opponent team self-join
    # ----------------------------------------------------
    TeamMetaSelf = aliased(Team)
    TeamMetaOpp = aliased(Team)

    opponent_stat_cols = None

    if scope_name == 'player_game_stats':
        if using_subquery:
            query = (
                query
                .join(Player, subject_cols.player_id == Player.player_id)
                .join(TeamMetaSelf, subject_cols.team_id == TeamMetaSelf.team_id)
                .join(TeamMetaOpp, subject_cols.opponent_team_id == TeamMetaOpp.team_id)
            )
        else:
            query = (
                query
                .join(Player, base_scope.player_id == Player.player_id)
                .join(TeamMetaSelf, base_scope.team_id == TeamMetaSelf.team_id)
                .join(TeamMetaOpp, base_scope.opponent_team_id == TeamMetaOpp.team_id)
            )
    else:
        if perspective == 'self':
            if using_subquery:
                query = (
                    query
                    .join(TeamMetaSelf, subject_cols.team_id == TeamMetaSelf.team_id)
                    .join(TeamMetaOpp, subject_cols.opponent_team_id == TeamMetaOpp.team_id)
                )
            else:
                query = (
                    query
                    .join(TeamMetaSelf, base_scope.team_id == TeamMetaSelf.team_id)
                    .join(TeamMetaOpp, base_scope.opponent_team_id == TeamMetaOpp.team_id)
                )
        else:
            OppTeamStats = aliased(TeamGameStats)

            if using_subquery:
                query = (
                    query
                    .join(
                        OppTeamStats,
                        (subject_cols.game_id == OppTeamStats.game_id) &
                        (subject_cols.team_id == OppTeamStats.opponent_team_id) &
                        (subject_cols.opponent_team_id == OppTeamStats.team_id)
                    )
                    .join(TeamMetaSelf, subject_cols.team_id == TeamMetaSelf.team_id)
                    .join(TeamMetaOpp, subject_cols.opponent_team_id == TeamMetaOpp.team_id)
                )
            else:
                query = (
                    query
                    .join(
                        OppTeamStats,
                        (base_scope.game_id == OppTeamStats.game_id) &
                        (base_scope.team_id == OppTeamStats.opponent_team_id) &
                        (base_scope.opponent_team_id == OppTeamStats.team_id)
                    )
                    .join(TeamMetaSelf, base_scope.team_id == TeamMetaSelf.team_id)
                    .join(TeamMetaOpp, base_scope.opponent_team_id == TeamMetaOpp.team_id)
                )

            opponent_stat_cols = OppTeamStats

    # ----------------------------------------------------
    # STEP 4: choose stat source
    # ----------------------------------------------------
    if scope_name == 'team_game_stats' and perspective == 'opponent':
        stat_cols = opponent_stat_cols
    else:
        stat_cols = subject_cols

    # -------------------------
    # STEP 5: build raw aggregations
    # -------------------------
    agg_cols = []
    agg_label_map = {}

    for agg_col, agg_type in aggregations.items():
        col = getattr(stat_cols, agg_col)

        if agg_type == 'mean':
            label = f'{agg_col}_mean'
            expr = func.avg(col).label(label)
        elif agg_type == 'sum':
            label = f'{agg_col}_sum'
            expr = func.sum(col).label(label)
        elif agg_type == 'count':
            label = f'{agg_col}_count'
            expr = func.count(col).label(label)
        elif agg_type == 'min':
            label = f'{agg_col}_min'
            expr = func.min(col).label(label)
        elif agg_type == 'max':
            label = f'{agg_col}_max'
            expr = func.max(col).label(label)
        else:
            continue

        agg_cols.append(expr)
        agg_label_map[label] = expr


    # ----------------------------------------------------
    # STEP 6: build derived metrics from summed components
    # ----------------------------------------------------
    derived_metric_exprs = []
    derived_metric_map = {}

    def metric_component_sum(col_name: str):
        col = getattr(stat_cols, col_name, None)
        if col is None:
            return None
        return func.sum(cast(col, Float))

    # player rows use pts, team rows use pf
    points_col_name = 'pts' if scope_name == 'player_game_stats' else 'pf'

    def safe_pct_expr(numerator, denominator, label: str):
        return case(
            (denominator == 0, None),
            else_=(numerator / denominator)
        ).label(label)

    if 'fg_pct' in derived_metrics:
        fgm_sum = metric_component_sum('fgm')
        fga_sum = metric_component_sum('fga')
        if fgm_sum is None or fga_sum is None:
            return {
                "status": "failed",
                "message": "fg_pct is not supported for this scope."
            }
        expr = safe_pct_expr(fgm_sum, fga_sum, 'fg_pct')
        derived_metric_exprs.append(expr)
        derived_metric_map['fg_pct'] = expr

    if 'fg3_pct' in derived_metrics:
        fg3m_sum = metric_component_sum('fg3m')
        fg3a_sum = metric_component_sum('fg3a')
        if fg3m_sum is None or fg3a_sum is None:
            return {
                "status": "failed",
                "message": "fg3_pct is not supported for this scope."
            }
        expr = safe_pct_expr(fg3m_sum, fg3a_sum, 'fg3_pct')
        derived_metric_exprs.append(expr)
        derived_metric_map['fg3_pct'] = expr

    if 'ft_pct' in derived_metrics:
        ftm_sum = metric_component_sum('ftm')
        fta_sum = metric_component_sum('fta')
        if ftm_sum is None or fta_sum is None:
            return {
                "status": "failed",
                "message": "ft_pct is not supported for this scope."
            }
        expr = safe_pct_expr(ftm_sum, fta_sum, 'ft_pct')
        derived_metric_exprs.append(expr)
        derived_metric_map['ft_pct'] = expr

    if 'efg_pct' in derived_metrics:
        fgm_sum = metric_component_sum('fgm')
        fg3m_sum = metric_component_sum('fg3m')
        fga_sum = metric_component_sum('fga')
        if fgm_sum is None or fg3m_sum is None or fga_sum is None:
            return {
                "status": "failed",
                "message": "efg_pct is not supported for this scope."
            }
        expr = safe_pct_expr(fgm_sum + 0.5 * fg3m_sum, fga_sum, 'efg_pct')
        derived_metric_exprs.append(expr)
        derived_metric_map['efg_pct'] = expr

    if 'ts_pct' in derived_metrics:
        points_sum = metric_component_sum(points_col_name)
        fga_sum = metric_component_sum('fga')
        fta_sum = metric_component_sum('fta')
        if points_sum is None or fga_sum is None or fta_sum is None:
            return {
                "status": "failed",
                "message": "ts_pct is not supported for this scope."
            }
        ts_denom = 2.0 * (fga_sum + 0.44 * fta_sum)
        expr = safe_pct_expr(points_sum, ts_denom, 'ts_pct')
        derived_metric_exprs.append(expr)
        derived_metric_map['ts_pct'] = expr

    # -------------------------
    # Advanced Player Metrics
    # -------------------------
    if 'tov_pct' in derived_metrics:
        tov_sum = metric_component_sum('tov')
        fga_sum = metric_component_sum('fga')
        fta_sum = metric_component_sum('fta')
        if tov_sum is None or fga_sum is None or fta_sum is None:
            return {
                "status": "failed",
                "message": "tov_pct is not supported for this scope."
            }
        tov_denom = fga_sum + 0.44 * fta_sum + tov_sum
        expr = safe_pct_expr(100.0 * tov_sum, tov_denom, 'tov_pct')
        derived_metric_exprs.append(expr)
        derived_metric_map['tov_pct'] = expr

    if 'usage_rate' in derived_metrics:
        # Usage Rate (Player only): Estimate of possessions used while on court
        # Simplified: 100 * (FGA + 0.44*FTA + TOV) / (Team possessions estimate)
        # Without team data, we return a simplified metric based on player activity
        if scope_name != 'player_game_stats':
            return {
                "status": "failed",
                "message": "usage_rate is only supported for player_game_stats scope."
            }
        fga_sum = metric_component_sum('fga')
        fta_sum = metric_component_sum('fta')
        tov_sum = metric_component_sum('tov')
        minutes_sum = metric_component_sum('minutes')
        game_count = agg_label_map.get('game_id_count')
        
        if fga_sum is None or fta_sum is None or tov_sum is None or minutes_sum is None or game_count is None:
            return {
                "status": "failed",
                "message": "usage_rate calculation requires fga, fta, tov, minutes, and game_id count."
            }
        # Simplified usage rate: possessions per 48 minutes
        player_poss = fga_sum + 0.44 * fta_sum + tov_sum
        minutes_per_game = minutes_sum / game_count
        expr = case(
            (minutes_per_game == 0, None),
            else_=((player_poss / minutes_sum) * 48.0)
        ).label('usage_rate')
        derived_metric_exprs.append(expr)
        derived_metric_map['usage_rate'] = expr

    if 'ast_pct' in derived_metrics:
        # Assist Percentage (Player): 100 * AST / (((MP/(Team_MP/5)) * Team_FGM) - FGM)
        # Simplified: assists per field goal made
        if scope_name != 'player_game_stats':
            return {
                "status": "failed",
                "message": "ast_pct is only supported for player_game_stats scope."
            }
        ast_sum = metric_component_sum('ast')
        fgm_sum = metric_component_sum('fgm')
        if ast_sum is None or fgm_sum is None:
            return {
                "status": "failed",
                "message": "ast_pct calculation requires ast and fgm."
            }
        # Simplified: assists per made field goal
        expr = safe_pct_expr(100.0 * ast_sum, fgm_sum, 'ast_pct')
        derived_metric_exprs.append(expr)
        derived_metric_map['ast_pct'] = expr

    if 'reb_pct' in derived_metrics:
        # Rebound Percentage: Simplified as rebounds per game
        # True calculation requires team/opponent data which isn't available in aggregated queries
        reb_sum = metric_component_sum('reb')
        game_count = agg_label_map.get('game_id_count')
        if reb_sum is None or game_count is None:
            return {
                "status": "failed",
                "message": "reb_pct calculation requires reb and game_id count."
            }
        expr = case(
            (game_count == 0, None),
            else_=(reb_sum / game_count)
        ).label('reb_pct')
        derived_metric_exprs.append(expr)
        derived_metric_map['reb_pct'] = expr

    if 'oreb_pct' in derived_metrics:
        oreb_sum = metric_component_sum('oreb')
        game_count = agg_label_map.get('game_id_count')
        if oreb_sum is None or game_count is None:
            return {
                "status": "failed",
                "message": "oreb_pct calculation requires oreb and game_id count."
            }
        if scope_name == 'player_game_stats':
            # For players: offensive rebounds per game
            expr = case(
                (game_count == 0, None),
                else_=(oreb_sum / game_count)
            ).label('oreb_pct')
        else:
            # For team stats, calculate OREB / (OREB + Opp_DREB) if opponent stats available
            if opponent_stat_cols is not None:
                opp_dreb_sum = func.sum(cast(opponent_stat_cols.dreb, Float))
                oreb_denom = oreb_sum + opp_dreb_sum
                expr = safe_pct_expr(100.0 * oreb_sum, oreb_denom, 'oreb_pct')
            else:
                # Without opponent data, return per-game average
                expr = case(
                    (game_count == 0, None),
                    else_=(oreb_sum / game_count)
                ).label('oreb_pct')
        derived_metric_exprs.append(expr)
        derived_metric_map['oreb_pct'] = expr

    if 'dreb_pct' in derived_metrics:
        dreb_sum = metric_component_sum('dreb')
        game_count = agg_label_map.get('game_id_count')
        if dreb_sum is None or game_count is None:
            return {
                "status": "failed",
                "message": "dreb_pct calculation requires dreb and game_id count."
            }
        if scope_name == 'player_game_stats':
            # For players: defensive rebounds per game
            expr = case(
                (game_count == 0, None),
                else_=(dreb_sum / game_count)
            ).label('dreb_pct')
        else:
            # For team stats, calculate DREB / (DREB + Opp_OREB) if opponent stats available
            if opponent_stat_cols is not None:
                opp_oreb_sum = func.sum(cast(opponent_stat_cols.oreb, Float))
                dreb_denom = dreb_sum + opp_oreb_sum
                expr = safe_pct_expr(100.0 * dreb_sum, dreb_denom, 'dreb_pct')
            else:
                # Without opponent data, return per-game average
                expr = case(
                    (game_count == 0, None),
                    else_=(dreb_sum / game_count)
                ).label('dreb_pct')
        derived_metric_exprs.append(expr)
        derived_metric_map['dreb_pct'] = expr

    if 'stl_pct' in derived_metrics:
        # Steal Percentage: steals per game
        stl_sum = metric_component_sum('stl')
        game_count = agg_label_map.get('game_id_count')
        if stl_sum is None or game_count is None:
            return {
                "status": "failed",
                "message": "stl_pct calculation requires stl and game_id count."
            }
        expr = case(
            (game_count == 0, None),
            else_=(stl_sum / game_count)
        ).label('stl_pct')
        derived_metric_exprs.append(expr)
        derived_metric_map['stl_pct'] = expr

    if 'blk_pct' in derived_metrics:
        # Block Percentage: blocks per game
        blk_sum = metric_component_sum('blk')
        game_count = agg_label_map.get('game_id_count')
        if blk_sum is None or game_count is None:
            return {
                "status": "failed",
                "message": "blk_pct calculation requires blk and game_id count."
            }
        expr = case(
            (game_count == 0, None),
            else_=(blk_sum / game_count)
        ).label('blk_pct')
        derived_metric_exprs.append(expr)
        derived_metric_map['blk_pct'] = expr

    if 'game_score' in derived_metrics:
        # Game Score: PTS + 0.4*FGM - 0.7*FGA - 0.4*(FTA-FTM) + 0.7*OREB + 0.3*DREB + STL + 0.7*AST + 0.7*BLK - 0.4*PF - TOV
        # Return average per game
        if scope_name != 'player_game_stats':
            return {
                "status": "failed",
                "message": "game_score is only supported for player_game_stats scope."
            }
        pts_sum = metric_component_sum('pts')
        fgm_sum = metric_component_sum('fgm')
        fga_sum = metric_component_sum('fga')
        ftm_sum = metric_component_sum('ftm')
        fta_sum = metric_component_sum('fta')
        oreb_sum = metric_component_sum('oreb')
        dreb_sum = metric_component_sum('dreb')
        stl_sum = metric_component_sum('stl')
        ast_sum = metric_component_sum('ast')
        blk_sum = metric_component_sum('blk')
        fouls_sum = metric_component_sum('fouls')
        tov_sum = metric_component_sum('tov')
        game_count = agg_label_map.get('game_id_count')
        
        if any(x is None for x in [pts_sum, fgm_sum, fga_sum, ftm_sum, fta_sum, oreb_sum, dreb_sum, stl_sum, ast_sum, blk_sum, fouls_sum, tov_sum, game_count]):
            return {
                "status": "failed",
                "message": "game_score calculation requires all basic stats and game_id count."
            }
        
        total_game_score = (
            pts_sum + 0.4 * fgm_sum - 0.7 * fga_sum - 0.4 * (fta_sum - ftm_sum) +
            0.7 * oreb_sum + 0.3 * dreb_sum + stl_sum + 0.7 * ast_sum + 0.7 * blk_sum -
            0.4 * fouls_sum - tov_sum
        )
        game_score_expr = case(
            (game_count == 0, None),
            else_=(total_game_score / game_count)
        ).label('game_score')
        derived_metric_exprs.append(game_score_expr)
        derived_metric_map['game_score'] = game_score_expr

    if 'ast_to_ratio' in derived_metrics:
        # Assist to Turnover Ratio: AST / TOV
        # Higher is better - measures ball security and playmaking
        if scope_name != 'player_game_stats':
            return {
                "status": "failed",
                "message": "ast_to_ratio is only supported for player_game_stats scope."
            }
        ast_sum = metric_component_sum('ast')
        tov_sum = metric_component_sum('tov')
        
        if ast_sum is None or tov_sum is None:
            return {
                "status": "failed",
                "message": "ast_to_ratio calculation requires ast and tov."
            }
        
        expr = safe_pct_expr(ast_sum, tov_sum, 'ast_to_ratio')
        derived_metric_exprs.append(expr)
        derived_metric_map['ast_to_ratio'] = expr

    # -------------------------
    # Betting/Fantasy Metrics (Player only)
    # -------------------------
    if 'pts_reb' in derived_metrics:
        # Points + Rebounds (popular betting prop)
        if scope_name != 'player_game_stats':
            return {
                "status": "failed",
                "message": "pts_reb is only supported for player_game_stats scope."
            }
        pts_sum = metric_component_sum('pts')
        reb_sum = metric_component_sum('reb')
        
        if pts_sum is None or reb_sum is None:
            return {
                "status": "failed",
                "message": "pts_reb calculation requires pts and reb."
            }
        
        expr = (pts_sum + reb_sum).label('pts_reb')
        derived_metric_exprs.append(expr)
        derived_metric_map['pts_reb'] = expr

    if 'pts_ast' in derived_metrics:
        # Points + Assists (popular betting prop)
        if scope_name != 'player_game_stats':
            return {
                "status": "failed",
                "message": "pts_ast is only supported for player_game_stats scope."
            }
        pts_sum = metric_component_sum('pts')
        ast_sum = metric_component_sum('ast')
        
        if pts_sum is None or ast_sum is None:
            return {
                "status": "failed",
                "message": "pts_ast calculation requires pts and ast."
            }
        
        expr = (pts_sum + ast_sum).label('pts_ast')
        derived_metric_exprs.append(expr)
        derived_metric_map['pts_ast'] = expr

    if 'pra' in derived_metrics:
        # Points + Rebounds + Assists (popular betting prop)
        if scope_name != 'player_game_stats':
            return {
                "status": "failed",
                "message": "pra is only supported for player_game_stats scope."
            }
        pts_sum = metric_component_sum('pts')
        reb_sum = metric_component_sum('reb')
        ast_sum = metric_component_sum('ast')
        
        if pts_sum is None or reb_sum is None or ast_sum is None:
            return {
                "status": "failed",
                "message": "pra calculation requires pts, reb, and ast."
            }
        
        expr = (pts_sum + reb_sum + ast_sum).label('pra')
        derived_metric_exprs.append(expr)
        derived_metric_map['pra'] = expr

    if 'reb_ast' in derived_metrics:
        # Rebounds + Assists (betting prop)
        if scope_name != 'player_game_stats':
            return {
                "status": "failed",
                "message": "reb_ast is only supported for player_game_stats scope."
            }
        reb_sum = metric_component_sum('reb')
        ast_sum = metric_component_sum('ast')
        
        if reb_sum is None or ast_sum is None:
            return {
                "status": "failed",
                "message": "reb_ast calculation requires reb and ast."
            }
        
        expr = (reb_sum + ast_sum).label('reb_ast')
        derived_metric_exprs.append(expr)
        derived_metric_map['reb_ast'] = expr

    if 'stl_blk' in derived_metrics:
        # Steals + Blocks (betting prop)
        if scope_name != 'player_game_stats':
            return {
                "status": "failed",
                "message": "stl_blk is only supported for player_game_stats scope."
            }
        stl_sum = metric_component_sum('stl')
        blk_sum = metric_component_sum('blk')
        
        if stl_sum is None or blk_sum is None:
            return {
                "status": "failed",
                "message": "stl_blk calculation requires stl and blk."
            }
        
        expr = (stl_sum + blk_sum).label('stl_blk')
        derived_metric_exprs.append(expr)
        derived_metric_map['stl_blk'] = expr

    if 'fantasy_score' in derived_metrics:
        # Fantasy Score: 1*PTS + 1.2*REB + 1.5*AST + 3*STL + 3*BLK - 1*TOV
        if scope_name != 'player_game_stats':
            return {
                "status": "failed",
                "message": "fantasy_score is only supported for player_game_stats scope."
            }
        pts_sum = metric_component_sum('pts')
        reb_sum = metric_component_sum('reb')
        ast_sum = metric_component_sum('ast')
        stl_sum = metric_component_sum('stl')
        blk_sum = metric_component_sum('blk')
        tov_sum = metric_component_sum('tov')
        
        if any(x is None for x in [pts_sum, reb_sum, ast_sum, stl_sum, blk_sum, tov_sum]):
            return {
                "status": "failed",
                "message": "fantasy_score calculation requires pts, reb, ast, stl, blk, and tov."
            }
        
        fantasy_expr = (
            1.0 * pts_sum + 
            1.2 * reb_sum + 
            1.5 * ast_sum + 
            3.0 * stl_sum + 
            3.0 * blk_sum - 
            1.0 * tov_sum
        ).label('fantasy_score')
        derived_metric_exprs.append(fantasy_expr)
        derived_metric_map['fantasy_score'] = fantasy_expr


    # -------------------------
    # Advanced Team Metrics
    # -------------------------
    if 'pace' in derived_metrics:
        # Pace: Estimate possessions per game (48 minutes)
        # Formula: Total Possessions / Total Games
        # Where possessions = 0.5 * (Team_Poss + Opp_Poss)
        if scope_name != 'team_game_stats':
            return {
                "status": "failed",
                "message": "pace is only supported for team_game_stats scope."
            }
        fga_sum = metric_component_sum('fga')
        fta_sum = metric_component_sum('fta')
        oreb_sum = metric_component_sum('oreb')
        tov_sum = metric_component_sum('tov')
        
        # Get game count from aggregations (it should be a count aggregation)
        game_count = agg_label_map.get('game_id_count')
        
        if any(x is None for x in [fga_sum, fta_sum, oreb_sum, tov_sum]):
            return {
                "status": "failed",
                "message": "pace calculation requires fga, fta, oreb, and tov."
            }
        
        if game_count is None:
            return {
                "status": "failed",
                "message": "pace calculation requires game_id count in aggregations."
            }
        
        team_poss = fga_sum + 0.44 * fta_sum - oreb_sum + tov_sum
        
        if opponent_stat_cols is not None:
            opp_fga_sum = func.sum(cast(opponent_stat_cols.fga, Float))
            opp_fta_sum = func.sum(cast(opponent_stat_cols.fta, Float))
            opp_oreb_sum = func.sum(cast(opponent_stat_cols.oreb, Float))
            opp_tov_sum = func.sum(cast(opponent_stat_cols.tov, Float))
            opp_poss = opp_fga_sum + 0.44 * opp_fta_sum - opp_oreb_sum + opp_tov_sum
            total_poss = 0.5 * (team_poss + opp_poss)
        else:
            total_poss = team_poss
        
        # Pace = Total Possessions / Number of Games
        # This gives possessions per 48-minute game
        pace_expr = case(
            (game_count == 0, None),
            else_=(total_poss / game_count)
        ).label('pace')
        derived_metric_exprs.append(pace_expr)
        derived_metric_map['pace'] = pace_expr

    if 'off_rating' in derived_metrics:
        # Offensive Rating: 100 * (Points / Possessions)
        # Only supported for team stats
        if scope_name != 'team_game_stats':
            return {
                "status": "failed",
                "message": "off_rating is only supported for team_game_stats scope."
            }
        pf_sum = metric_component_sum('pf')
        fga_sum = metric_component_sum('fga')
        fta_sum = metric_component_sum('fta')
        oreb_sum = metric_component_sum('oreb')
        tov_sum = metric_component_sum('tov')
        
        if any(x is None for x in [pf_sum, fga_sum, fta_sum, oreb_sum, tov_sum]):
            return {
                "status": "failed",
                "message": "off_rating calculation requires pf, fga, fta, oreb, and tov."
            }
        
        possessions = fga_sum + 0.44 * fta_sum - oreb_sum + tov_sum
        expr = safe_pct_expr(100.0 * pf_sum, possessions, 'off_rating')
        derived_metric_exprs.append(expr)
        derived_metric_map['off_rating'] = expr

    if 'def_rating' in derived_metrics:
        # Defensive Rating: 100 * (Points_Allowed / Possessions)
        # Only supported for team stats
        if scope_name != 'team_game_stats':
            return {
                "status": "failed",
                "message": "def_rating is only supported for team_game_stats scope."
            }
        pa_sum = metric_component_sum('pa')
        fga_sum = metric_component_sum('fga')
        fta_sum = metric_component_sum('fta')
        oreb_sum = metric_component_sum('oreb')
        tov_sum = metric_component_sum('tov')
        
        if any(x is None for x in [pa_sum, fga_sum, fta_sum, oreb_sum, tov_sum]):
            return {
                "status": "failed",
                "message": "def_rating calculation requires pa, fga, fta, oreb, and tov."
            }
        
        possessions = fga_sum + 0.44 * fta_sum - oreb_sum + tov_sum
        expr = safe_pct_expr(100.0 * pa_sum, possessions, 'def_rating')
        derived_metric_exprs.append(expr)
        derived_metric_map['def_rating'] = expr

    if 'net_rating' in derived_metrics:
        # Net Rating: Offensive Rating - Defensive Rating
        # Only supported for team stats where we have both pf and pa
        if scope_name != 'team_game_stats':
            return {
                "status": "failed",
                "message": "net_rating is only supported for team_game_stats scope."
            }
        pf_sum = metric_component_sum('pf')
        pa_sum = metric_component_sum('pa')
        fga_sum = metric_component_sum('fga')
        fta_sum = metric_component_sum('fta')
        oreb_sum = metric_component_sum('oreb')
        tov_sum = metric_component_sum('tov')
        
        if any(x is None for x in [pf_sum, pa_sum, fga_sum, fta_sum, oreb_sum, tov_sum]):
            return {
                "status": "failed",
                "message": "net_rating calculation requires pf, pa, fga, fta, oreb, and tov."
            }
        
        possessions = fga_sum + 0.44 * fta_sum - oreb_sum + tov_sum
        off_rating = safe_pct_expr(100.0 * pf_sum, possessions, 'off_rating_temp')
        def_rating = safe_pct_expr(100.0 * pa_sum, possessions, 'def_rating_temp')
        net_rating_expr = (off_rating - def_rating).label('net_rating')
        derived_metric_exprs.append(net_rating_expr)
        derived_metric_map['net_rating'] = net_rating_expr

    if 'ast_ratio' in derived_metrics:
        # Assist Ratio: 100 * AST / FGM
        if scope_name != 'team_game_stats':
            return {
                "status": "failed",
                "message": "ast_ratio is only supported for team_game_stats scope."
            }
        ast_sum = metric_component_sum('ast')
        fgm_sum = metric_component_sum('fgm')
        
        if ast_sum is None or fgm_sum is None:
            return {
                "status": "failed",
                "message": "ast_ratio calculation requires ast and fgm."
            }
        
        expr = safe_pct_expr(100.0 * ast_sum, fgm_sum, 'ast_ratio')
        derived_metric_exprs.append(expr)
        derived_metric_map['ast_ratio'] = expr

    if 'oreb_pct_team' in derived_metrics:
        # Team Offensive Rebound Percentage: 100 * OREB / (OREB + Opp_DREB)
        if scope_name != 'team_game_stats':
            return {
                "status": "failed",
                "message": "oreb_pct_team is only supported for team_game_stats scope."
            }
        oreb_sum = metric_component_sum('oreb')
        game_count = agg_label_map.get('game_id_count')
        if oreb_sum is None or game_count is None:
            return {
                "status": "failed",
                "message": "oreb_pct_team calculation requires oreb and game_id count."
            }
        
        if opponent_stat_cols is not None:
            opp_dreb_sum = func.sum(cast(opponent_stat_cols.dreb, Float))
            oreb_denom = oreb_sum + opp_dreb_sum
            expr = safe_pct_expr(100.0 * oreb_sum, oreb_denom, 'oreb_pct_team')
        else:
            # Without opponent data, return per-game average
            expr = case(
                (game_count == 0, None),
                else_=(oreb_sum / game_count)
            ).label('oreb_pct_team')
        
        derived_metric_exprs.append(expr)
        derived_metric_map['oreb_pct_team'] = expr

    if 'dreb_pct_team' in derived_metrics:
        # Team Defensive Rebound Percentage: 100 * DREB / (DREB + Opp_OREB)
        if scope_name != 'team_game_stats':
            return {
                "status": "failed",
                "message": "dreb_pct_team is only supported for team_game_stats scope."
            }
        dreb_sum = metric_component_sum('dreb')
        game_count = agg_label_map.get('game_id_count')
        if dreb_sum is None or game_count is None:
            return {
                "status": "failed",
                "message": "dreb_pct_team calculation requires dreb and game_id count."
            }
        
        if opponent_stat_cols is not None:
            opp_oreb_sum = func.sum(cast(opponent_stat_cols.oreb, Float))
            dreb_denom = dreb_sum + opp_oreb_sum
            expr = safe_pct_expr(100.0 * dreb_sum, dreb_denom, 'dreb_pct_team')
        else:
            # Without opponent data, return per-game average
            expr = case(
                (game_count == 0, None),
                else_=(dreb_sum / game_count)
            ).label('dreb_pct_team')
        
        derived_metric_exprs.append(expr)
        derived_metric_map['dreb_pct_team'] = expr

    if 'tov_pct_team' in derived_metrics:
        # Team Turnover Percentage: 100 * TOV / (FGA + 0.44*FTA + TOV)
        if scope_name != 'team_game_stats':
            return {
                "status": "failed",
                "message": "tov_pct_team is only supported for team_game_stats scope."
            }
        tov_sum = metric_component_sum('tov')
        fga_sum = metric_component_sum('fga')
        fta_sum = metric_component_sum('fta')
        
        if any(x is None for x in [tov_sum, fga_sum, fta_sum]):
            return {
                "status": "failed",
                "message": "tov_pct_team calculation requires tov, fga, and fta."
            }
        
        tov_denom = fga_sum + 0.44 * fta_sum + tov_sum
        expr = safe_pct_expr(100.0 * tov_sum, tov_denom, 'tov_pct_team')
        derived_metric_exprs.append(expr)
        derived_metric_map['tov_pct_team'] = expr

    # -------------------------
    # STEP 7: output shape
    # -------------------------
    if has_group_by:
        select_cols = []
        group_by_exprs = []

        for group_field in group_by:
            base_group_col = getattr(subject_cols, group_field)
            select_cols.append(base_group_col.label(group_field))
            group_by_exprs.append(base_group_col)

            if group_field == 'player_id':
                select_cols.append(Player.full_name.label('player_name'))
                group_by_exprs.append(Player.full_name)

            elif group_field == 'team_id':
                select_cols.append(TeamMetaSelf.abbreviation.label('team_abbreviation'))
                select_cols.append(TeamMetaSelf.full_name.label('team_name'))
                group_by_exprs.extend([TeamMetaSelf.abbreviation, TeamMetaSelf.full_name])

            elif group_field == 'opponent_team_id':
                select_cols.append(TeamMetaOpp.abbreviation.label('opponent_team_abbreviation'))
                select_cols.append(TeamMetaOpp.full_name.label('opponent_team_name'))
                group_by_exprs.extend([TeamMetaOpp.abbreviation, TeamMetaOpp.full_name])

        query = query.with_entities(
            *select_cols,
            *agg_cols,
            *derived_metric_exprs
        ).group_by(*group_by_exprs)

    elif has_aggs:
        # Only use aggregated derived metrics when there are actual aggregations
        query = query.with_entities(*agg_cols, *derived_metric_exprs)

    else:
        if scope_name == 'team_game_stats' and perspective == 'opponent':
            return {
                "status": "failed",
                "message": "Raw row output with perspective='opponent' is not supported for team_game_stats. Use aggregations and/or group_by."
            }

        if using_subquery:
            raw_cols = [subject_cols[c.name].label(c.name) for c in base_scope.__table__.columns]
            raw_cols.append(subject_cols.game_date.label("game_date"))
        else:
            raw_cols = [getattr(base_scope, c.name).label(c.name) for c in base_scope.__table__.columns]
            raw_cols.append(Game.game_date.label("game_date"))

        label_cols = [
            TeamMetaSelf.abbreviation.label('team_abbreviation'),
            TeamMetaSelf.full_name.label('team_name'),
            TeamMetaOpp.abbreviation.label('opponent_team_abbreviation'),
            TeamMetaOpp.full_name.label('opponent_team_name'),
        ]

        if scope_name == 'player_game_stats':
            label_cols = [Player.full_name.label('player_name')] + label_cols

        # Add derived metrics for raw rows (betting/fantasy metrics on individual games)
        raw_derived_exprs = []
        if has_derived and scope_name == 'player_game_stats':
            # For raw rows, use column values directly instead of aggregations
            col_ref = subject_cols if using_subquery else base_scope
            
            if 'pts_reb' in derived_metrics:
                raw_derived_exprs.append((col_ref.pts + col_ref.reb).label('pts_reb'))
            if 'pts_ast' in derived_metrics:
                raw_derived_exprs.append((col_ref.pts + col_ref.ast).label('pts_ast'))
            if 'pra' in derived_metrics:
                raw_derived_exprs.append((col_ref.pts + col_ref.reb + col_ref.ast).label('pra'))
            if 'reb_ast' in derived_metrics:
                raw_derived_exprs.append((col_ref.reb + col_ref.ast).label('reb_ast'))
            if 'stl_blk' in derived_metrics:
                raw_derived_exprs.append((col_ref.stl + col_ref.blk).label('stl_blk'))
            if 'fantasy_score' in derived_metrics:
                fantasy_expr = (
                    1.0 * col_ref.pts +
                    1.2 * col_ref.reb +
                    1.5 * col_ref.ast +
                    3.0 * col_ref.stl +
                    3.0 * col_ref.blk -
                    1.0 * col_ref.tov
                ).label('fantasy_score')
                raw_derived_exprs.append(fantasy_expr)

        query = query.with_entities(*raw_cols, *label_cols, *raw_derived_exprs)

    # -------------------------
    # STEP 8: sortable columns
    # -------------------------
    sortable_columns = {
        "game_date": game_date_col,
        "minutes": getattr(stat_cols, "minutes", None),
        "pts": getattr(stat_cols, "pts", None),
        "reb": getattr(stat_cols, "reb", None),
        "ast": getattr(stat_cols, "ast", None),
        "stl": getattr(stat_cols, "stl", None),
        "blk": getattr(stat_cols, "blk", None),
        "tov": getattr(stat_cols, "tov", None),
        "fouls": getattr(stat_cols, "fouls", None),
        "fgm": getattr(stat_cols, "fgm", None),
        "fga": getattr(stat_cols, "fga", None),
        "fg3m": getattr(stat_cols, "fg3m", None),
        "fg3a": getattr(stat_cols, "fg3a", None),
        "ftm": getattr(stat_cols, "ftm", None),
        "fta": getattr(stat_cols, "fta", None),
        "oreb": getattr(stat_cols, "oreb", None),
        "dreb": getattr(stat_cols, "dreb", None),
        "pf": getattr(stat_cols, "pf", None),
        "pa": getattr(stat_cols, "pa", None),
        "plus_minus": getattr(stat_cols, "plus_minus", None),
        "player_id": getattr(subject_cols, "player_id", None),
        "team_id": getattr(subject_cols, "team_id", None),
        "opponent_team_id": getattr(subject_cols, "opponent_team_id", None),
    }

    sortable_columns.update(agg_label_map)
    
    # For raw rows with derived metrics, use the raw expressions instead of aggregated ones
    if not has_aggs and has_derived and scope_name == 'player_game_stats':
        col_ref = subject_cols if using_subquery else base_scope
        raw_derived_sort_map = {}
        if 'pts_reb' in derived_metrics:
            raw_derived_sort_map['pts_reb'] = col_ref.pts + col_ref.reb
        if 'pts_ast' in derived_metrics:
            raw_derived_sort_map['pts_ast'] = col_ref.pts + col_ref.ast
        if 'pra' in derived_metrics:
            raw_derived_sort_map['pra'] = col_ref.pts + col_ref.reb + col_ref.ast
        if 'reb_ast' in derived_metrics:
            raw_derived_sort_map['reb_ast'] = col_ref.reb + col_ref.ast
        if 'stl_blk' in derived_metrics:
            raw_derived_sort_map['stl_blk'] = col_ref.stl + col_ref.blk
        if 'fantasy_score' in derived_metrics:
            raw_derived_sort_map['fantasy_score'] = (
                1.0 * col_ref.pts +
                1.2 * col_ref.reb +
                1.5 * col_ref.ast +
                3.0 * col_ref.stl +
                3.0 * col_ref.blk -
                1.0 * col_ref.tov
            )
        sortable_columns.update(raw_derived_sort_map)
    else:
        sortable_columns.update(derived_metric_map)

    # -------------------------
    # STEP 9: sort
    # -------------------------
    sort_spec = query_spec.get('sort')
    if sort_spec:
        sort_field = sort_spec['by']
        sort_dir = sort_spec['direction']

        sort_col = sortable_columns.get(sort_field)
        if sort_col is None:
            return {
                "status": "failed",
                "message": f"Invalid sort field '{sort_field}'."
            }

        if sort_dir == 'desc':
            query = query.order_by(sort_col.desc())
        else:
            query = query.order_by(sort_col.asc())

    # -------------------------
    # STEP 10: limit
    # -------------------------
    if query_spec.get('limit') is not None:
        query = query.limit(query_spec['limit'])

    # -------------------------
    # STEP 11: rows -> dicts
    # -------------------------
    rows = query.all()
    out_rows = [dict(row._mapping) for row in rows]

    return {
        "status": "success",
        "rows": out_rows
    }

if __name__ == '__main__':
    with open('app/query/test_cases_out.txt', 'w') as f:
        pass

    with open('app/query/test_cases.json', 'r') as f:
        data = json.load(f)

    session = SessionLocal()

    for i, tcase in enumerate(data, 1):
        with open('app/query/test_cases_out.txt', 'a') as f:
            f.write(tcase['name'] + '\n')
            pprint.pprint(run_query_spec(session=session, query_spec=tcase['query_spec']), stream=f)
            f.write('\n---------------------------------------------------\n\n')


    print('Test Case Results saved to app/query/test_cases.json')