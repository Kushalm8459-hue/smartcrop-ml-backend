package com.smartcrop;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.validation.Valid;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.Map;

@RestController
public class RecommendationController {
    private final PythonRecommendationClient pythonClient;

    public RecommendationController(PythonRecommendationClient pythonClient) {
        this.pythonClient = pythonClient;
    }

    @GetMapping("/api/health")
    public Map<String, String> health() {
        return Map.of("status", "UP", "service", "SmartCrop Spring Boot API");
    }

    @PostMapping("/api/v1/farmer/recommend")
    public JsonNode recommend(
            @Valid @RequestBody RecommendationRequest request,
            @RequestHeader(value = HttpHeaders.AUTHORIZATION, required = false) String authorization) {
        if (authorization == null || !authorization.startsWith("Bearer ")) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Please log in to continue.");
        }
        return pythonClient.recommend(request, authorization);
    }
}
