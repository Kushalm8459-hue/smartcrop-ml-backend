import pandas as pd
from pathlib import Path

from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import SVC


# --------------------------------------------------
# 1. Load dataset
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "dataset" / "Crop_recommendation.csv"

df = pd.read_csv(CSV_FILE)

# Remove duplicates
df = df.drop_duplicates()


# --------------------------------------------------
# 2. Features and target
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
# 3. Define models
# --------------------------------------------------

models = {

    "Logistic Regression": Pipeline([
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(
            max_iter=2000,
            random_state=42
        ))
    ]),

    "KNN": Pipeline([
        ("scaler", StandardScaler()),
        ("model", KNeighborsClassifier(
            n_neighbors=5
        ))
    ]),

    "Decision Tree": DecisionTreeClassifier(
        random_state=42
    ),

    "Random Forest": RandomForestClassifier(
        n_estimators=300,
        random_state=42,
        n_jobs=-1
    ),

    "SVM": Pipeline([
        ("scaler", StandardScaler()),
        ("model", SVC(
            probability=True,
            random_state=42
        ))
    ]),

    "Gradient Boosting": GradientBoostingClassifier(
        random_state=42
    )
}


# --------------------------------------------------
# 4. Stratified 5-Fold Cross Validation
# --------------------------------------------------

cv = StratifiedKFold(
    n_splits=5,
    shuffle=True,
    random_state=42
)


# --------------------------------------------------
# 5. Evaluation metrics
# --------------------------------------------------

scoring = {
    "accuracy": "accuracy",
    "precision": "precision_weighted",
    "recall": "recall_weighted",
    "f1": "f1_weighted"
}


# --------------------------------------------------
# 6. Run cross-validation
# --------------------------------------------------

results = []

print("=" * 75)
print("SMARTCROP AI - 5-FOLD CROSS-VALIDATION")
print("=" * 75)

for name, model in models.items():

    print(f"\nEvaluating: {name}")

    scores = cross_validate(
        model,
        X,
        y,
        cv=cv,
        scoring=scoring,
        n_jobs=-1
    )

    results.append({
        "Model": name,
        "Accuracy Mean": scores["test_accuracy"].mean(),
        "Accuracy Std": scores["test_accuracy"].std(),
        "Precision Mean": scores["test_precision"].mean(),
        "Recall Mean": scores["test_recall"].mean(),
        "F1 Mean": scores["test_f1"].mean()
    })


# --------------------------------------------------
# 7. Display results
# --------------------------------------------------

results_df = pd.DataFrame(results)

print("\n" + "=" * 75)
print("CROSS-VALIDATION RESULTS")
print("=" * 75)

print(
    results_df.to_string(
        index=False,
        formatters={
            "Accuracy Mean": "{:.4f}".format,
            "Accuracy Std": "{:.4f}".format,
            "Precision Mean": "{:.4f}".format,
            "Recall Mean": "{:.4f}".format,
            "F1 Mean": "{:.4f}".format
        }
    )
)

print("\nCross-validation completed successfully.")