package com.astram.controller;

import com.astram.service.AstramClientService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/health")
public class HealthController {

    private final AstramClientService astramClientService;

    public HealthController(AstramClientService astramClientService) {
        this.astramClientService = astramClientService;
    }

    @GetMapping
    public Mono<Map<String, String>> getHealth() {
        return astramClientService.get("/health")
                .map(response -> {
                    Map<String, String> status = new HashMap<>();
                    status.put("backend", "ok");
                    status.put("astramService", "ok");
                    return status;
                })
                .onErrorResume(e -> {
                    Map<String, String> status = new HashMap<>();
                    status.put("backend", "ok");
                    status.put("astramService", "unreachable");
                    return Mono.just(status);
                });
    }
}
