import pandas as pd
from pathlib import Path

# --------------------------------------------------
# 1. Project and dataset path
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "dataset" / "Crop_recommendation.csv"

# --------------------------------------------------
# 2. Load dataset
# --------------------------------------------------

df = pd.read_csv(CSV_FILE)

print("=" * 50)
print("SMARTCROP AI - DATA PREPARATION")
print("=" * 50)

print("\nOriginal dataset shape:")
print(df.shape)

# --------------------------------------------------
# 3. Remove duplicate rows
# --------------------------------------------------

duplicate_count = df.duplicated().sum()

print("\nDuplicate rows found:")
print(duplicate_count)

if duplicate_count > 0:
    df = df.drop_duplicates()
    print("Duplicate rows removed.")
else:
    print("No duplicate rows to remove.")

print("\nDataset shape after duplicate check:")
print(df.shape)

# --------------------------------------------------
# 4. Check missing values
# --------------------------------------------------

print("\nMissing values:")
print(df.isnull().sum())

# --------------------------------------------------
# 5. Define features and target
# --------------------------------------------------

features = [
    "N",
    "P",
    "K",
    "temperature",
    "humidity",
    "ph",
    "rainfall"
]

target = "label"

X = df[features]
y = df[target]

# --------------------------------------------------
# 6. Display features and target
# --------------------------------------------------

print("\nFeatures:")
print(X.columns.tolist())

print("\nTarget:")
print(target)

print("\nFeature shape:")
print(X.shape)

print("\nTarget shape:")
print(y.shape)

# --------------------------------------------------
# 7. Display sample input
# --------------------------------------------------

print("\nSample feature data:")
print(X.head())

print("\nSample target values:")
print(y.head())

# --------------------------------------------------
# 8. Check target classes
# --------------------------------------------------

print("\nNumber of crop classes:")
print(y.nunique())

print("\nCrop classes:")
print(sorted(y.unique()))

print("\nCrop distribution:")
print(y.value_counts())

print("\nData preparation completed successfully.")