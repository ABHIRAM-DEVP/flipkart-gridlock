package com.astram.controller;

import com.astram.entity.PredictionRequest;
import com.astram.repository.PredictionRequestRepository;
import com.astram.service.AstramClientService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.data.web.PageableDefault;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Mono;

import java.time.ZonedDateTime;
import java.util.UUID;

@RestController
@RequestMapping("/api/predictions")
public class PredictionController {

    private final AstramClientService astramClientService;
    private final PredictionRequestRepository repository;
    private final ObjectMapper objectMapper;

    public PredictionController(AstramClientService astramClientService, PredictionRequestRepository repository, ObjectMapper objectMapper) {
        this.astramClientService = astramClientService;
        this.repository = repository;
        this.objectMapper = objectMapper;
    }

    @PostMapping
    public Mono<PredictionRequest> predict(@RequestBody String requestPayload) {
        return astramClientService.post("/predict", requestPayload)
                .map(responsePayload -> {
                    PredictionRequest req = new PredictionRequest();
                    req.setId(UUID.randomUUID());
                    req.setRequestedAt(ZonedDateTime.now());
                    req.setRequestPayload(requestPayload);
                    req.setResponsePayload(responsePayload);
                    
                    try {
                        JsonNode resNode = objectMapper.readTree(responsePayload);
                        if (resNode.has("predicted_duration_min")) {
                            req.setDurationEstimate(resNode.get("predicted_duration_min").asDouble());
                        } else if (resNode.has("duration_estimate")) {
                            req.setDurationEstimate(resNode.get("duration_estimate").asDouble());
                        }
                        if (resNode.has("predicted_severity")) {
                            req.setSeverityLabel(resNode.get("predicted_severity").asText());
                        } else if (resNode.has("severity_label")) {
                            req.setSeverityLabel(resNode.get("severity_label").asText());
                        }
                    } catch (Exception e) {
                        // Ignore parsing errors for extraction
                    }
                    
                    return repository.save(req);
                });
    }

    @GetMapping
    public Page<PredictionRequest> getHistory(@PageableDefault(sort = "requestedAt", direction = Sort.Direction.DESC) Pageable pageable) {
        return repository.findAll(pageable);
    }

    @GetMapping("/{id}")
    public PredictionRequest getPrediction(@PathVariable UUID id) {
        return repository.findById(id).orElseThrow(() -> new RuntimeException("Not Found"));
    }
}
