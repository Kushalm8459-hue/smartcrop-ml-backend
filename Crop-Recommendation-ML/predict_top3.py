import pandas as pd
from pathlib import Path
import joblib
import numpy as np


# ------------------------------------------------
# 1. Load trained model
# ------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
MODEL_FILE = BASE_DIR / "crop_model.pkl"

print(f"Loading model: {MODEL_FILE}")

if not MODEL_FILE.exists():
    raise FileNotFoundError(f"Model file not found: {MODEL_FILE}")

model = joblib.load(MODEL_FILE)
print("Model loaded successfully!")


# ------------------------------------------------
# 2. Sample input for testing
# ------------------------------------------------

features = [
    "N",
    "P",
    "K",
    "temperature",
    "humidity",
    "ph",
    "rainfall"
]

sample_input = {
    "N": 90,
    "P": 42,
    "K": 43,
    "temperature": 20.87,
    "humidity": 82.00,
    "ph": 6.50,
    "rainfall": 202.93
}

input_df = pd.DataFrame([sample_input])[features]


# ------------------------------------------------
# 3. Predict probabilities
# ------------------------------------------------

probabilities = model.predict_proba(input_df)[0]
crops = model.classes_

top_3_indices = np.argsort(probabilities)[::-1][:3]


# ------------------------------------------------
# 4. Display recommendations
# ------------------------------------------------

print("\n====================================")
print("TOP 3 CROP RECOMMENDATIONS")
print("====================================")

for rank, idx in enumerate(top_3_indices, start=1):
    crop_name = crops[idx].capitalize()
    confidence = probabilities[idx] * 100
    print(f"{rank}. {crop_name:<15} | Suitability: {confidence:.2f}%")

print("====================================")