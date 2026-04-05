from sqlalchemy import Column, Integer, String
from app.db import Base

class Team(Base):
    __tablename__ = "teams"

    team_id = Column(Integer, primary_key=True, index=True)
    abbreviation = Column(String, nullable=False, unique=True)
    full_name = Column(String, nullable=False)
    city = Column(String, nullable=True)