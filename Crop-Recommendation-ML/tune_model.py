from pathlib import Path
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split, GridSearchCV, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import SVC

# 1. Dataset loading
BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "dataset" / "Crop_recommendation.csv"

print(f"Loading dataset: {CSV_FILE}")
if not CSV_FILE.exists():
    raise FileNotFoundError(f"Dataset not found: {CSV_FILE}")

df = pd.read_csv(CSV_FILE)
df = df.drop_duplicates()

# 2. Features and target
features = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]
X = df[features]
y = df["label"]

# 3. Train-test split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.20, random_state=42, stratify=y
)

# 4. 5-Fold Cross Validation
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

# Dictionary to hold the best estimators and their test scores
model_results = {}  # Pick a model using training-fold CV, never hold-out accuracy.

# ------------------------------------------------
# RANDOM FOREST
# ------------------------------------------------
print("\n--- Tuning Random Forest ---")
rf = RandomForestClassifier(random_state=42, n_jobs=-1)
rf_params = {
    "n_estimators": [100, 200],
    "max_depth": [None, 15],
    "min_samples_split": [2, 5]
}
rf_search = GridSearchCV(rf, rf_params, cv=cv, scoring="accuracy", n_jobs=-1, verbose=1)
rf_search.fit(X_train, y_train)

rf_best = rf_search.best_estimator_
model_results["Random Forest"] = (rf_best, rf_search.best_score_)
print(f"Random Forest Best CV Score: {rf_search.best_score_:.4f}")

# ------------------------------------------------
# SVM (with probability=True for Top-3 predictions)
# ------------------------------------------------
print("\n--- Tuning SVM ---")
svm_pipeline = Pipeline([
    ("scaler", StandardScaler()),
    ("model", SVC(probability=True, random_state=42))
])
svm_params = {
    "model__C": [1, 10],
    "model__gamma": ["scale", 0.01],
    "model__kernel": ["rbf"]
}
svm_search = GridSearchCV(svm_pipeline, svm_params, cv=cv, scoring="accuracy", n_jobs=-1, verbose=1)
svm_search.fit(X_train, y_train)

svm_best = svm_search.best_estimator_
model_results["SVM"] = (svm_best, svm_search.best_score_)
print(f"SVM Best CV Score: {svm_search.best_score_:.4f}")

# ------------------------------------------------
# GRADIENT BOOSTING
# ------------------------------------------------
print("\n--- Tuning Gradient Boosting ---")
gb = GradientBoostingClassifier(random_state=42)
gb_params = {
    "n_estimators": [100],
    "learning_rate": [0.1],
    "max_depth": [3]
}
gb_search = GridSearchCV(gb, gb_params, cv=cv, scoring="accuracy", n_jobs=-1, verbose=1)
gb_search.fit(X_train, y_train)

gb_best = gb_search.best_estimator_
model_results["Gradient Boosting"] = (gb_best, gb_search.best_score_)
print(f"Gradient Boosting Best CV Score: {gb_search.best_score_:.4f}")

# ------------------------------------------------
# SELECT & SAVE THE BEST MODEL
# ------------------------------------------------
best_name = max(model_results, key=lambda k: model_results[k][1])
best_estimator, best_cv_score = model_results[best_name]
holdout_accuracy = best_estimator.score(X_test, y_test)

print("\n====================================")
print(f"WINNER: {best_name} (training-fold CV accuracy: {best_cv_score * 100:.2f}%)")
print(f"One-time held-out test accuracy: {holdout_accuracy * 100:.2f}%")
print("====================================")

MODEL_PATH = BASE_DIR / "crop_model.pkl"
joblib.dump(best_estimator, MODEL_PATH)
print(f"Saved winning model to: {MODEL_PATH}")