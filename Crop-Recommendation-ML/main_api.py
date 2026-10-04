"""SmartCrop API: farmer accounts, crop recommendations and farm services."""

from datetime import datetime, timezone
import os
from pathlib import Path
import re
import uuid
from typing import Optional
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

from database import (
    AnnualFarmProfile, CommunityPost, Farmer, FarmDocument, PastCropHistory, ProduceListing,
    create_access_token, decode_access_token,
    get_db, hash_password, verify_password,
)
from decision_engine import evaluate_crop_plan
from external_services import (
    analyze_crop_photo, ask_smartcrop, fetch_market_comparison,
    fetch_crop_image, fetch_live_mandi_rates, fetch_live_weather, fetch_weather_by_coordinates,
    search_locations,
)

app = FastAPI(
    title="SmartCrop AI Platform API",
    description="Farmer accounts, field profiles, crop decision support, weather and mandi benchmarks.",
    version="2.2.0",
)
UPLOAD_DIR = Path(__file__).with_name("uploads")
MAX_SOIL_REPORT_BYTES = 10 * 1024 * 1024
MAX_FARM_PHOTO_BYTES = 8 * 1024 * 1024
ALLOWED_UPLOAD_TYPES = {
    "application/pdf": (".pdf", b"%PDF-"),
    "image/jpeg": (".jpg", b"\xff\xd8\xff"),
    "image/png": (".png", b"\x89PNG\r\n\x1a\n"),
    "image/webp": (".webp", b"RIFF"),
}
allowed_origins = [origin.strip() for origin in os.getenv("SMARTCROP_ALLOWED_ORIGINS", "").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
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
    budget: float = Field(default=50000.0, ge=20000)
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
    budget: float = Field(..., ge=20000)
    irrigation_source: str = Field(..., min_length=2, max_length=80)
    location: str = Field(..., min_length=2, max_length=160)
    soil_type: str = Field(default="Unknown", min_length=2, max_length=80)
    seasonal_rainfall_mm: Optional[float] = Field(default=None, ge=0, le=2000)


class CropHistoryPayload(BaseModel):
    crop: str = Field(..., min_length=2, max_length=80)
    year: int = Field(..., ge=1950, le=2200)
    season: str = Field(..., min_length=2, max_length=40)
    area_acres: float = Field(..., gt=0, le=100000)
    yield_quintals: float = Field(..., ge=0, le=10000000)
    notes: str = Field(default="", max_length=500)


class CommunityPostPayload(BaseModel):
    message: str = Field(..., min_length=4, max_length=600)


class ProduceListingPayload(BaseModel):
    crop: str = Field(..., min_length=2, max_length=80)
    quantity_quintals: float = Field(..., gt=0, le=10000000)
    asking_price_per_quintal: float = Field(..., gt=0)
    location: str = Field(..., min_length=2, max_length=160)
    notes: str = Field(default="", max_length=600)
    share_phone: bool = False


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
        "soil_type": profile.soil_type,
        "N": profile.n, "P": profile.p, "K": profile.k, "ph": profile.ph,
        "temperature": profile.temperature, "humidity": profile.humidity,
        "rainfall": profile.rainfall, "seasonal_rainfall_mm": profile.seasonal_rainfall_mm,
    }


def document_public(document: FarmDocument) -> dict:
    return {
        "id": document.id,
        "year": document.year,
        "kind": document.kind,
        "name": document.original_name,
        "media_type": document.media_type,
        "size_bytes": document.file_size,
        "created_at": document.created_at.isoformat(),
        "download_url": f"/api/v1/farmer/documents/{document.id}/file",
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
    for key in ("acres", "budget", "irrigation_source", "N", "P", "K", "ph", "temperature", "humidity", "rainfall", "seasonal_rainfall_mm", "location", "soil_type"):
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
    farm = {key: getattr(payload, key) for key in ("acres", "budget", "irrigation_source", "location", "soil_type")}
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


@app.post("/api/v1/farmer/profile/documents")
async def upload_farm_documents(
    year: int = Form(..., ge=2000, le=2200),
    soil_report: Optional[UploadFile] = File(default=None),
    farm_photos: list[UploadFile] = File(default=[]),
    farmer: Farmer = Depends(get_current_farmer),
    db: Session = Depends(get_db),
):
    """Save private soil reports and field photos against an existing yearly farm profile."""
    if len(farm_photos) > 5:
        raise HTTPException(status_code=413, detail="Choose up to five farm photos at a time.")
    profile = db.query(AnnualFarmProfile).filter(
        AnnualFarmProfile.farmer_id == farmer.id, AnnualFarmProfile.year == year,
    ).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Save your farm details before uploading documents.")
    pending = []
    if soil_report and soil_report.filename:
        pending.append((soil_report, "soil_report", MAX_SOIL_REPORT_BYTES))
    pending.extend((photo, "farm_photo", MAX_FARM_PHOTO_BYTES) for photo in farm_photos if photo.filename)
    if not pending:
        raise HTTPException(status_code=400, detail="Choose a soil report or at least one farm photo to upload.")

    farmer_dir = UPLOAD_DIR / str(farmer.id)
    farmer_dir.mkdir(parents=True, exist_ok=True)
    created_files = []
    created_records = []
    try:
        for upload, kind, max_bytes in pending:
            details = ALLOWED_UPLOAD_TYPES.get(upload.content_type or "")
            if details is None:
                raise HTTPException(status_code=415, detail="Use a PDF, JPG, PNG, or WEBP soil report/photo.")
            extension, signature = details
            prefix = await upload.read(16)
            await upload.seek(0)
            valid_signature = prefix.startswith(signature)
            if upload.content_type == "image/webp":
                valid_signature = valid_signature and prefix[8:12] == b"WEBP"
            if not valid_signature:
                raise HTTPException(status_code=415, detail="One of the selected files does not match its file type.")

            stored_name = f"{uuid.uuid4().hex}{extension}"
            destination = farmer_dir / stored_name
            created_files.append(destination)
            size = 0
            with destination.open("wb") as output:
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > max_bytes:
                        raise HTTPException(
                            status_code=413,
                            detail=f"{kind.replace('_', ' ').title()} files must be under {max_bytes // (1024 * 1024)} MB.",
                        )
                    output.write(chunk)
            if size == 0:
                destination.unlink(missing_ok=True)
                raise HTTPException(status_code=400, detail="Empty files cannot be uploaded.")
            safe_name = Path(upload.filename or f"{kind}{extension}").name[:180]
            created_records.append(FarmDocument(
                farmer_id=farmer.id, year=year, kind=kind, original_name=safe_name,
                media_type=upload.content_type, stored_name=stored_name, file_size=size,
            ))
        db.add_all(created_records)
        db.commit()
        for record in created_records:
            db.refresh(record)
        return {"success": True, "documents": [document_public(record) for record in created_records]}
    except Exception:
        db.rollback()
        for path in created_files:
            path.unlink(missing_ok=True)
        raise
    finally:
        if soil_report:
            await soil_report.close()
        for photo in farm_photos:
            await photo.close()


@app.get("/api/v1/farmer/profile/documents")
def list_farm_documents(
    year: int = Query(..., ge=2000, le=2200),
    farmer: Farmer = Depends(get_current_farmer),
    db: Session = Depends(get_db),
):
    documents = db.query(FarmDocument).filter(
        FarmDocument.farmer_id == farmer.id, FarmDocument.year == year,
    ).order_by(FarmDocument.created_at.desc()).all()
    return {"documents": [document_public(document) for document in documents]}


@app.get("/api/v1/farmer/documents/{document_id}/file")
def download_farm_document(
    document_id: int,
    farmer: Farmer = Depends(get_current_farmer),
    db: Session = Depends(get_db),
):
    document = db.query(FarmDocument).filter(
        FarmDocument.id == document_id, FarmDocument.farmer_id == farmer.id,
    ).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Farm document was not found.")
    path = UPLOAD_DIR / str(farmer.id) / document.stored_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="This file is no longer available on the server.")
    return FileResponse(path, media_type=document.media_type, filename=document.original_name)


@app.get("/api/v1/farmer/history")
def get_crop_history(farmer: Farmer = Depends(get_current_farmer), db: Session = Depends(get_db)):
    records = db.query(PastCropHistory).filter(PastCropHistory.farmer_id == farmer.id).order_by(
        PastCropHistory.year.desc(), PastCropHistory.id.desc(),
    ).limit(100).all()
    return {"history": [{"id": row.id, "crop": row.crop, "year": row.year, "season": row.season,
                         "area_acres": row.area_acres, "yield_quintals": row.yield_quintals,
                         "notes": row.notes} for row in records]}


@app.post("/api/v1/farmer/history")
def add_crop_history(payload: CropHistoryPayload, farmer: Farmer = Depends(get_current_farmer), db: Session = Depends(get_db)):
    record = PastCropHistory(farmer_id=farmer.id, **payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"success": True, "id": record.id}


@app.delete("/api/v1/farmer/history/{record_id}")
def delete_crop_history(record_id: int, farmer: Farmer = Depends(get_current_farmer), db: Session = Depends(get_db)):
    record = db.query(PastCropHistory).filter(
        PastCropHistory.id == record_id, PastCropHistory.farmer_id == farmer.id,
    ).first()
    if record is None:
        raise HTTPException(status_code=404, detail="Crop history entry not found.")
    db.delete(record)
    db.commit()
    return {"success": True}


@app.get("/api/v1/community/posts")
def get_community_posts(_farmer: Farmer = Depends(get_current_farmer), db: Session = Depends(get_db)):
    rows = db.query(CommunityPost, Farmer).join(Farmer, Farmer.id == CommunityPost.farmer_id).order_by(
        CommunityPost.created_at.desc(),
    ).limit(50).all()
    return {"posts": [{"id": post.id, "farmer": farmer.full_name, "district": farmer.district,
                       "state": farmer.state, "message": post.message,
                       "is_owner": post.farmer_id == _farmer.id,
                       "created_at": post.created_at.isoformat()} for post, farmer in rows]}


@app.post("/api/v1/community/posts")
def create_community_post(payload: CommunityPostPayload, farmer: Farmer = Depends(get_current_farmer), db: Session = Depends(get_db)):
    post = CommunityPost(farmer_id=farmer.id, message=payload.message.strip())
    db.add(post)
    db.commit()
    return {"success": True}


@app.delete("/api/v1/community/posts/{post_id}")
def delete_community_post(post_id: int, farmer: Farmer = Depends(get_current_farmer), db: Session = Depends(get_db)):
    post = db.query(CommunityPost).filter(
        CommunityPost.id == post_id, CommunityPost.farmer_id == farmer.id,
    ).first()
    if post is None:
        raise HTTPException(status_code=404, detail="Your community post was not found.")
    db.delete(post)
    db.commit()
    return {"success": True}


@app.get("/api/v1/market/listings")
def get_produce_listings(_farmer: Farmer = Depends(get_current_farmer), db: Session = Depends(get_db)):
    rows = db.query(ProduceListing, Farmer).join(Farmer, Farmer.id == ProduceListing.farmer_id).filter(
        ProduceListing.active == 1,
    ).order_by(ProduceListing.created_at.desc()).limit(100).all()
    return {"listings": [{"id": listing.id, "farmer": owner.full_name, "crop": listing.crop,
                          "quantity_quintals": listing.quantity_quintals,
                          "asking_price_per_quintal": listing.asking_price_per_quintal,
                          "location": listing.location, "notes": listing.notes,
                          "contact_phone": owner.phone_number if listing.share_phone else None,
                          "is_owner": listing.farmer_id == _farmer.id,
                          "created_at": listing.created_at.isoformat()} for listing, owner in rows]}


@app.post("/api/v1/market/listings")
def create_produce_listing(payload: ProduceListingPayload, farmer: Farmer = Depends(get_current_farmer), db: Session = Depends(get_db)):
    values = payload.model_dump()
    values["share_phone"] = int(values["share_phone"])
    listing = ProduceListing(farmer_id=farmer.id, **values)
    db.add(listing)
    db.commit()
    return {"success": True}


@app.delete("/api/v1/market/listings/{listing_id}")
def remove_produce_listing(listing_id: int, farmer: Farmer = Depends(get_current_farmer), db: Session = Depends(get_db)):
    listing = db.query(ProduceListing).filter(
        ProduceListing.id == listing_id, ProduceListing.farmer_id == farmer.id,
    ).first()
    if listing is None:
        raise HTTPException(status_code=404, detail="Your listing was not found.")
    listing.active = 0
    db.commit()
    return {"success": True}


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


@app.get("/api/v1/services/crop-image")
def crop_image(crop: str = Query(..., min_length=2, max_length=80)):
    return fetch_crop_image(crop)


@app.get("/api/v1/services/market-comparison")
def market_comparison(
    crop: str = Query(..., min_length=2, max_length=80),
    state: str = Query(default="Maharashtra", min_length=2, max_length=100),
    farmer: Farmer = Depends(get_current_farmer),
):
    return fetch_market_comparison(crop, state)


@app.post("/api/v1/services/crop-health")
async def crop_health_check(
    image: UploadFile = File(...),
    crop: str = Form(default="", max_length=80),
    stage: str = Form(default="", max_length=80),
    location: str = Form(default="", max_length=160),
    soil_type: str = Form(default="", max_length=80),
    farmer: Farmer = Depends(get_current_farmer),
):
    allowed = {"image/jpeg": b"\xff\xd8\xff", "image/png": b"\x89PNG\r\n\x1a\n", "image/webp": b"RIFF"}
    media_type = image.content_type or ""
    signature = allowed.get(media_type)
    if signature is None:
        raise HTTPException(status_code=415, detail="Upload a JPG, PNG, or WEBP crop photo.")
    content = await image.read(8 * 1024 * 1024 + 1)
    await image.close()
    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Crop photos must be under 8 MB.")
    valid = content.startswith(signature)
    if media_type == "image/webp":
        valid = valid and content[8:12] == b"WEBP"
    if not content or not valid:
        raise HTTPException(status_code=415, detail="The photo data does not match its image type.")
    current_weather = fetch_live_weather(location.strip()) if location.strip() else None
    result = analyze_crop_photo(content, media_type, crop.strip(), stage.strip(), location.strip(), soil_type.strip(), current_weather)
    if result["status"] == "not_configured":
        raise HTTPException(status_code=503, detail=result["message"])
    if result["status"] != "success":
        raise HTTPException(status_code=502, detail=result["message"])
    return result
