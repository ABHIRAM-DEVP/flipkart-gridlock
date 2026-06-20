package com.astram.service;

import com.astram.entity.MetricsSnapshot;
import com.astram.repository.MetricsSnapshotRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.time.ZonedDateTime;
import java.util.UUID;

@Service
public class MetricsSnapshotService {

    private static final Logger logger = LoggerFactory.getLogger(MetricsSnapshotService.class);

    private final AstramClientService astramClientService;
    private final MetricsSnapshotRepository repository;

    public MetricsSnapshotService(AstramClientService astramClientService, MetricsSnapshotRepository repository) {
        this.astramClientService = astramClientService;
        this.repository = repository;
    }

    @Scheduled(fixedRateString = "600000") // 10 minutes
    public void fetchAndSaveMetrics() {
        try {
            astramClientService.get("/metrics").subscribe(
                metricsPayload -> {
                    MetricsSnapshot snapshot = new MetricsSnapshot();
                    snapshot.setId(UUID.randomUUID());
                    snapshot.setCapturedAt(ZonedDateTime.now());
                    snapshot.setMetricsPayload(metricsPayload);
                    repository.save(snapshot);
                    logger.info("Successfully captured metrics snapshot");
                },
                error -> logger.warn("Failed to capture metrics snapshot: {}", error.getMessage())
            );
        } catch (Exception e) {
            logger.error("Error scheduling metrics fetch", e);
        }
    }

    public void triggerOnDemandSnapshotIfOld() {
        MetricsSnapshot latest = repository.findTopByOrderByCapturedAtDesc();
        if (latest == null || latest.getCapturedAt().isBefore(ZonedDateTime.now().minusMinutes(10))) {
            fetchAndSaveMetrics();
        }
    }
}
