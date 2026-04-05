from sqlalchemy import Column, Integer, String
from app.db import Base


class Player(Base):
    __tablename__ = "players"

    player_id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)