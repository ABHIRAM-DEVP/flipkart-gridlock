package com.astram.controller;

import com.astram.service.AstramClientService;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@RestController
@RequestMapping("/api/reports")
public class ReportController {

    private final AstramClientService astramClientService;

    public ReportController(AstramClientService astramClientService) {
        this.astramClientService = astramClientService;
    }

    @GetMapping(value = "/text", produces = MediaType.TEXT_PLAIN_VALUE)
    public Mono<String> getReportText() {
        return astramClientService.get("/report.txt");
    }

    @GetMapping("/graph-files")
    public Mono<String> getGraphFiles() {
        return astramClientService.get("/graph-files");
    }

    @GetMapping(value = "/graph/{name}", produces = MediaType.IMAGE_PNG_VALUE)
    public ResponseEntity<Flux<DataBuffer>> getGraphImage(@PathVariable String name) {
        // Basic validation for filename to prevent directory traversal
        if (name == null || name.contains("..") || name.contains("/") || name.contains("\\")) {
            return ResponseEntity.badRequest().build();
        }
        
        Flux<DataBuffer> imageStream = astramClientService.getStream("/graph/" + name);
        return ResponseEntity.ok()
                .contentType(MediaType.IMAGE_PNG)
                .body(imageStream);
    }
}
