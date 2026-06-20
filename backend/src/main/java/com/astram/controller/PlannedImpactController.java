package com.astram.controller;

import com.astram.entity.PlannedImpactRequest;
import com.astram.repository.PlannedImpactRequestRepository;
import com.astram.service.AstramClientService;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.data.web.PageableDefault;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Mono;

import java.time.ZonedDateTime;
import java.util.UUID;

@RestController
@RequestMapping("/api/planned-impact")
public class PlannedImpactController {

    private final AstramClientService astramClientService;
    private final PlannedImpactRequestRepository repository;

    public PlannedImpactController(AstramClientService astramClientService, PlannedImpactRequestRepository repository) {
        this.astramClientService = astramClientService;
        this.repository = repository;
    }

    @PostMapping
    public Mono<PlannedImpactRequest> plannedImpact(@RequestBody String requestPayload) {
        return astramClientService.post("/planned-impact", requestPayload)
                .map(responsePayload -> {
                    PlannedImpactRequest req = new PlannedImpactRequest();
                    req.setId(UUID.randomUUID());
                    req.setRequestedAt(ZonedDateTime.now());
                    req.setRequestPayload(requestPayload);
                    req.setResponsePayload(responsePayload);
                    return repository.save(req);
                });
    }

    @GetMapping
    public Page<PlannedImpactRequest> getHistory(@PageableDefault(sort = "requestedAt", direction = Sort.Direction.DESC) Pageable pageable) {
        return repository.findAll(pageable);
    }
}
