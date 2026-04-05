from sqlalchemy import Column, Integer, String, Date, ForeignKey
from app.db import Base

class Game(Base):
    __tablename__ = 'games'

    game_id = Column(String, primary_key=True, index=True)
    game_date = Column(Date, nullable=False, index=True)
    season = Column(String, nullable=False, index=True)
    season_type = Column(String, nullable=True)

    home_team_id = Column(Integer, ForeignKey("teams.team_id"), nullable=False)
    away_team_id = Column(Integer, ForeignKey("teams.team_id"), nullable=False)
    
    # V2: Game outcome fields
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)

    status = Column(String, nullable=True)

