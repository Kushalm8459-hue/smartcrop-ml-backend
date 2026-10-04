"""
SmartCrop AI: Database Layer & Farmer Profile Persistence
Uses SQLite + SQLAlchemy to manage farmer authentication and annual farm profiles.
"""

from pathlib import Path
from datetime import datetime, timezone, timedelta
import bcrypt
import hashlib
import hmac
import os
import secrets
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
import jwt

BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = f"sqlite:///{BASE_DIR / 'smartcrop.db'}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

SECRET_KEY = os.environ.get("SMARTCROP_SECRET_KEY", "smartcrop-local-development-key-change-before-deployment")
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
    location = Column(String, nullable=False, default="Maharashtra, India")

    # Soil Chemistry
    n = Column(Float, nullable=False)
    p = Column(Float, nullable=False)
    k = Column(Float, nullable=False)
    ph = Column(Float, nullable=False)

    # Weather/Climate
    temperature = Column(Float, nullable=False)
    humidity = Column(Float, nullable=False)
    rainfall = Column(Float, nullable=False)
    seasonal_rainfall_mm = Column(Float, nullable=False, default=0)

    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    owner = relationship("Farmer", back_populates="profiles")
    __table_args__ = (UniqueConstraint("farmer_id", "year", name="uq_farmer_year"),)


Base.metadata.create_all(bind=engine)

# Add the location field to databases created by earlier project versions.
with engine.begin() as connection:
    columns = {row["name"] for row in connection.execute(text("PRAGMA table_info(annual_farm_profiles)" )).mappings()}
    if "location" not in columns:
        connection.execute(text("ALTER TABLE annual_farm_profiles ADD COLUMN location VARCHAR NOT NULL DEFAULT 'Maharashtra, India'"))
    if "seasonal_rainfall_mm" not in columns:
        connection.execute(text("ALTER TABLE annual_farm_profiles ADD COLUMN seasonal_rainfall_mm FLOAT NOT NULL DEFAULT 0"))
        connection.execute(text("UPDATE annual_farm_profiles SET seasonal_rainfall_mm = rainfall"))


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
    salt = secrets.token_bytes(16)
    cost, block_size, parallelism = 2**14, 8, 1
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=cost, r=block_size,
        p=parallelism, dklen=32,
    )
    return f"scrypt${cost}${block_size}${parallelism}${salt.hex()}${digest.hex()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if hashed_password.startswith("scrypt$"):
        try:
            _, cost, block_size, parallelism, salt_hex, digest_hex = hashed_password.split("$", 5)
            actual = hashlib.scrypt(
                plain_password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
                n=int(cost), r=int(block_size), p=int(parallelism), dklen=32,
            )
            return hmac.compare_digest(actual.hex(), digest_hex)
        except (ValueError, TypeError):
            return False
    # Existing accounts used Passlib bcrypt. Verify their stored hashes directly
    # so they continue working with current bcrypt releases, including bcrypt 5.
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8")[:72], hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(timezone.utc) + timedelta(days=7)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None
