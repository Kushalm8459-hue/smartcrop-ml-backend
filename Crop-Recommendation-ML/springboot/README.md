# SmartCrop Spring Boot integration

This is the Java backend for the existing SmartCrop application. The existing HTML/CSS/JavaScript frontend and Python FastAPI/ML backend remain in the parent folder. The recommendation request now travels through Spring Boot before reaching FastAPI.

```text
Browser at :8000 → Spring Boot at :8081 → FastAPI + ML at :8000 → Spring Boot → browser
```

The browser still uses FastAPI directly for sign-in, profiles, weather, uploads and other existing features. Only the crop recommendation request is routed through Spring Boot. FastAPI keeps the existing authentication, database persistence, trained scikit-learn model and crop planning logic.

## Run the project

Use two PowerShell windows. Java 17+ and Maven are required for the Spring Boot backend.

**Terminal 1: start the existing Python app** (from the parent `Crop-Recommendation-ML` folder):

```powershell
python -m uvicorn main_api:app --reload --port 8000
```

**Terminal 2: start the Java backend** (from this `springboot` folder):

```powershell
mvn spring-boot:run
```

Open <http://127.0.0.1:8000/> and sign in or create a demo account. The app page is served by Python, while its crop report request goes through Spring Boot on port 8081. Both servers must stay running.

## Endpoints

- `GET http://127.0.0.1:8081/api/health` — Spring Boot health check.
- `POST http://127.0.0.1:8081/api/v1/farmer/recommend` — validates the farm request, forwards it to Python, and returns the crop report.
- `POST http://127.0.0.1:8000/api/v1/farmer/recommend` — existing authenticated Python endpoint called by Spring Boot.
- `GET http://127.0.0.1:8000/api/health` — Python API health check.

The recommendation request carries a Bearer token from the signed-in farmer. Spring Boot forwards that token to FastAPI, which continues to enforce authentication and save the yearly farm profile.

## Main Java classes

- `SmartCropApplication` — Java `main` method and Spring Boot startup.
- `RecommendationController` — `@RestController`; exposes `GET /api/health` and `POST /api/v1/farmer/recommend`.
- `RecommendationRequest` — request DTO with Jakarta validation matching Python's farm profile fields.
- `PythonRecommendationClient` — Spring `RestClient` that calls the existing FastAPI recommendation endpoint and forwards the authorization header.
- `WebConfig` — allows the existing browser app on port 8000 to call Spring Boot on port 8081.
- `ApiErrorHandler` — returns useful upstream Python errors and a clear response when FastAPI is not running.

`pom.xml` declares Spring Web and Validation. `application.properties` sets the Java server to port 8081 and the Python API base URL to `http://127.0.0.1:8000`. Change `smartcrop.python-api-url` if FastAPI runs at a different address.

## Deploy to Render

The repository-root `render.yaml` defines the Java Spring Boot web service. It calls the existing Python service at `https://smartcrop-ml-backend.onrender.com`, so the Blueprint will not create a duplicate Python service. Create a Blueprint in Render from this repository's `main` branch and deploy the Java service. Then set `SMARTCROP_SPRING_API_URL` on the existing Python service to the deployed Java service URL and let that service redeploy. The frontend will then route crop recommendations through Spring Boot.

This demo Blueprint uses SQLite and Render's ephemeral service filesystem to avoid creating a paid database or persistent disk. Free services can spin down when idle, and local files can be lost on spin-down, restart, or redeploy. Treat farmer accounts, farm reports, and uploads on the public demo as temporary test data; this configuration is for an exam demo, not production persistence. Render documents these free-service limits in its [free instance guide](https://render.com/docs/free).

## Viva explanation

> “The existing SmartCrop frontend sends the recommendation request to my Spring Boot REST controller. The controller validates the JSON request and passes it to a service that uses Spring's RestClient to call the existing FastAPI backend. Spring forwards the signed-in farmer's Bearer token. FastAPI runs the scikit-learn model and existing crop planning logic, saves the profile, and returns JSON. Spring Boot passes that response back to the browser. This lets the project demonstrate Java Spring Boot and Python ML together without duplicating or retraining the model.”

Spring Boot does not train or run the ML model in this design. The Python service owns predictions and farm-report persistence; Java demonstrates REST controllers, request validation, dependency injection, HTTP client integration, CORS and error handling.
