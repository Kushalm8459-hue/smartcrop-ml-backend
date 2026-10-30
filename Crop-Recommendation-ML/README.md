# SmartCrop AI

## Spring Boot backend integration

This project includes a small Java/Spring Boot backend in [`springboot/`](springboot/README.md). The existing frontend sends crop recommendation requests through Spring Boot, which forwards them to the existing FastAPI and ML backend. Run FastAPI on port 8000 and Spring Boot on port 8081 as described in the integration guide.

A local college-project prototype for farmer accounts, saved farm profiles, a trained crop suitability model, rule-based crop planning, local weather, and official daily mandi records when configured.

## Start locally on Windows

Open PowerShell in this folder (`Crop-Recommendation-ML`):

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:SMARTCROP_SECRET_KEY = (python -c "import secrets; print(secrets.token_urlsafe(48))")
# Optional: set a data.gov.in API key to show official mandi rates
$env:DATA_GOV_IN_API_KEY = "your-data-gov-in-key"
# Add GEMINI_API_KEY to a local ignored .env file to enable chat and crop-photo guidance.
python -m uvicorn main_api:app --reload
```

Open <http://127.0.0.1:8000/> for the farmer app and <http://127.0.0.1:8000/docs> for the API reference. The app serves the API and frontend from one origin. SQLite creates `smartcrop.db` beside the backend files.

For the Spring Boot practical flow, keep this Python server running and start the Java service in a second PowerShell window from `springboot` with `mvn spring-boot:run`. The Java service runs at `http://127.0.0.1:8081`; the app page stays at `http://127.0.0.1:8000/`.

Farmer accounts and farm records persist in the configured database. Local development uses this SQLite file. For deployment, set `SMARTCROP_DATABASE_URL` (or the hosting provider's `DATABASE_URL`) to a managed PostgreSQL database, or mount persistent storage and set `SMARTCROP_DATA_DIR` to its path. Keep `SMARTCROP_SECRET_KEY` stable between deploys so current sessions remain valid. A GitHub push by itself cannot provide durable server storage; the host must provide the database or persistent disk.

To run with your existing repository-level virtual environment, activate `..\venv\Scripts\Activate.ps1` instead. Install this folder's `requirements.txt` into that environment first.

## Included flows

- Phone-number and password signup/login; passwords are hashed, and API sessions expire after seven days.
- Farmer profile endpoint and one saved farm profile per year.
- Editable farmer account details from the dashboard profile card.
- Report-aware SmartCrop chat and crop-photo triage via the Google Gemini API when `GEMINI_API_KEY` is configured in the backend environment.
- Authenticated crop reports with top-three model suggestions, budget-aware decision ranking, cost breakdowns, seasonal water estimates, risk notes, and rainfall/price what-if scenarios.
- Optional private soil-health report (PDF or image) and up to five farm/soil photos saved to the farmer's yearly profile. Files are served only to their signed-in owner; accepted formats are PDF, JPG, PNG and WEBP.
- Illustrative crop photos from Wikimedia Commons on recommendation cards, with a link to each image's attribution/licence page.
- Manually entered farm budget with a ₹20,000 minimum and no application-level upper limit.
- Crop photo triage with crop, growth-stage, soil-type and current local weather context when live weather is available. It requires `GEMINI_API_KEY`; the photo is sent to Google for analysis and is not saved by SmartCrop.
- Farmer profile harvest history, an authenticated farmer community feed, and opt-in farmer produce listings with an explicit choice before showing a seller's phone number.
- State-wide mandi record comparison: latest returned AGMARKNET rate per market, sorted by modal price, when the data.gov.in key is configured.
- Separate model rainfall input from expected seasonal rainfall, so the training feature is not confused with a seven-day forecast or an entire growing season.
- Indian place-name search and optional browser GPS for current Open-Meteo weather.
- Official daily AGMARKNET-derived mandi lookups through the data.gov.in API when `DATA_GOV_IN_API_KEY` is configured.

## Read the report carefully

Enter N/P/K and pH from a soil test when possible. The crop model was trained on the included demonstration dataset; its rainfall feature spans about 20–299 mm, so the form keeps that input separate from your whole-season rainfall estimate. Model scores compare its crop classes and are not probabilities of success. Sowing windows, input costs, water needs and expected yield use project reference assumptions; check them locally. The rainfall and market what-if scenarios are arithmetic illustrations, not forecasts.

Soil reports and field photos are stored as private farmer files, but the current model does not extract soil values from reports or diagnose soil/crop condition from images. Farmers must still enter soil N, P, K and pH measurements manually. Local uploaded files are stored in `uploads/`, which is ignored by Git. On a hosted service, configure persistent disk/storage for this folder if files must survive redeployments; otherwise the host may delete uploaded files when replacing the app instance.

The crop-health photo feature is an AI visual triage aid, not a verified diagnosis. It avoids pesticide brands, chemical mixtures and dosage instructions; confirm suspected disease, nutrient needs and treatment with a local agriculture officer/KVK. Gemini free-tier availability and quotas can change; free-tier prompts and uploaded photos may be used by Google to improve its products. Do not send private personal information or documents. A free tier has usage limits and is not guaranteed availability. The community and produce listings are visible only after sign-in; SmartCrop does not process sales, buyer guarantees, logistics or payments. Seller phone numbers are returned to signed-in farmers only when the seller checked the sharing option.

The current crop classifier was trained on a demonstration dataset with N, P, K, temperature, humidity, pH and rainfall. It was not trained on farm location, soil texture, season dates, previous harvests, budget or market price. Those values are stored/displayed or used by existing planning rules, but do not make the classifier a local yield/profit predictor. Soil type is saved as profile context; obtain local multi-year yield/price data and agronomist-reviewed crop rules before treating the shortlist as a location-optimized profit recommendation. Mandi comparison uses one official data.gov.in/AGMARKNET feed across markets in a selected state, not several online trading platforms or guaranteed dealer bids.

Weather requires an internet connection. Weather and place search use Open-Meteo and require an internet connection. Mandi requests need a data.gov.in API key; when the key, a recent official record or network access is unavailable, the app says so rather than inventing a current quote. A daily mandi record may be delayed. Never commit API keys, the database, or production secrets to Git.

To enable AI chat and crop-photo guidance, copy `.env.example` to `.env`, set `GEMINI_API_KEY` to a Google AI Studio API key, optionally set `GEMINI_MODEL` (defaults to `gemini-3.1-flash-lite`), and restart Uvicorn. The key stays on the backend and is never sent to the browser. Google currently offers a Gemini API free tier with model and rate limits; free-tier content may be used to improve Google's products, and free access can change. See the [Gemini API pricing and tier terms](https://ai.google.dev/gemini-api/docs/pricing). For a hosted deployment, configure `GEMINI_API_KEY` as a private environment variable in your hosting dashboard and redeploy. Official mandi data uses the data.gov.in API when `DATA_GOV_IN_API_KEY` is set. Without it, SmartCrop tries a community-operated, keyless fallback that currently covers Maharashtra, Uttar Pradesh, Punjab, Madhya Pradesh and Karnataka; it may be delayed or unavailable. The fallback displays its provider and reported arrival date, and does not invent prices. The Farm services page shows provider status; `/api/v1/services/status` reports readiness without exposing keys. Never commit `.env` or share its key values in chat.

## GitHub

The app is inside the Git repository folder `Crop-Recommendation-ML`. From the repository root, stage only the app source changes (do not stage the database or `__pycache__`):

```powershell
git status
git add Crop-Recommendation-ML/main_api.py Crop-Recommendation-ML/database.py Crop-Recommendation-ML/external_services.py Crop-Recommendation-ML/decision_engine.py Crop-Recommendation-ML/tune_model.py Crop-Recommendation-ML/index.html Crop-Recommendation-ML/requirements.txt Crop-Recommendation-ML/README.md Crop-Recommendation-ML/.gitignore Crop-Recommendation-ML/.env.example
git commit -m "Build SmartCrop farmer web application"
git push
```

If your branch has no upstream yet, Git will print the command to set one; usually that is `git push -u origin <your-branch-name>`. Stage only the listed source and documentation files. This repository already tracks generated files; avoid `git add -A` and do not stage `smartcrop.db` or `__pycache__`. Do not commit real API keys or any database containing personal farmer information.
