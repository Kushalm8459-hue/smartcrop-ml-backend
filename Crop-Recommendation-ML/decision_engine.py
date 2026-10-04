import pandas as pd
from pathlib import Path
import joblib
import numpy as np

from knowledge_base import CROP_DATABASE, DEFAULT_METRICS


# ------------------------------------------------
# 1. Load trained model
# ------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
MODEL_FILE = BASE_DIR / "crop_model.pkl"

if not MODEL_FILE.exists():
    raise FileNotFoundError(f"Model file not found: {MODEL_FILE}")

model = joblib.load(MODEL_FILE)


# ------------------------------------------------
# 2. Decision Logic Engine
# ------------------------------------------------

def compute_detailed_costs(crop_info, acres):
    """Calculates granular line-item costs scaled by farm acreage."""
    breakdown = {
        "seeds": round(crop_info["seed_cost_per_acre"] * acres),
        "fertilizer": round(crop_info["fertilizer_cost_per_acre"] * acres),
        "labor": round(crop_info["labor_cost_per_acre"] * acres),
        "machinery": round(crop_info["machinery_cost_per_acre"] * acres),
        "irrigation": round(crop_info["irrigation_cost_per_acre"] * acres),
        "pesticides": round(crop_info["pesticide_cost_per_acre"] * acres)
    }
    total_cost = sum(breakdown.values())
    return breakdown, total_cost


def compute_water_balance(crop_info, acres, rainfall_mm):
    """
    1 mm of rain over 1 acre = 4,046.86 liters.
    Calculates total water needed vs irrigation deficit.
    """
    water_req_mm = crop_info["water_requirement_mm"]
    liters_per_mm_acre = 4046.86
    total_water_liters = round(water_req_mm * acres * liters_per_mm_acre)
    water_deficit_mm = max(0.0, water_req_mm - rainfall_mm)
    irrigation_liters = round(water_deficit_mm * acres * liters_per_mm_acre)

    return {
        "requirement_mm": water_req_mm,
        "total_water_liters": total_water_liters,
        "deficit_mm": round(water_deficit_mm, 1),
        "irrigation_liters": irrigation_liters
    }


def generate_rationales(crop_name, suitability, total_cost, budget, water_deficit_mm, market_risk):
    """Generates human-readable Why and Why-Not explanations."""
    pros = []
    cons = []

    # Agronomic match
    if suitability >= 80:
        pros.append(f"The crop model ranked this soil and climate combination highly ({suitability:.1f} similarity score).")
    else:
        pros.append(f"The crop model gives this soil and climate combination a {suitability:.1f} similarity score.")

    # Financial viability
    if total_cost <= budget:
        margin = budget - total_cost
        pros.append(f"Fits within budget with a surplus safety buffer of ₹{margin:,}.")
    else:
        deficit = total_cost - budget
        cons.append(f"Exceeds current budget by ₹{deficit:,}.")

    # Water viability
    if water_deficit_mm == 0:
        pros.append("Natural rainfall covers the complete water requirement.")
    elif water_deficit_mm > 300:
        cons.append(f"Severe water deficit ({water_deficit_mm:.0f} mm); requires substantial external irrigation.")
    else:
        pros.append(f"Moderate water deficit ({water_deficit_mm:.0f} mm); manageable with standard irrigation.")

    # Market risk
    if market_risk == "LOW":
        pros.append("Historical wholesale market prices remain steady with low volatility.")
    elif market_risk == "HIGH":
        cons.append("High price fluctuations in wholesale markets; income may vary significantly.")

    why_this_crop = " ".join(pros)
    why_not_this_crop = " ".join(cons) if cons else "No major constraints identified under normal conditions."

    return why_this_crop, why_not_this_crop


def run_scenario_testing(crop_info, acres, base_cost, rainfall_mm):
    """
    Simulates What-If scenarios:
    1. Scenario A: Drought condition (-20% rainfall)
    2. Scenario B: Market price drop (-15% wholesale price)
    """
    yield_quintals = crop_info["expected_yield_quintal_per_acre"] * acres
    base_price = crop_info["market_price_per_quintal"]

    # Scenario A: Drought (-20% rain)
    drought_rainfall = rainfall_mm * 0.80
    drought_deficit_mm = max(0.0, crop_info["water_requirement_mm"] - drought_rainfall)
    drought_risk = "HIGH" if drought_deficit_mm > 300 else "MEDIUM"

    # Scenario B: Market price slump (-15%)
    slump_price = base_price * 0.85
    slump_revenue = round(yield_quintals * slump_price)
    slump_net_profit = slump_revenue - base_cost

    return {
        "drought_scenario": {
            "rainfall_drop": "-20%",
            "extra_irrigation_needed": f"{round(drought_deficit_mm * acres * 4046.86):,} L",
            "risk_impact": drought_risk
        },
        "market_slump_scenario": {
            "price_drop": "-15%",
            "projected_revenue": f"₹{slump_revenue:,}",
            "net_profit": f"₹{slump_net_profit:,}"
        }
    }


def evaluate_crop_plan(soil_inputs, farm_profile):
    """
    Main evaluation pipeline connecting ML, agronomy, economics, and hydrology.
    """
    features = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]
    input_df = pd.DataFrame([soil_inputs])[features]

    # Predict class probabilities
    probabilities = model.predict_proba(input_df)[0]
    crops = model.classes_
    top_3_indices = np.argsort(probabilities)[::-1][:3]

    acres = float(farm_profile.get("acres", 1.0))
    budget = float(farm_profile.get("budget", 50000.0))
    rainfall_mm = float(soil_inputs.get("rainfall", 0.0))
    seasonal_rainfall_mm = float(farm_profile.get("seasonal_rainfall_mm", rainfall_mm))

    results = []

    for rank, idx in enumerate(top_3_indices, start=1):
        crop_key = crops[idx].lower()
        suitability = probabilities[idx] * 100
        crop_info = CROP_DATABASE.get(crop_key, DEFAULT_METRICS)

        # 1. Economics
        cost_breakdown, total_cost = compute_detailed_costs(crop_info, acres)
        expected_yield = crop_info["expected_yield_quintal_per_acre"] * acres
        base_revenue = expected_yield * crop_info["market_price_per_quintal"]
        min_rev = round(base_revenue * 0.85)
        max_rev = round(base_revenue * 1.15)
        net_profit_est = round(base_revenue - total_cost)

        # 2. Water
        water_data = compute_water_balance(crop_info, acres, seasonal_rainfall_mm)

        # 3. Risk Levels
        cost_risk = "HIGH" if total_cost > budget else ("MEDIUM" if total_cost > (0.85 * budget) else "LOW")
        water_risk = "HIGH" if water_data["deficit_mm"] > 300 else ("MEDIUM" if water_data["deficit_mm"] > 100 else "LOW")
        market_risk = crop_info["market_risk"].upper()

        risk_scores = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
        composite_risk_val = (risk_scores[cost_risk] + risk_scores[water_risk] + risk_scores[market_risk]) / 3.0
        overall_risk = "HIGH" if composite_risk_val >= 2.3 else ("MEDIUM" if composite_risk_val >= 1.6 else "LOW")

        # 4. Decision Feasibility Score (0 to 100)
        budget_ratio = min(1.0, budget / max(1.0, total_cost))
        water_factor = 0.7 if water_risk == "HIGH" else 1.0
        final_score = round((suitability * 0.5) + (budget_ratio * 30.0) + (water_factor * 20.0), 1)

        # 5. Explanations
        why_this, why_not = generate_rationales(
            crop_key, suitability, total_cost, budget, water_data["deficit_mm"], market_risk
        )

        # 6. Scenarios
        scenarios = run_scenario_testing(crop_info, acres, total_cost, seasonal_rainfall_mm)

        results.append({
            "rank": rank,
            "crop": crop_key.capitalize(),
            "final_score": final_score,
            "suitability_pct": round(suitability, 2),
            "sowing_window": crop_info["sowing_window"],
            "economics": {
                "total_cost": total_cost,
                "cost_breakdown": cost_breakdown,
                "cost_risk": cost_risk,
                "projected_revenue_range": f"₹{min_rev:,} – ₹{max_rev:,}",
                "estimated_net_profit": f"₹{net_profit_est:,}"
            },
            "water": {
                "total_water_liters": water_data["total_water_liters"],
                "irrigation_deficit_liters": water_data["irrigation_liters"],
                "water_risk": water_risk
            },
            "risk": {
                "overall_risk": overall_risk,
                "cost_risk": cost_risk,
                "water_risk": water_risk,
                "market_risk": market_risk
            },
            "explanations": {
                "why_this_crop": why_this,
                "potential_hazards": why_not
            },
            "scenarios": scenarios
        })

    # Sort top options by the comprehensive decision score rather than ML probability alone
    results.sort(key=lambda x: x["final_score"], reverse=True)
    for i, item in enumerate(results, start=1):
        item["rank"] = i

    return results


# ------------------------------------------------
# 3. Main execution test
# ------------------------------------------------

if __name__ == "__main__":
    sample_soil = {
        "N": 90,
        "P": 42,
        "K": 43,
        "temperature": 20.87,
        "humidity": 82.00,
        "ph": 6.50,
        "rainfall": 202.93
    }

    sample_farm = {
        "acres": 2.5,
        "budget": 40000.0
    }

    print("\n=======================================================")
    print("      SMARTCROP AI: FARM DECISION SUPPORT SYSTEM       ")
    print("=======================================================")

    evaluations = evaluate_crop_plan(sample_soil, sample_farm)

    for item in evaluations:
        print(f"\nRANK {item['rank']}: {item['crop']} (Overall Decision Score: {item['final_score']}/100)")
        print(f"  • ML Suitability Score : {item['suitability_pct']}%")
        print(f"  • Optimal Sowing Window: {item['sowing_window']}")
        print(f"  • Financial Overview   : Cost ₹{item['economics']['total_cost']:,} | Net Profit ~{item['economics']['estimated_net_profit']}")
        print(f"    - Cost Breakdown     : Seeds: ₹{item['economics']['cost_breakdown']['seeds']:,} | Fertilizer: ₹{item['economics']['cost_breakdown']['fertilizer']:,} | Labor: ₹{item['economics']['cost_breakdown']['labor']:,}")
        print(f"  • Water Balance        : Total: {item['water']['total_water_liters']:,} L | Deficit: {item['water']['irrigation_deficit_liters']:,} L (Risk: {item['water']['water_risk']})")
        print(f"  • Risk Breakdown       : Overall: {item['risk']['overall_risk']} | Cost: {item['risk']['cost_risk']} | Market: {item['risk']['market_risk']}")
        print(f"  • Why Recommend        : {item['explanations']['why_this_crop']}")
        print(f"  • Watch-outs / Hazards : {item['explanations']['potential_hazards']}")
        print(f"  • Scenario Analysis    : Drought (-20% Rain) Risk -> {item['scenarios']['drought_scenario']['risk_impact']} | Slump (-15% Price) Net -> {item['scenarios']['market_slump_scenario']['net_profit']}")

    print("\n=======================================================")
