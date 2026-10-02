import pandas as pd
from pathlib import Path

# Find project folder
BASE_DIR = Path(__file__).resolve().parent

# Dataset path
CSV_FILE = BASE_DIR / "dataset" / "Crop_recommendation.csv"

# Load dataset
df = pd.read_csv(CSV_FILE)

print("=" * 50)
print("SMARTCROP AI - DATASET ANALYSIS")
print("=" * 50)

# 1. Dataset shape
print("\n1. DATASET SHAPE")
print("Rows:", df.shape[0])
print("Columns:", df.shape[1])

# 2. Column information
print("\n2. COLUMN INFORMATION")
print(df.info())

# 3. Statistical summary
print("\n3. STATISTICAL SUMMARY")
print(df.describe())

# 4. Missing values
print("\n4. MISSING VALUES")
print(df.isnull().sum())

# 5. Duplicate rows
print("\n5. DUPLICATE ROWS")
print(df.duplicated().sum())

# 6. Number of different crops
print("\n6. NUMBER OF CROPS")
print(df["label"].nunique())

# 7. Crop distribution
print("\n7. CROP DISTRIBUTION")
print(df["label"].value_counts())

# 8. Unique crop names
print("\n8. CROP NAMES")
print(sorted(df["label"].unique()))