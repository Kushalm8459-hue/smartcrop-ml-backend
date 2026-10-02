import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

CSV_FILE = BASE_DIR / "dataset" / "Crop_recommendation.csv"

print(f"Loading dataset from: {CSV_FILE}")

if not CSV_FILE.exists():
    raise FileNotFoundError(f"Dataset not found: {CSV_FILE}")

df = pd.read_csv(CSV_FILE)

print("\nFirst 5 rows:")
print(df.head())

print("\nShape:")
print(df.shape)

print("\nColumns:")
print(df.columns.tolist())

print("\nMissing values:")
print(df.isnull().sum())

print("\nDuplicate rows:")
print(df.duplicated().sum())

print("\nData types:")
print(df.dtypes)

print("\nCrop distribution:")
print(df["label"].value_counts())