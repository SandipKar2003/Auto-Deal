
from sqlalchemy import Column, Integer, String, Float, ForeignKey,Date
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    address = Column(String(200), nullable=False)
    location = Column(String(100), nullable=False)
    password_hash = Column(String(200), nullable=False)


# 1. Rent table
class Rent(Base):
    __tablename__ = "rents"

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    pick_up_date=Column(Date,nullable=False)
    duration = Column(String(50), nullable=False)   # e.g. "6 months"
    car_id = Column(Integer, nullable=False)
    car_name = Column(String(100), nullable=False)
    rent_price_per_month = Column(Float, nullable=False)
    total_rent = Column(Float, nullable=False)


# 2. Buy table
class Buy(Base):
    __tablename__ = "buys"

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    car_id = Column(Integer, nullable=False)
    car_name = Column(String(100), nullable=False)
    price = Column(String(100), nullable=False)

