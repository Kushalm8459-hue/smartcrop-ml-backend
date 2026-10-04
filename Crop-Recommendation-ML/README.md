# SmartCrop AI

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
# Add OPENAI_API_KEY to a local ignored .env file to enable the report-aware chatbot.
python -m uvicorn main_api:app --reload
```

Open <http://127.0.0.1:8000/> for the farmer app and <http://127.0.0.1:8000/docs> for the API reference. The app serves the API and frontend from one origin. SQLite creates `smartcrop.db` beside the backend files.

To run with your existing repository-level virtual environment, activate `..\venv\Scripts\Activate.ps1` instead. Install this folder's `requirements.txt` into that environment first.

## Included flows

- Phone-number and password signup/login; passwords are hashed, and API sessions expire after seven days.
- Farmer profile endpoint and one saved farm profile per year.
- Editable farmer account details from the dashboard profile card.
- Report-aware SmartCrop chat via the OpenAI Responses API when `OPENAI_API_KEY` is configured in the local `.env` file.
- Authenticated crop reports with top-three model suggestions, budget-aware decision ranking, cost breakdowns, seasonal water estimates, risk notes, and rainfall/price what-if scenarios.
- Separate model rainfall input from expected seasonal rainfall, so the training feature is not confused with a seven-day forecast or an entire growing season.
- Indian place-name search and optional browser GPS for current Open-Meteo weather.
- Official daily AGMARKNET-derived mandi lookups through the data.gov.in API when `DATA_GOV_IN_API_KEY` is configured.

## Read the report carefully

Enter N/P/K and pH from a soil test when possible. The crop model was trained on the included demonstration dataset; its rainfall feature spans about 20–299 mm, so the form keeps that input separate from your whole-season rainfall estimate. Model scores compare its crop classes and are not probabilities of success. Sowing windows, input costs, water needs and expected yield use project reference assumptions; check them locally. The rainfall and market what-if scenarios are arithmetic illustrations, not forecasts.

Weather requires an internet connection. Weather and place search use Open-Meteo and require an internet connection. Mandi requests need a data.gov.in API key; when the key, a recent official record or network access is unavailable, the app says so rather than inventing a current quote. A daily mandi record may be delayed. Never commit API keys, the database, or production secrets to Git.

To enable AI chat, copy `.env.example` to `.env`, replace the empty `OPENAI_API_KEY=` value with your own API key, optionally set `OPENAI_MODEL`, and restart Uvicorn. The key stays on the backend and is never sent to the browser. OpenAI API usage may incur charges under your API account. The chatbot uses the OpenAI Responses API and receives only the question, recent chat turns, and the crop report currently displayed.

## GitHub

The app is inside the Git repository folder `Crop-Recommendation-ML`. From the repository root, stage only the app source changes (do not stage the database or `__pycache__`):

```powershell
git status
git add Crop-Recommendation-ML/main_api.py Crop-Recommendation-ML/database.py Crop-Recommendation-ML/external_services.py Crop-Recommendation-ML/decision_engine.py Crop-Recommendation-ML/tune_model.py Crop-Recommendation-ML/index.html Crop-Recommendation-ML/requirements.txt Crop-Recommendation-ML/README.md Crop-Recommendation-ML/.gitignore Crop-Recommendation-ML/.env.example
git commit -m "Build SmartCrop farmer web application"
git push
```

If your branch has no upstream yet, Git will print the command to set one; usually that is `git push -u origin <your-branch-name>`. Stage only the listed source and documentation files. This repository already tracks generated files; avoid `git add -A` and do not stage `smartcrop.db` or `__pycache__`. Do not commit real API keys or any database containing personal farmer information.
