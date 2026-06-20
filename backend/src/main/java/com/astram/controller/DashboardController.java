package com.astram.controller;

import com.astram.service.AstramClientService;
import com.astram.service.MetricsSnapshotService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

@RestController
@RequestMapping("/api/dashboard")
public class DashboardController {

    private final AstramClientService astramClientService;
    private final MetricsSnapshotService metricsSnapshotService;

    public DashboardController(AstramClientService astramClientService, MetricsSnapshotService metricsSnapshotService) {
        this.astramClientService = astramClientService;
        this.metricsSnapshotService = metricsSnapshotService;
    }

    @GetMapping("/metrics")
    public Mono<String> getMetrics() {
        metricsSnapshotService.triggerOnDemandSnapshotIfOld();
        return astramClientService.get("/metrics");
    }

    @GetMapping("/graphs")
    public Mono<String> getGraphs() {
        return astramClientService.get("/graphs");
    }

    @GetMapping("/weights")
    public Mono<String> getWeights(@RequestParam(required = false) String kind, @RequestParam(required = false) Integer top) {
        String uri = "/weights";
        if (kind != null || top != null) {
            uri += "?";
            if (kind != null) uri += "kind=" + kind;
            if (kind != null && top != null) uri += "&";
            if (top != null) uri += "top=" + top;
        }
        return astramClientService.get(uri);
    }

    @GetMapping("/hotspots")
    public Mono<String> getHotspots() {
        return astramClientService.get("/hotspots");
    }

    @GetMapping("/dbscan-hotspots")
    public Mono<String> getDbscanHotspots() {
        return astramClientService.get("/dbscan-hotspots");
    }

    @GetMapping("/feedback-summary")
    public Mono<String> getFeedbackSummary() {
        return astramClientService.get("/feedback/summary");
    }
}
