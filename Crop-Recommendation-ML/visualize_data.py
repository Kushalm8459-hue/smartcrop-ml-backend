import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Project directory
BASE_DIR = Path(__file__).resolve().parent

# Dataset path
CSV_FILE = BASE_DIR / "dataset" / "Crop_recommendation.csv"

# Load dataset
df = pd.read_csv(CSV_FILE)

# Numerical features
features = [
    "N",
    "P",
    "K",
    "temperature",
    "humidity",
    "ph",
    "rainfall"
]

# --------------------------------------------------
# 1. Feature distributions
# --------------------------------------------------

df[features].hist(
    figsize=(14, 10),
    bins=20
)

plt.suptitle("SmartCrop AI - Feature Distributions")
plt.tight_layout()
plt.show()


# --------------------------------------------------
# 2. Crop distribution
# --------------------------------------------------

plt.figure(figsize=(12, 7))

sns.countplot(
    data=df,
    y="label",
    order=df["label"].value_counts().index
)

plt.title("Number of Samples per Crop")
plt.xlabel("Number of Samples")
plt.ylabel("Crop")

plt.tight_layout()
plt.show()


# --------------------------------------------------
# 3. Correlation heatmap
# --------------------------------------------------

plt.figure(figsize=(10, 7))

correlation = df[features].corr()

sns.heatmap(
    correlation,
    annot=True,
    cmap="coolwarm",
    fmt=".2f"
)

plt.title("Feature Correlation Matrix")

plt.tight_layout()
plt.show()


# --------------------------------------------------
# 4. Boxplots - detect unusual values
# --------------------------------------------------

plt.figure(figsize=(14, 8))

sns.boxplot(data=df[features])

plt.title("Feature Boxplots")
plt.xticks(rotation=45)

plt.tight_layout()
plt.show()