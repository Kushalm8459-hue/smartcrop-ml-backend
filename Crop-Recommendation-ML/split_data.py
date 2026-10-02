import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split

# --------------------------------------------------
# 1. Load dataset
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "dataset" / "Crop_recommendation.csv"

df = pd.read_csv(CSV_FILE)

# --------------------------------------------------
# 2. Remove duplicates
# --------------------------------------------------

df = df.drop_duplicates()

# --------------------------------------------------
# 3. Define features and target
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

X = df[features]
y = df["label"]

# --------------------------------------------------
# 4. Split dataset
# --------------------------------------------------

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y
)

# --------------------------------------------------
# 5. Display results
# --------------------------------------------------

print("=" * 50)
print("SMARTCROP AI - TRAIN / TEST SPLIT")
print("=" * 50)

print("\nOriginal dataset:")
print("X:", X.shape)
print("y:", y.shape)

print("\nTraining data:")
print("X_train:", X_train.shape)
print("y_train:", y_train.shape)

print("\nTesting data:")
print("X_test:", X_test.shape)
print("y_test:", y_test.shape)

print("\nTraining crop distribution:")
print(y_train.value_counts())

print("\nTesting crop distribution:")
print(y_test.value_counts())

print("\nTrain/Test split completed successfully.")