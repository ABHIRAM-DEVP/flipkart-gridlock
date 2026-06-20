package com.astram.controller;

import com.astram.entity.PlanRequest;
import com.astram.repository.PlanRequestRepository;
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
@RequestMapping("/api/plans")
public class PlanController {

    private final AstramClientService astramClientService;
    private final PlanRequestRepository repository;
    private final ObjectMapper objectMapper;

    public PlanController(AstramClientService astramClientService, PlanRequestRepository repository, ObjectMapper objectMapper) {
        this.astramClientService = astramClientService;
        this.repository = repository;
        this.objectMapper = objectMapper;
    }

    @PostMapping
    public Mono<PlanRequest> plan(@RequestBody String requestPayload) {
        return astramClientService.post("/plan", requestPayload)
                .map(responsePayload -> {
                    PlanRequest req = new PlanRequest();
                    req.setId(UUID.randomUUID());
                    req.setRequestedAt(ZonedDateTime.now());
                    req.setRequestPayload(requestPayload);
                    req.setResponsePayload(responsePayload);
                    
                    try {
                        JsonNode reqNode = objectMapper.readTree(requestPayload);
                        if (reqNode.has("budget")) {
                            req.setBudget(reqNode.get("budget").asInt());
                        } else {
                            req.setBudget(50); // Default per spec
                        }
                        
                        if (reqNode.has("events") && reqNode.get("events").isArray()) {
                            req.setEventCount(reqNode.get("events").size());
                        } else if (reqNode.isArray()) {
                            req.setEventCount(reqNode.size());
                        } else {
                            req.setEventCount(0);
                        }
                    } catch (Exception e) {
                        req.setBudget(0);
                        req.setEventCount(0);
                    }
                    
                    return repository.save(req);
                });
    }

    @GetMapping
    public Page<PlanRequest> getHistory(@PageableDefault(sort = "requestedAt", direction = Sort.Direction.DESC) Pageable pageable) {
        return repository.findAll(pageable);
    }

    @GetMapping("/{id}")
    public PlanRequest getPlan(@PathVariable UUID id) {
        return repository.findById(id).orElseThrow(() -> new RuntimeException("Not Found"));
    }
}
