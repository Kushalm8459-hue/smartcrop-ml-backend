package com.smartcrop;

import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClientResponseException;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.Map;

@RestControllerAdvice
public class ApiErrorHandler {
    private final ObjectMapper objectMapper;

    public ApiErrorHandler(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    @ExceptionHandler(RestClientResponseException.class)
    public ResponseEntity<Object> forwardPythonError(RestClientResponseException exception) {
        try {
            Object body = objectMapper.readValue(exception.getResponseBodyAsByteArray(), Object.class);
            if (body != null) {
                return ResponseEntity.status(exception.getStatusCode())
                        .header(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                        .body(body);
            }
        } catch (Exception ignored) {
            // Return a clear JSON error below if FastAPI did not send a JSON body.
        }
        return ResponseEntity.status(exception.getStatusCode())
                .contentType(MediaType.APPLICATION_JSON)
                .body(Map.of("detail", "The Python API returned HTTP " + exception.getStatusCode().value() + "."));
    }

    @ExceptionHandler(ResourceAccessException.class)
    public ResponseEntity<Map<String, String>> pythonUnavailable() {
        return ResponseEntity.status(503).body(Map.of(
                "detail", "The SmartCrop Python API is unavailable. Start FastAPI on port 8000."));
    }
}
