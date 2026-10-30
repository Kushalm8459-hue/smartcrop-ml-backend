package com.smartcrop;

import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

/** Calls the existing SmartCrop FastAPI endpoint and forwards its report. */
@Service
public class PythonRecommendationClient {
    private final RestClient restClient;

    public PythonRecommendationClient(
            RestClient.Builder builder,
            @Value("${smartcrop.python-api-url:http://127.0.0.1:8000}") String pythonApiUrl) {
        this.restClient = builder
                .requestFactory(new SimpleClientHttpRequestFactory())
                .baseUrl(pythonApiUrl)
                .build();
    }

    public JsonNode recommend(RecommendationRequest request, String authorization) {
        return restClient.post()
                .uri("/api/v1/farmer/recommend")
                .header(HttpHeaders.AUTHORIZATION, authorization)
                .body(request)
                .retrieve()
                .body(JsonNode.class);
    }
}
