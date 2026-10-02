import pandas as pd
from pathlib import Path

from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix


# --------------------------------------------------
# 1. Load dataset
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "dataset" / "Crop_recommendation.csv"

df = pd.read_csv(CSV_FILE)


# --------------------------------------------------
# 2. Remove duplicate rows
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
# 4. Train/Test split
# --------------------------------------------------

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y
)


# --------------------------------------------------
# 5. Create ML pipeline
# --------------------------------------------------

model = Pipeline([
    ("scaler", StandardScaler()),
    ("classifier", LogisticRegression(
        max_iter=2000,
        random_state=42
    ))
])


# --------------------------------------------------
# 6. Train model
# --------------------------------------------------

print("=" * 60)
print("SMARTCROP AI - BASELINE MODEL")
print("=" * 60)

print("\nTraining Logistic Regression...")

model.fit(X_train, y_train)

print("Training completed.")


# --------------------------------------------------
# 7. Make predictions
# --------------------------------------------------

y_pred = model.predict(X_test)


# --------------------------------------------------
# 8. Accuracy
# --------------------------------------------------

accuracy = accuracy_score(y_test, y_pred)

print("\nModel Accuracy:")
print(f"{accuracy:.4f}")

print(f"\nModel Accuracy Percentage:")
print(f"{accuracy * 100:.2f}%")


# --------------------------------------------------
# 9. Classification report
# --------------------------------------------------

print("\nClassification Report:")
print(classification_report(y_test, y_pred))


# --------------------------------------------------
# 10. Confusion matrix
# --------------------------------------------------

print("\nConfusion Matrix:")
print(confusion_matrix(y_test, y_pred))


print("\nBaseline model completed successfully.")