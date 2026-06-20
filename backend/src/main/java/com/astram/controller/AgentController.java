package com.astram.controller;

import com.astram.service.AstramClientService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

@RestController
@RequestMapping("/api/agent")
public class AgentController {

    private final AstramClientService astramClientService;

    public AgentController(AstramClientService astramClientService) {
        this.astramClientService = astramClientService;
    }

    @PostMapping("/run")
    public Mono<String> runWorkflow(@RequestBody(required = false) String payload) {
        String body = payload != null ? payload : "{}";
        return astramClientService.post("/agent/run", body);
    }
}
