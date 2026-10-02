"""
SmartCrop AI: Database Layer & Farmer Profile Persistence
Uses SQLite + SQLAlchemy to manage farmer authentication and annual farm profiles.
"""

from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from passlib.context import CryptContext
import jwt

BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = f"sqlite:///{BASE_DIR / 'smartcrop.db'}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "SMARTCROP_PRODUCTION_SECRET_KEY_CHANGE_IN_ENV"
ALGORITHM = "HS256"


# ------------------------------------------------
# Database Tables
# ------------------------------------------------

class Farmer(Base):
    __tablename__ = "farmers"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    phone_number = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    state = Column(String, default="Maharashtra")
    district = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    profiles = relationship("AnnualFarmProfile", back_populates="owner", cascade="all, delete-orphan")


class AnnualFarmProfile(Base):
    __tablename__ = "annual_farm_profiles"

    id = Column(Integer, primary_key=True, index=True)
    farmer_id = Column(Integer, ForeignKey("farmers.id"), nullable=False)
    year = Column(Integer, nullable=False)

    # Farm parameters
    acres = Column(Float, nullable=False)
    budget = Column(Float, nullable=False)
    irrigation_source = Column(String, nullable=False)

    # Soil Chemistry
    n = Column(Float, nullable=False)
    p = Column(Float, nullable=False)
    k = Column(Float, nullable=False)
    ph = Column(Float, nullable=False)

    # Weather/Climate
    temperature = Column(Float, nullable=False)
    humidity = Column(Float, nullable=False)
    rainfall = Column(Float, nullable=False)

    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    owner = relationship("Farmer", back_populates="profiles")
    __table_args__ = (UniqueConstraint("farmer_id", "year", name="uq_farmer_year"),)


Base.metadata.create_all(bind=engine)


# ------------------------------------------------
# Helpers
# ------------------------------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None