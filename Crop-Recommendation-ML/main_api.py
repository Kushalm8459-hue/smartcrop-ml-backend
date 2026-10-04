"""SmartCrop API: farmer accounts, crop recommendations and farm services."""

from datetime import datetime
import os
from pathlib import Path
from typing import Optional
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

from database import (
    AnnualFarmProfile, Farmer, create_access_token, decode_access_token,
    get_db, hash_password, verify_password,
)
from decision_engine import evaluate_crop_plan
from external_services import (
    ask_smartcrop,
    fetch_live_mandi_rates, fetch_live_weather, fetch_weather_by_coordinates,
    search_locations,
)

app = FastAPI(
    title="SmartCrop AI Platform API",
    description="Farmer accounts, field profiles, crop decision support, weather and mandi benchmarks.",
    version="2.2.0",
)
allowed_origins = [origin.strip() for origin in os.getenv("SMARTCROP_ALLOWED_ORIGINS", "").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


class SoilClimateData(BaseModel):
    N: float = Field(..., ge=0, le=300)
    P: float = Field(..., ge=0, le=300)
    K: float = Field(..., ge=0, le=300)
    temperature: float = Field(..., ge=-10, le=60)
    humidity: float = Field(..., ge=0, le=100)
    ph: float = Field(..., ge=0, le=14)
    rainfall: float = Field(..., ge=0, le=300)


class FarmProfileData(BaseModel):
    acres: float = Field(default=1.0, gt=0, le=100000)
    budget: float = Field(default=50000.0, gt=0)
    irrigation_source: str = Field(default="Canal", min_length=2, max_length=80)
    location: str = Field(default="Maharashtra, India", min_length=2, max_length=160)
    seasonal_rainfall_mm: Optional[float] = Field(default=None, ge=0, le=2000)


class DirectRecommendationRequest(BaseModel):
    soil_climate: SoilClimateData
    farm_profile: FarmProfileData


class SignupRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    phone_number: str = Field(..., min_length=10, max_length=20)
    password: str = Field(..., min_length=8, max_length=128)
    district: str = Field(..., min_length=2, max_length=100)
    state: str = Field(default="Maharashtra", min_length=2, max_length=100)

    @field_validator("phone_number")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        digits = "".join(char for char in value if char.isdigit())
        if not 10 <= len(digits) <= 15:
            raise ValueError("Enter a phone number with 10 to 15 digits.")
        return f"+{digits}" if value.strip().startswith("+") else digits


class LoginRequest(BaseModel):
    phone_number: str = Field(..., min_length=10, max_length=20)
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("phone_number")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        digits = "".join(char for char in value if char.isdigit())
        if not 10 <= len(digits) <= 15:
            raise ValueError("Enter a phone number with 10 to 15 digits.")
        return f"+{digits}" if value.strip().startswith("+") else digits


class FarmerProfileUpdate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    phone_number: str = Field(..., min_length=10, max_length=20)
    district: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)

    @field_validator("phone_number")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        digits = "".join(char for char in value if char.isdigit())
        if not 10 <= len(digits) <= 15:
            raise ValueError("Enter a phone number with 10 to 15 digits.")
        return f"+{digits}" if value.strip().startswith("+") else digits


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=1200)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1200)
    history: list[ChatMessage] = Field(default_factory=list, max_length=12)
    crop_report: Optional[dict] = None


class AnnualProfilePayload(SoilClimateData):
    year: int = Field(default_factory=lambda: datetime.now().year, ge=2000, le=2200)
    acres: float = Field(..., gt=0, le=100000)
    budget: float = Field(..., gt=0)
    irrigation_source: str = Field(..., min_length=2, max_length=80)
    location: str = Field(..., min_length=2, max_length=160)
    seasonal_rainfall_mm: Optional[float] = Field(default=None, ge=0, le=2000)


def farmer_public(farmer: Farmer) -> dict:
    return {
        "id": farmer.id,
        "full_name": farmer.full_name,
        "phone_number": farmer.phone_number,
        "district": farmer.district,
        "state": farmer.state,
    }


def profile_public(profile: AnnualFarmProfile) -> dict:
    return {
        "year": profile.year, "acres": profile.acres, "budget": profile.budget,
        "irrigation_source": profile.irrigation_source, "location": profile.location,
        "N": profile.n, "P": profile.p, "K": profile.k, "ph": profile.ph,
        "temperature": profile.temperature, "humidity": profile.humidity,
        "rainfall": profile.rainfall, "seasonal_rainfall_mm": profile.seasonal_rainfall_mm,
    }


def get_current_farmer(
    authorization: Optional[str] = Header(None), db: Session = Depends(get_db),
) -> Farmer:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Please log in to continue.")
    payload = decode_access_token(authorization.removeprefix("Bearer ").strip())
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Your session has expired. Please log in again.")
    farmer = db.query(Farmer).filter(Farmer.phone_number == payload["sub"]).first()
    if farmer is None:
        raise HTTPException(status_code=401, detail="Farmer account was not found.")
    return farmer


def issue_session(farmer: Farmer) -> dict:
    return {"success": True, "token": create_access_token({"sub": farmer.phone_number}), "farmer": farmer_public(farmer)}


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(Path(__file__).with_name("index.html"))


@app.get("/api/health")
def health_check():
    return {"status": "online", "service": "SmartCrop AI Decision Support Engine", "version": app.version}


@app.post("/api/v1/recommend")
def get_recommendation(payload: DirectRecommendationRequest):
    soil, farm = payload.soil_climate.model_dump(), payload.farm_profile.model_dump()
    try:
        recommendations = evaluate_crop_plan(soil, farm)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"Could not evaluate this farm: {exc}") from exc
    return {
        "success": True, "farm_summary": farm, "recommendation_count": len(recommendations),
        "model_note": "Model scores compare crop classes for the supplied data; they are not calibrated probabilities of yield or crop success.",
        "estimate_note": "Costs, water, yields and sowing windows use the project's reference assumptions. Confirm local agronomy and input prices.",
        "top_crops": recommendations,
    }


@app.post("/api/v1/auth/signup")
def register_farmer(req: SignupRequest, db: Session = Depends(get_db)):
    if db.query(Farmer).filter(Farmer.phone_number == req.phone_number).first():
        raise HTTPException(status_code=409, detail="This phone number is already registered. Please log in.")
    farmer = Farmer(
        full_name=req.full_name.strip(), phone_number=req.phone_number,
        hashed_password=hash_password(req.password), district=req.district.strip(), state=req.state.strip(),
    )
    db.add(farmer)
    db.commit()
    db.refresh(farmer)
    return issue_session(farmer)


@app.post("/api/v1/auth/login")
def login_farmer(req: LoginRequest, db: Session = Depends(get_db)):
    farmer = db.query(Farmer).filter(Farmer.phone_number == req.phone_number).first()
    if not farmer or not verify_password(req.password, farmer.hashed_password):
        raise HTTPException(status_code=401, detail="Phone number or password is incorrect.")
    return issue_session(farmer)


@app.get("/api/v1/farmer/me")
def get_farmer_profile(farmer: Farmer = Depends(get_current_farmer), db: Session = Depends(get_db)):
    profiles = db.query(AnnualFarmProfile).filter(AnnualFarmProfile.farmer_id == farmer.id).order_by(AnnualFarmProfile.year.desc()).all()
    return {"farmer": farmer_public(farmer), "profiles": [profile_public(profile) for profile in profiles]}


@app.patch("/api/v1/farmer/me")
def update_farmer_profile(
    payload: FarmerProfileUpdate,
    farmer: Farmer = Depends(get_current_farmer),
    db: Session = Depends(get_db),
):
    duplicate = db.query(Farmer).filter(
        Farmer.phone_number == payload.phone_number, Farmer.id != farmer.id,
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="That phone number is already linked to another account.")
    farmer.full_name = payload.full_name.strip()
    farmer.phone_number = payload.phone_number
    farmer.district = payload.district.strip()
    farmer.state = payload.state.strip()
    db.commit()
    db.refresh(farmer)
    # Refresh the token's subject when the farmer changes their phone number.
    return issue_session(farmer)


@app.get("/api/v1/chat/status")
def smartcrop_chat_status():
    return {"configured": bool(os.environ.get("OPENAI_API_KEY")), "provider": "OpenAI Responses API"}


@app.post("/api/v1/chat")
def smartcrop_chat(
    payload: ChatRequest,
    farmer: Farmer = Depends(get_current_farmer),
):
    result = ask_smartcrop(payload.message.strip(), payload.history, payload.crop_report)
    if result["status"] == "not_configured":
        raise HTTPException(status_code=503, detail=result["message"])
    if result["status"] != "success":
        raise HTTPException(status_code=502, detail=result["message"])
    return result


@app.post("/api/v1/farmer/profile/upsert")
def upsert_yearly_profile(
    payload: AnnualProfilePayload,
    farmer: Farmer = Depends(get_current_farmer),
    db: Session = Depends(get_db),
):
    profile = db.query(AnnualFarmProfile).filter(
        AnnualFarmProfile.farmer_id == farmer.id, AnnualFarmProfile.year == payload.year,
    ).first()
    if profile is None:
        profile = AnnualFarmProfile(farmer_id=farmer.id, year=payload.year)
        db.add(profile)
    values = payload.model_dump()
    for key in ("acres", "budget", "irrigation_source", "N", "P", "K", "ph", "temperature", "humidity", "rainfall", "seasonal_rainfall_mm", "location"):
        value = values[key]
        if key == "seasonal_rainfall_mm" and value is None:
            value = values["rainfall"]
        setattr(profile, {"N": "n", "P": "p", "K": "k", "seasonal_rainfall_mm": "seasonal_rainfall_mm"}.get(key, key), value)
    db.commit()
    db.refresh(profile)
    return {"success": True, "profile": profile_public(profile)}


@app.post("/api/v1/farmer/recommend")
def recommend_for_farmer(
    payload: AnnualProfilePayload,
    farmer: Farmer = Depends(get_current_farmer),
    db: Session = Depends(get_db),
):
    soil = {key: getattr(payload, key) for key in ("N", "P", "K", "temperature", "humidity", "ph", "rainfall")}
    farm = {key: getattr(payload, key) for key in ("acres", "budget", "irrigation_source", "location")}
    farm["seasonal_rainfall_mm"] = (
        payload.seasonal_rainfall_mm if payload.seasonal_rainfall_mm is not None else payload.rainfall
    )
    try:
        recommendations = evaluate_crop_plan(soil, farm)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"Could not evaluate this farm: {exc}") from exc
    saved = upsert_yearly_profile(payload, farmer, db)
    return {
        "success": True, "profile": saved["profile"], "recommendation_count": len(recommendations),
        "model_note": "Model scores compare crop classes for the supplied data; they are not calibrated probabilities of yield or crop success.",
        "estimate_note": "Costs, water, yields and sowing windows use the project's reference assumptions. Confirm local agronomy and input prices.",
        "top_crops": recommendations,
    }


@app.get("/api/v1/services/search-location")
def search_location(query: str = Query(..., min_length=2, max_length=120)):
    return search_locations(query)


@app.get("/api/v1/services/weather")
def get_weather(location: str = "Nashik", latitude: Optional[float] = None, longitude: Optional[float] = None):
    if (latitude is None) != (longitude is None):
        raise HTTPException(status_code=422, detail="Provide both latitude and longitude.")
    if latitude is not None and longitude is not None:
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise HTTPException(status_code=422, detail="Coordinates are outside the valid range.")
        return fetch_weather_by_coordinates(latitude, longitude)
    return fetch_live_weather(location)


@app.get("/api/v1/services/mandi")
def get_mandi_rate(
    crop: str = Query(..., min_length=2, max_length=80),
    state: str = Query(default="Maharashtra", min_length=2, max_length=100),
):
    return fetch_live_mandi_rates(crop, state)
