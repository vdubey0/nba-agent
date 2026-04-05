from sqlalchemy import Column, Integer, String, Float, ForeignKey, UniqueConstraint, Boolean
from app.db import Base


class PlayerGameStats(Base):
    __tablename__ = "player_game_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)

    game_id = Column(String, ForeignKey("games.game_id"), nullable=False, index=True)
    player_id = Column(Integer, ForeignKey("players.player_id"), nullable=False, index=True)
    team_id = Column(Integer, ForeignKey("teams.team_id"), nullable=False, index=True)
    opponent_team_id = Column(Integer, ForeignKey("teams.team_id"), nullable=False)
    
    # V2: Game context fields
    is_win = Column(Boolean, nullable=True, index=True)
    point_differential = Column(Integer, nullable=True)
    is_home = Column(Boolean, nullable=True, index=True)

    minutes = Column(Float, nullable=True)

    pts = Column(Integer, nullable=True)
    reb = Column(Integer, nullable=True)
    ast = Column(Integer, nullable=True)
    stl = Column(Integer, nullable=True)
    blk = Column(Integer, nullable=True)
    tov = Column(Integer, nullable=True)
    fouls = Column(Integer, nullable=True)

    fgm = Column(Integer, nullable=True)
    fga = Column(Integer, nullable=True)
    fg3m = Column(Integer, nullable=True)
    fg3a = Column(Integer, nullable=True)
    ftm = Column(Integer, nullable=True)
    fta = Column(Integer, nullable=True)

    oreb = Column(Integer, nullable=True)
    dreb = Column(Integer, nullable=True)

    plus_minus = Column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("game_id", "player_id", name="uq_player_game"),
    )
