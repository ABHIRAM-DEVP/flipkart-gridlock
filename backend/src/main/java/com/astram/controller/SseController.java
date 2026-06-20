package com.astram.controller;

import com.astram.service.AstramClientService;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Flux;

@RestController
public class SseController {

    private final AstramClientService astramClientService;

    public SseController(AstramClientService astramClientService) {
        this.astramClientService = astramClientService;
    }

    @GetMapping(value = "/sse/live", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<DataBuffer> streamLiveFeed() {
        return astramClientService.getStream("/sse/live");
    }
}
