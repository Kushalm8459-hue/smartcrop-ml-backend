"""
SmartCrop AI: External API Services
Fetches real-time weather (via Name or GPS Coordinates) and commodity market (Mandi) rates.
"""

from typing import Dict, Any, Optional
import os
import json
import urllib.parse
import requests


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
