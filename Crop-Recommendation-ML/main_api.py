"""
SmartCrop AI: Enterprise REST API
Exposes ML Crop Evaluation, Direct Recommendations, Farmer Authentication,
Annual Field Profiles, Live Weather Telemetry, and APMC Mandi Market Benchmarks.
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from decision_engine import evaluate_crop_plan
from database import (
    get_db,
    Farmer,
    AnnualFarmProfile,
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token
)
from external_services import fetch_live_weather, fetch_live_mandi_rates, fetch_weather_by_coordinates


app = FastAPI(
    title="SmartCrop AI Platform API",
    description="Farmer Authentication, Yearly Field Profiles, Live Weather/Mandi Services, and ML Decision Engine",
    version="2.1.0"
)

# Enable CORS for frontend clients, local testing, and production deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------
# Pydantic Schemas
# ------------------------------------------------

class SoilClimateData(BaseModel):
    N: float = Field(..., ge=0, le=300)
    P: float = Field(..., ge=0, le=300)
    K: float = Field(..., ge=0, le=300)
    temperature: float = Field(..., ge=-10, le=60)
    humidity: float = Field(..., ge=0, le=100)
    ph: float = Field(..., ge=0, le=14)
    rainfall: float = Field(..., ge=0, le=2000)


class FarmProfileData(BaseModel):
    acres: float = Field(default=1.0, gt=0)
    budget: float = Field(default=50000.0, gt=0)
    irrigation_source: str = Field(default="Canal")
    location: str = Field(default="Maharashtra, India")


class DirectRecommendationRequest(BaseModel):
    soil_climate: SoilClimateData
    farm_profile: FarmProfileData


class SignupRequest(BaseModel):
    full_name: str
    phone_number: str
    password: str
    district: str
    state: str = "Maharashtra"


class LoginRequest(BaseModel):
    phone_number: str
    password: str


class AnnualProfilePayload(BaseModel):
    year: int = Field(default_factory=lambda: datetime.now().year)
    acres: float = Field(..., gt=0)
    budget: float = Field(..., gt=0)
    irrigation_source: str
    N: float = Field(..., ge=0)
    P: float = Field(..., ge=0)
    K: float = Field(..., ge=0)
    ph: float = Field(..., ge=0, le=14)
    temperature: float = Field(..., ge=-10, le=60)
    humidity: float = Field(..., ge=0, le=100)
    rainfall: float = Field(..., ge=0)


# ------------------------------------------------
# System Health Route
# ------------------------------------------------

@app.get("/")
def health_check():
    return {
        "status": "Online",
        "service": "SmartCrop AI Decision Support Engine",
        "version": "2.1.0"
    }


# ------------------------------------------------
# Direct Recommendation Endpoint
# ------------------------------------------------

@app.post("/api/v1/recommend")
def get_recommendation(payload: DirectRecommendationRequest):
    """
    Direct endpoint called by frontend interfaces for real-time inference.
    """
    try:
        soil_dict = payload.soil_climate.model_dump()
        farm_dict = payload.farm_profile.model_dump()

        recommendations = evaluate_crop_plan(soil_dict, farm_dict)

        return {
            "success": True,
            "farm_summary": farm_dict,
            "recommendation_count": len(recommendations),
            "top_crops": recommendations
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Engine evaluation failure: {str(e)}")


# ------------------------------------------------
# Authentication & Database Routes
# ------------------------------------------------

def get_current_farmer(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)) -> Farmer:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header.")
    token = authorization.split(" ")[1]
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Session expired or invalid token.")
    farmer = db.query(Farmer).filter(Farmer.phone_number == payload["sub"]).first()
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer account does not exist.")
    return farmer


@app.post("/api/v1/auth/signup")
def register_farmer(req: SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(Farmer).filter(Farmer.phone_number == req.phone_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="Phone number is already registered.")

    new_farmer = Farmer(
        full_name=req.full_name,
        phone_number=req.phone_number,
        hashed_password=hash_password(req.password),
        district=req.district,
        state=req.state
    )
    db.add(new_farmer)
    db.commit()
    db.refresh(new_farmer)

    token = create_access_token({"sub": new_farmer.phone_number, "name": new_farmer.full_name})
    return {"success": True, "token": token, "farmer": {"id": new_farmer.id, "name": new_farmer.full_name}}


@app.post("/api/v1/auth/login")
def login_farmer(req: LoginRequest, db: Session = Depends(get_db)):
    farmer = db.query(Farmer).filter(Farmer.phone_number == req.phone_number).first()
    if not farmer or not verify_password(req.password, farmer.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid phone number or password.")

    token = create_access_token({"sub": farmer.phone_number, "name": farmer.full_name})
    return {"success": True, "token": token, "farmer": {"id": farmer.id, "name": farmer.full_name}}


@app.post("/api/v1/farmer/profile/upsert")
def upsert_yearly_profile(payload: AnnualProfilePayload, farmer: Farmer = Depends(get_current_farmer), db: Session = Depends(get_db)):
    profile = db.query(AnnualFarmProfile).filter(
        AnnualFarmProfile.farmer_id == farmer.id,
        AnnualFarmProfile.year == payload.year
    ).first()

    if not profile:
        profile = AnnualFarmProfile(farmer_id=farmer.id, year=payload.year)
        db.add(profile)

    profile.acres = payload.acres
    profile.budget = payload.budget
    profile.irrigation_source = payload.irrigation_source
    profile.n = payload.N
    profile.p = payload.P
    profile.k = payload.K
    profile.ph = payload.ph
    profile.temperature = payload.temperature
    profile.humidity = payload.humidity
    profile.rainfall = payload.rainfall
    profile.updated_at = datetime.now(timezone.utc)
    db.commit()

    soil_dict = {
        "N": payload.N,
        "P": payload.P,
        "K": payload.K,
        "temperature": payload.temperature,
        "humidity": payload.humidity,
        "ph": payload.ph,
        "rainfall": payload.rainfall
    }
    farm_dict = {
        "acres": payload.acres,
        "budget": payload.budget,
        "irrigation_source": payload.irrigation_source,
        "location": f"{farmer.district}, {farmer.state}"
    }
    recommendations = evaluate_crop_plan(soil_dict, farm_dict)

    return {"success": True, "year": payload.year, "recommendations": recommendations}


# ------------------------------------------------
# Live External Services (Weather & APMC Mandi API)
# ------------------------------------------------

@app.get("/api/v1/services/weather")
def get_weather(location: str = "Nashik"):
    """
    Fetches real-time temperature, humidity, and rainfall using Open-Meteo geocoding.
    """
    return fetch_live_weather(location)

from external_services import fetch_live_weather, fetch_live_mandi_rates, fetch_weather_by_coordinates

@app.get("/api/v1/services/search-location")
def search_location(query: str):
    """
    Google-like search: Enter any village, town, or district name in India.
    Returns the resolved location and real-time farm climate data.
    """
    return search_and_fetch_farm_weather(query)


@app.get("/api/v1/services/weather")
def get_weather(location: str = "Nashik"):
    """
    Fetches real-time temperature, humidity, and rainfall using Open-Meteo geocoding.
    """
    return fetch_live_weather(location)


@app.get("/api/v1/services/mandi")
def get_mandi_rate(crop: str, state: str = "Maharashtra"):
    """
    Fetches wholesale APMC market price benchmarks (INR per Quintal and per KG) and market trend.
    """
    return fetch_live_mandi_rates(crop, state)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_api:app", host="127.0.0.1", port=8000, reload=True, app_dir="Crop-Recommendation-ML")