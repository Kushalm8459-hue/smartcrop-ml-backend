"""
SmartCrop AI: External API Services
Fetches real-time weather (via Name or GPS Coordinates) and commodity market (Mandi) rates.
"""

from typing import Dict, Any, Optional
from functools import lru_cache
import os
import json
import re
import base64
from datetime import datetime
import urllib.parse
import requests


@lru_cache(maxsize=256)
def fetch_crop_image(crop_name: str) -> Dict[str, Any]:
    """Find a crop photo on Wikimedia Commons and return image-credit details."""
    query = f"{crop_name.strip()} crop plant field"
    try:
        response = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query", "format": "json", "generator": "search",
                "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": 8,
                "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": 900,
            },
            headers={"User-Agent": "SmartCropCollegeProject/1.0 (crop recommendation demo)"},
            timeout=10,
        )
        response.raise_for_status()
        pages = response.json().get("query", {}).get("pages", {})
        for page in sorted(pages.values(), key=lambda item: item.get("index", 999)):
            info = (page.get("imageinfo") or [{}])[0]
            if not info.get("thumburl"):
                continue
            metadata = info.get("extmetadata", {})
            def plain(key: str) -> str:
                raw = metadata.get(key, {}).get("value", "")
                return re.sub(r"<[^>]*>", " ", raw).replace("&nbsp;", " ").strip()[:240]
            return {
                "status": "success", "crop": crop_name,
                "image_url": info["thumburl"],
                "page_url": info.get("descriptionurl", "https://commons.wikimedia.org/"),
                "creator": plain("Artist") or "Wikimedia Commons contributor",
                "license": plain("LicenseShortName") or "See image page",
            }
        return {"status": "not_found", "crop": crop_name}
    except (requests.RequestException, ValueError, TypeError):
        return {"status": "unavailable", "crop": crop_name}


def ask_smartcrop(message: str, history: list, crop_report: Optional[dict] = None) -> Dict[str, Any]:
    """Ask the OpenAI Responses API for a plain-language, report-aware answer."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"status": "not_configured", "message": "Add OPENAI_API_KEY to Crop-Recommendation-ML/.env and restart the server to enable the AI agronomy chat."}

    context = "The user is a farmer using SmartCrop, a crop decision-support prototype. Explain terms in simple language and provide practical next steps. Do not claim a model score guarantees crop success, do not invent live weather, market prices, government rules, or local facts. Make clear when estimates need local confirmation. For pesticide, disease, chemical dosage, or high-stakes financial questions, recommend confirmation with a qualified local agriculture officer. Answer in the language the farmer uses."
    if crop_report:
        context += "\n\nCurrent crop report (project estimates, not guarantees):\n" + json.dumps(crop_report, ensure_ascii=False)[:12000]

    conversation = [{"role": item.role, "content": item.content} for item in history[-10:]]
    conversation.append({"role": "user", "content": message})
    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": os.environ.get("OPENAI_MODEL", "gpt-6-astra"),
                "instructions": context,
                "input": conversation,
                "max_output_tokens": 700,
                "store": False,
            }, timeout=45,
        )
        if response.status_code in (401, 403):
            return {"status": "error", "message": "The OpenAI API key is invalid or does not have access to this model. Check the server configuration."}
        if response.status_code == 429:
            return {"status": "error", "message": "The AI service is rate-limited or out of API credit. Please try again later."}
        response.raise_for_status()
        payload = response.json()
        answer = payload.get("output_text")
        if not answer:
            answer = "\n".join(
                part.get("text", "")
                for item in payload.get("output", []) if item.get("type") == "message"
                for part in item.get("content", []) if part.get("type") == "output_text"
            ).strip()
        if not answer:
            return {"status": "error", "message": "The AI service returned an empty response. Please rephrase your question."}
        return {"status": "success", "answer": answer, "model": os.environ.get("OPENAI_MODEL", "gpt-6-astra")}
    except requests.RequestException:
        return {"status": "error", "message": "Could not connect to the AI service. Check the server's internet connection and try again."}
    except (ValueError, TypeError):
        return {"status": "error", "message": "The AI service returned an unreadable response. Please try again."}


def analyze_crop_photo(image_bytes: bytes, media_type: str, crop: str, stage: str, location: str, soil_type: str = "", weather: Optional[dict] = None) -> Dict[str, Any]:
    """Provide cautious visual triage; this is not a certified disease diagnosis."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"status": "not_configured", "message": "Crop photo guidance needs the server's OPENAI_API_KEY setting."}
    data_url = f"data:{media_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
    instructions = (
        "You are a cautious crop-health triage assistant for Indian smallholder farmers. "
        "Inspect only visible signs and clearly say a photo cannot confirm a diagnosis. "
        "Structure the answer with: visible observations; possible causes (ranked and uncertain); "
        "safe immediate checks/actions; general fertilizer/nutrient considerations for the stated stage; "
        "what to avoid; what additional close-up/photos/details are useful; "
        "when to contact a local Krishi Vigyan Kendra/agriculture officer. "
        "Do not invent fertilizer or pesticide dosage, product brands, or chemical mixes. Recommend integrated pest management, "
        "label-compliant products only after local expert confirmation, and protective equipment. "
        "Do not claim live weather or location knowledge beyond details supplied. Use simple language and the farmer's context."
    )
    weather_context = "No live weather data was available."
    if weather and weather.get("status") == "success":
        weather_context = json.dumps({key: weather.get(key) for key in ("temperature", "humidity", "forecast_rainfall_7_day_mm", "weather_observed_at")}, ensure_ascii=False)
    text = f"Crop: {crop or 'not specified'}. Growth stage: {stage or 'not specified'}. Farm location: {location or 'not specified'}. Reported soil type: {soil_type or 'not specified'}. Current local weather data (not a seasonal forecast): {weather_context}. Please give visual triage and safe next steps."
    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": os.environ.get("OPENAI_MODEL", "gpt-6-astra"),
                "instructions": instructions,
                "input": [{"role": "user", "content": [
                    {"type": "input_text", "text": text},
                    {"type": "input_image", "image_url": data_url, "detail": "high"},
                ]}],
                "max_output_tokens": 800,
                "store": False,
            }, timeout=60,
        )
        if response.status_code in (401, 403):
            return {"status": "error", "message": "The OpenAI key is invalid or cannot use the configured model."}
        if response.status_code == 429:
            return {"status": "error", "message": "The AI image service is rate-limited or out of API credit."}
        response.raise_for_status()
        payload = response.json()
        answer = payload.get("output_text") or "\n".join(
            part.get("text", "") for item in payload.get("output", []) if item.get("type") == "message"
            for part in item.get("content", []) if part.get("type") == "output_text"
        ).strip()
        if not answer:
            return {"status": "error", "message": "The AI returned no guidance for this photo. Try another clear photo."}
        return {"status": "success", "answer": answer, "model": os.environ.get("OPENAI_MODEL", "gpt-6-astra")}
    except requests.RequestException:
        return {"status": "error", "message": "Could not reach the AI image service. Try again when the server is online."}
    except (ValueError, TypeError):
        return {"status": "error", "message": "The AI image service returned an unreadable response."}


def search_locations(query: str) -> Dict[str, Any]:
    """Resolve an Indian place name and attach current weather when available."""
    cleaned = query.strip()
    if len(cleaned) < 2:
        return {"status": "not_found", "message": "Enter at least two characters."}
    try:
        response = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": cleaned, "count": 5, "language": "en", "format": "json", "countryCode": "IN"},
            timeout=8,
        )
        response.raise_for_status()
        results = response.json().get("results", [])
        if not results:
            return {"status": "not_found", "query": cleaned, "results": []}
        places = [{
            "name": item.get("name", cleaned),
            "district": item.get("admin2") or item.get("admin1", ""),
            "state": item.get("admin1", "India"),
            "country": item.get("country", "India"),
            "latitude": item["latitude"],
            "longitude": item["longitude"],
        } for item in results]
        first = places[0]
        weather = fetch_weather_by_coordinates(first["latitude"], first["longitude"])
        return {"status": "success", "query": cleaned, "results": places, "weather": weather}
    except (requests.RequestException, ValueError, KeyError) as exc:
        return {"status": "unavailable", "query": cleaned, "message": "Location search is temporarily unavailable."}


def fetch_live_weather(city_name: str) -> Dict[str, Any]:
    """
    Fetches live temperature, humidity, and rainfall using Open-Meteo geocoding.
    Supports free-text search for any city, town, or district in India.
    """
    cleaned_name = city_name.strip()
    encoded_name = urllib.parse.quote(cleaned_name)

    try:
        # 1. Geocode location name to latitude/longitude restricted to India
        geo_url = (
            f"https://geocoding-api.open-meteo.com/v1/search?"
            f"name={encoded_name}&count=1&language=en&format=json&countryCode=IN"
        )
        geo_response = requests.get(geo_url, timeout=8)
        geo_response.raise_for_status()
        geo_res = geo_response.json()

        results = geo_res.get("results")
        if not results:
            return {"status": "not_found", "city": cleaned_name, "message": "No matching Indian location was found."}
        else:
            lat = results[0]["latitude"]
            lon = results[0]["longitude"]
            resolved_place = f"{results[0].get('name', cleaned_name)}, {results[0].get('admin1', 'India')}"

        # 2. Fetch current weather metrics
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,precipitation"
            f"&daily=precipitation_sum&timezone=auto"
        )
        weather_response = requests.get(weather_url, timeout=8)
        weather_response.raise_for_status()
        weather_res = weather_response.json()
        current = weather_res.get("current", {})

        temp = current.get("temperature_2m", 25.0)
        humidity = current.get("relative_humidity_2m", 70.0)

        forecast_rainfall = weather_res.get("daily", {}).get("precipitation_sum", [])

        return {
            "status": "success",
            "city": resolved_place,
            "latitude": lat,
            "longitude": lon,
            "temperature": round(float(temp), 2),
            "humidity": round(float(humidity), 2),
            "forecast_rainfall_7_day_mm": round(sum(float(value or 0) for value in forecast_rainfall[:7]), 2),
            "weather_source": "Open-Meteo",
            "weather_observed_at": current.get("time"),
        }
    except (requests.RequestException, ValueError, KeyError, TypeError) as e:
        return {
            "status": "fallback",
            "city": cleaned_name,
            "temperature": None,
            "humidity": None,
            "forecast_rainfall_7_day_mm": None,
            "message": "Live weather is temporarily unavailable. Please try again later."
        }


def fetch_weather_by_coordinates(lat: float, lon: float) -> Dict[str, Any]:
    """
    Fetches hyper-local real-time weather and village/district name
    using exact GPS coordinates from a map or device location.
    """
    try:
        # 1. Reverse geocode to get the exact village/taluka/district
        geo_rev_url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
        headers = {"User-Agent": "SmartCropAI-CollegeProject/1.0"}
        rev_response = requests.get(geo_rev_url, headers=headers, timeout=8)
        rev_response.raise_for_status()
        rev_res = rev_response.json()

        address = rev_res.get("address", {})
        village = (
            address.get("village")
            or address.get("suburb")
            or address.get("town")
            or address.get("county", "Local Area")
        )
        district = address.get("state_district") or address.get("city", "District")
        state = address.get("state", "India")
        location_label = f"{village}, {district}, {state}"

        # 2. Fetch live weather metrics for these exact farm coordinates
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,precipitation"
            f"&daily=precipitation_sum&timezone=auto"
        )
        weather_response = requests.get(weather_url, timeout=8)
        weather_response.raise_for_status()
        weather_res = weather_response.json()
        current = weather_res.get("current", {})

        temperature = current.get("temperature_2m", 27.0)
        humidity = current.get("relative_humidity_2m", 65.0)
        forecast_rainfall = weather_res.get("daily", {}).get("precipitation_sum", [])

        return {
            "status": "success",
            "latitude": lat,
            "longitude": lon,
            "location_name": location_label,
            "district": district,
            "state": state,
            "temperature": round(float(temperature), 2),
            "humidity": round(float(humidity), 2),
            "forecast_rainfall_7_day_mm": round(sum(float(value or 0) for value in forecast_rainfall[:7]), 2),
            "weather_source": "Open-Meteo",
            "weather_observed_at": current.get("time"),
        }
    except Exception as exc:
        return {
            "status": "fallback",
            "latitude": lat,
            "longitude": lon,
            "location_name": f"Coordinates ({lat}, {lon})",
            "temperature": None,
            "humidity": None,
            "forecast_rainfall_7_day_mm": None,
            "message": "Live weather is temporarily unavailable. Please try again later."
        }


def fetch_live_mandi_rates(crop_name: str, state: str = "Maharashtra") -> Dict[str, Any]:
    """Fetch today's official AGMARKNET-derived price records through data.gov.in."""
    api_key = os.environ.get("DATA_GOV_IN_API_KEY")
    aliases = {
        "chickpea": "Gram", "kidneybeans": "Kidney Beans", "pigeonpeas": "Arhar (Tur/Red Gram)",
        "mungbean": "Moong (Green Gram)", "blackgram": "Urad", "mothbeans": "Moth",
        "lentil": "Lentil (Masur)", "maize": "Maize", "rice": "Paddy(Dhan)",
        "cotton": "Cotton", "jute": "Jute", "coffee": "Coffee", "banana": "Banana",
        "mango": "Mango", "grapes": "Grapes", "orange": "Orange", "coconut": "Coconut",
        "muskmelon": "Muskmelon", "papaya": "Papaya", "pomegranate": "Pomegranate",
        "watermelon": "Watermelon", "apple": "Apple",
    }
    commodity = aliases.get(crop_name.lower().strip(), crop_name.strip())
    if not api_key:
        return {
            "crop": crop_name, "state": state, "data_status": "unavailable",
            "message": "Live mandi data needs a data.gov.in API key. Configure DATA_GOV_IN_API_KEY to enable today's market prices.",
        }
    try:
        response = requests.get(
            "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070",
            params={
                "api-key": api_key, "format": "json", "limit": 100,
                "filters[commodity]": commodity, "filters[state]": state,
                "sort[arrival_date]": "desc",
            }, timeout=10,
        )
        response.raise_for_status()
        records = response.json().get("records", [])
        if records:
            record = records[0]
            modal = float(record["modal_price"])
            return {
                "crop": crop_name, "commodity": record.get("commodity", commodity),
                "state": record.get("state", state), "district": record.get("district"),
                "market": record.get("market"), "arrival_date": record.get("arrival_date"),
                "min_price_per_quintal": float(record["min_price"]),
                "max_price_per_quintal": float(record["max_price"]),
                "modal_price_per_quintal": modal, "price_per_kg": round(modal / 100, 2),
                "data_status": "live", "data_source": "AGMARKNET via data.gov.in",
            }
        return {"crop": crop_name, "state": state, "data_status": "no_records", "message": f"No recent official market record found for {commodity} in {state}."}
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return {"crop": crop_name, "state": state, "data_status": "unavailable", "message": "The official mandi feed is temporarily unavailable. Try again later."}


def fetch_market_comparison(crop_name: str, state: str = "Maharashtra") -> Dict[str, Any]:
    """Return the latest reported rate per mandi in a state for farmer comparison."""
    api_key = os.environ.get("DATA_GOV_IN_API_KEY")
    aliases = {
        "chickpea": "Gram", "kidneybeans": "Kidney Beans", "pigeonpeas": "Arhar (Tur/Red Gram)",
        "mungbean": "Moong (Green Gram)", "blackgram": "Urad", "mothbeans": "Moth",
        "lentil": "Lentil (Masur)", "maize": "Maize", "rice": "Paddy(Dhan)",
        "cotton": "Cotton", "jute": "Jute", "coffee": "Coffee", "banana": "Banana",
        "mango": "Mango", "grapes": "Grapes", "orange": "Orange", "coconut": "Coconut",
        "muskmelon": "Muskmelon", "papaya": "Papaya", "pomegranate": "Pomegranate",
        "watermelon": "Watermelon", "apple": "Apple",
    }
    commodity = aliases.get(crop_name.lower().strip(), crop_name.strip())
    if not api_key:
        return {"status": "unavailable", "crop": crop_name, "state": state,
                "message": "Market comparison needs DATA_GOV_IN_API_KEY on the server."}
    try:
        response = requests.get(
            "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070",
            params={"api-key": api_key, "format": "json", "limit": 500,
                   "filters[commodity]": commodity, "filters[state]": state,
                   "sort[arrival_date]": "desc"}, timeout=12,
        )
        response.raise_for_status()
        records = response.json().get("records", [])
        latest_by_market = {}
        for record in records:
            try:
                modal = float(record["modal_price"])
                low, high = float(record["min_price"]), float(record["max_price"])
                market = record.get("market") or "Unknown market"
                district = record.get("district") or ""
                key = (market.casefold(), district.casefold())
                date_text = str(record.get("arrival_date", ""))
                parsed_date = None
                for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                    try:
                        parsed_date = datetime.strptime(date_text, fmt)
                        break
                    except ValueError:
                        pass
                sort_date = parsed_date or datetime.min
                item = {"market": market, "district": district,
                        "arrival_date": date_text, "min_price_per_quintal": low,
                        "max_price_per_quintal": high, "modal_price_per_quintal": modal}
                if key not in latest_by_market or sort_date > latest_by_market[key][0]:
                    latest_by_market[key] = (sort_date, item)
            except (ValueError, KeyError, TypeError):
                continue
        markets = [item for _, item in latest_by_market.values()]
        markets.sort(key=lambda item: item["modal_price_per_quintal"], reverse=True)
        return {"status": "live" if markets else "no_records", "crop": crop_name,
                "commodity": commodity, "state": state, "markets": markets[:25],
                "highest_reported": markets[0] if markets else None,
                "data_source": "AGMARKNET via data.gov.in",
                "message": "Reported wholesale rates only; these are not confirmed buyer offers."}
    except (requests.RequestException, ValueError, TypeError):
        return {"status": "unavailable", "crop": crop_name, "state": state,
                "message": "The official mandi comparison feed is temporarily unavailable."}
