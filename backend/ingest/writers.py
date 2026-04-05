from sqlalchemy.dialects.postgresql import insert
from app.models import PlayerGameStats, Team, Game, Player, TeamGameStats


def upsert_dict(session, model, data, conflict_cols):
    stmt = insert(model).values(**data)

    update_dict = {
        col: getattr(stmt.excluded, col)
        for col in data.keys()
        if col not in conflict_cols + ['id']
    }

    stmt = stmt.on_conflict_do_update(
        index_elements=conflict_cols,
        set_=update_dict
    )

    session.execute(stmt)

def bulk_upsert(session, model, rows, conflict_cols):
    stmt = insert(model).values(rows)

    update_cols = {
        col.name: getattr(stmt.excluded, col.name)
        for col in model.__table__.columns
        if col.name not in conflict_cols + ['id']
    }

    stmt = stmt.on_conflict_do_update(
        index_elements=conflict_cols,
        set_=update_cols
    )

    session.execute(stmt)

def upsert_player(session, player_dict):
    upsert_dict(
        session, 
        Player, 
        player_dict, 
        ['player_id']
    )


def upsert_game(session, game_dict):
    upsert_dict(
        session, 
        Game, 
        game_dict, 
        ['game_id']
    )
    
def upsert_team(session, team_dict):
    upsert_dict(
        session, 
        Team, 
        team_dict, 
        ['team_id']
    )
    
def insert_player_game_stats(session, rows):
    bulk_upsert(
        session, 
        PlayerGameStats, 
        rows, 
        ['game_id', 'player_id']
    )

def insert_team_game_stats(session, rows):
    bulk_upsert(
        session, 
        TeamGameStats, 
        rows, 
        ['game_id', 'team_id']
    )
    
    

