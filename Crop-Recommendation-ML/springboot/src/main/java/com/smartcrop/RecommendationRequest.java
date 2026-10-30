package com.smartcrop;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

/** Request DTO matching the existing Python farmer recommendation API. */
public record RecommendationRequest(
        @NotNull @DecimalMin("2000") @DecimalMax("2200") Integer year,
        @NotNull @DecimalMin("0") @DecimalMax("300") Double N,
        @NotNull @DecimalMin("0") @DecimalMax("300") Double P,
        @NotNull @DecimalMin("0") @DecimalMax("300") Double K,
        @NotNull @DecimalMin("-10") @DecimalMax("60") Double temperature,
        @NotNull @DecimalMin("0") @DecimalMax("100") Double humidity,
        @NotNull @DecimalMin("0") @DecimalMax("14") Double ph,
        @NotNull @DecimalMin("0") @DecimalMax("300") Double rainfall,
        @NotNull @DecimalMin("0.000001") @DecimalMax("100000") Double acres,
        @NotNull @DecimalMin("20000") Double budget,
        @NotBlank @Size(min = 2, max = 80) @JsonProperty("irrigation_source") String irrigationSource,
        @NotBlank @Size(min = 2, max = 160) String location,
        @NotBlank @Size(min = 2, max = 80) @JsonProperty("soil_type") String soilType,
        @DecimalMin("0") @DecimalMax("2000") @JsonProperty("seasonal_rainfall_mm") Double seasonalRainfallMm) {
}
