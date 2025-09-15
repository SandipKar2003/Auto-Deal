
from sqlalchemy import Column, Integer, String
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    address = Column(String(200), nullable=False)
    location = Column(String(100), nullable=False)
    password_hash = Column(String(200), nullable=False)
