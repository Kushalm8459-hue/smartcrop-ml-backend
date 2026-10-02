"""
SmartCrop AI: Decision Engine Test Harness
Simulates an Indian farmer profile with soil test report, land constraints,
and water access to generate complete agricultural decision intelligence.
"""

from decision_engine import evaluate_crop_plan

# Simulate Farmer Input (e.g., Vidarbha/Marathwada farmer)
farmer_soil_and_climate = {
    "N": 90,
    "P": 42,
    "K": 43,
    "temperature": 24.5,
    "humidity": 78.0,
    "ph": 6.8,
    "rainfall": 185.0
}

farmer_profile = {
    "acres": 2.5,
    "budget": 45000.0,
    "irrigation_source": "Borewell (Limited)",
    "location": "Maharashtra, India"
}

print("\n" + "=" * 75)
print("      SMARTCROP AI: FARM DECISION SUPPORT SYSTEM REPORT      ")
print("=" * 75)

print("\n--- FARMER & LAND PROFILE ---")
print(f"• Location              : {farmer_profile['location']}")
print(f"• Farm Cultivation Area : {farmer_profile['acres']} Acres")
print(f"• Available Budget      : ₹{farmer_profile['budget']:,.0f}")
print(f"• Irrigation Source     : {farmer_profile['irrigation_source']}")
print(f"• Soil & Weather Inputs : N={farmer_soil_and_climate['N']}, P={farmer_soil_and_climate['P']}, K={farmer_soil_and_climate['K']}, pH={farmer_soil_and_climate['ph']}, Rain={farmer_soil_and_climate['rainfall']} mm")

# Run Master Decision Pipeline
reports = evaluate_crop_plan(farmer_soil_and_climate, farmer_profile)

for crop in reports:
    print("\n" + "#" * 75)
    print(f"RANK {crop['rank']}: {crop['crop'].upper()}  (Overall Feasibility Score: {crop['overall_decision_score']}/100)")
    print("#" * 75)

    print(f"\n[1] AGRONOMIC SUITABILITY & TIMING")
    print(f"  • ML Suitability Match  : {crop['ml_suitability_score']}%")
    print(f"  • Optimal Sowing Window : {crop['calendar']['sowing_window']}")
    print(f"  • Expected Harvest Time : {crop['calendar']['harvest_window']}")
    print(f"  • Season Category       : {crop['calendar']['season']}")

    print(f"\n[2] FINANCIAL & COST BREAKDOWN (Scaled for {farmer_profile['acres']} Acres)")
    print(f"  • Total Cultivation Cost: ₹{crop['economics']['total_cost']:,}")
    print(f"    - Seeds Cost          : ₹{crop['economics']['cost_breakdown']['seeds']:,}")
    print(f"    - Fertilizer Cost     : ₹{crop['economics']['cost_breakdown']['fertilizer']:,}")
    print(f"    - Labor Cost          : ₹{crop['economics']['cost_breakdown']['labor']:,}")
    print(f"    - Machinery / Fuel    : ₹{crop['economics']['cost_breakdown']['machinery']:,}")
    print(f"    - Supplemental Water  : ₹{crop['economics']['cost_breakdown']['irrigation']:,}")
    print(f"    - Plant Protection    : ₹{crop['economics']['cost_breakdown']['pesticides']:,}")

    print(f"\n[3] MARKET REVENUE & ROI PROJECTION")
    print(f"  • Expected Yield        : {crop['market_intelligence']['expected_yield_quintals']} Quintals")
    print(f"  • Benchmark Mandi Price : ₹{crop['market_intelligence']['benchmark_price_per_quintal']:,} / Quintal")
    print(f"  • Expected Gross Revenue: ₹{crop['economics']['expected_gross_revenue']:,} (Range: {crop['economics']['revenue_range']})")
    print(f"  • Expected Net Profit   : ₹{crop['economics']['expected_net_profit']:,} (ROI: {crop['economics']['projected_roi']})")
    print(f"  • Selling Channels      : {', '.join(crop['market_intelligence']['recommended_selling_channels'])}")

    print(f"\n[4] WATER BALANCE & IRRIGATION REQUIREMENT")
    print(f"  • Gross Seasonal Need   : {crop['water']['total_water_liters']:,} Litres")
    print(f"  • Irrigation Deficit    : {crop['water']['supplemental_irrigation_liters']:,} Litres ({crop['water']['irrigation_deficit_mm']} mm deficit)")
    print(f"  • Critical Water Stages : {', '.join(crop['water']['critical_growth_stages'])}")

    print(f"\n[5] MULTI-FACTOR RISK AUDIT")
    print(f"  • Overall Composite Risk: {crop['risk']['overall_risk']}")
    print(f"  • Financial Risk        : {crop['risk']['financial_risk']} -> {crop['risk']['financial_risk_reason']}")
    print(f"  • Hydrological Risk     : {crop['risk']['water_risk']} -> {crop['risk']['water_risk_reason']}")
    print(f"  • Market Volatility     : {crop['risk']['market_volatility_risk']} -> {crop['risk']['market_volatility_risk_reason']}")
    print(f"  • Disease Vulnerability : {crop['risk']['disease_vulnerability']}")

    print(f"\n[6] SCENARIO TESTING (WHAT-IF SENSITIVITY)")
    print(f"  • Drought Shock (-25% Rain)   : Requires {crop['scenario_testing']['drought_scenario']['required_irrigation_liters']} extra irrigation. Threat Level: {crop['scenario_testing']['drought_scenario']['hydrological_risk']}")
    print(f"  • Market Slump (-20% Price)   : Stressed Net Profit -> {crop['scenario_testing']['market_slump_scenario']['stressed_net_profit']} ({crop['scenario_testing']['market_slump_scenario']['status']})")
    print(f"  • Favorable Monsoon Condition : Optimistic Net Profit -> ₹{crop['scenario_testing']['bumper_scenario']['optimistic_net_profit']}")

    print(f"\n[7] EXPLAINABILITY RATIONALES")
    print(f"  • Why This Crop?       : {crop['rationales']['why_this_crop']}")
    print(f"  • Potential Hazards    : {crop['rationales']['potential_hazards']}")

print("\n" + "=" * 75)
print("EVALUATION COMPLETE: All 7 SmartCrop Modules Successfully Executed.")
print("=" * 75 + "\n")