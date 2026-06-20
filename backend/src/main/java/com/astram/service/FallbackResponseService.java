package com.astram.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.core.io.buffer.DataBufferFactory;
import org.springframework.core.io.buffer.DefaultDataBufferFactory;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@Service
public class FallbackResponseService {

    private static final DataBufferFactory BUFFER_FACTORY = new DefaultDataBufferFactory();

    private final ObjectMapper objectMapper;
    private final Path artifactDir;

    public FallbackResponseService(
            ObjectMapper objectMapper,
            @Value("${astram.fallback.dir:../artifacts}") String artifactDir
    ) {
        this.objectMapper = objectMapper;
        this.artifactDir = Paths.get(artifactDir).toAbsolutePath().normalize();
    }

    public Mono<String> fallbackGet(String uri) {
        return Mono.fromSupplier(() -> {
            if (uri.startsWith("/weights")) {
                return serialize(featureWeightsList());
            }
            if (uri.equals("/metrics")) {
                return serialize(metricsSnapshot());
            }
            if (uri.equals("/graphs")) {
                return serialize(graphsSnapshot());
            }
            if (uri.equals("/hotspots")) {
                return serialize(bundleList("train_hotspots"));
            }
            if (uri.equals("/dbscan-hotspots")) {
                return serialize(bundleList("dbscan_hotspots"));
            }
            if (uri.equals("/feedback/summary")) {
                return serialize(Map.of("count", 0, "note", "Fallback active. No live feedback service available."));
            }
            if (uri.equals("/report.txt")) {
                return readText("report.txt", "ASTRAM fallback report unavailable.");
            }
            if (uri.equals("/graph-files")) {
                return serialize(graphFiles());
            }
            if (uri.startsWith("/graph/")) {
                return serialize(Map.of("error", "graph fallback is handled as a binary stream"));
            }
            if (uri.equals("/app-data")) {
                return readJson("app_data.json", Map.of("metrics", metricsSnapshot()));
            }
            return serialize(Map.of("error", "fallback not available for " + uri));
        });
    }

    public Mono<String> fallbackPost(String uri, String body) {
        return Mono.fromSupplier(() -> {
            try {
                JsonNode request = objectMapper.readTree(body == null || body.isBlank() ? "{}" : body);
                if (uri.equals("/predict")) {
                    return serialize(predictFallback(request));
                }
                if (uri.equals("/plan")) {
                    return serialize(planFallback(request));
                }
                if (uri.equals("/planned-impact")) {
                    return serialize(plannedImpactFallback(request));
                }
            } catch (Exception ignored) {
                // Fall through to generic fallback.
            }
            return serialize(Map.of(
                    "error", "astram service unavailable",
                    "details", "Using backend fallback from cached artifacts",
                    "fallback_active", true
            ));
        });
    }

    public Flux<DataBuffer> fallbackStream(String uri) {
        if (!uri.startsWith("/graph/")) {
            return Flux.empty();
        }
        String graphName = uri.substring("/graph/".length()).trim();
        if (graphName.isEmpty()) {
            return Flux.empty();
        }
        Path graphPath = artifactDir.resolve("graphs").resolve(graphName).normalize();
        if (!graphPath.startsWith(artifactDir) || !Files.exists(graphPath)) {
            return Flux.empty();
        }
        try {
            byte[] bytes = Files.readAllBytes(graphPath);
            return Flux.just(BUFFER_FACTORY.wrap(bytes));
        } catch (IOException e) {
            return Flux.empty();
        }
    }

    private Map<String, Object> metricsSnapshot() {
        Map<String, Object> metrics = readJsonObject("summary.json");
        if (metrics.containsKey("metrics")) {
            Object nested = metrics.get("metrics");
            if (nested instanceof Map<?, ?> nestedMap) {
                return new LinkedHashMap<>((Map<String, Object>) nestedMap);
            }
        }
        Map<String, Object> fallback = readJsonObject("app_data.json");
        Object metricsObj = fallback.get("metrics");
        if (metricsObj instanceof Map<?, ?> m) {
            return new LinkedHashMap<>((Map<String, Object>) m);
        }
        return new LinkedHashMap<>(Map.of("status", "fallback", "note", "cached metrics unavailable"));
    }

    private Map<String, Object> graphsSnapshot() {
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("metrics", metricsSnapshot());
        data.put("hotspots", bundleList("train_hotspots"));
        data.put("dbscan_hotspots", bundleList("dbscan_hotspots"));
        data.put("feature_weights", featureWeightsList());
        data.put("graph_paths", readJsonObject("summary.json").getOrDefault("graph_paths", Map.of()));
        return data;
    }

    private List<Map<String, Object>> featureWeightsList() {
        Map<String, Object> bundle = readJsonObject("bundle.json");
        Object weights = bundle.get("feature_weights");
        if (weights instanceof Map<?, ?> map) {
            Object items = map.get("duration_feature_importance");
            if (items instanceof List<?> list) {
                List<Map<String, Object>> rows = new ArrayList<>();
                for (Object item : list) {
                    if (item instanceof Map<?, ?> itemMap) {
                        rows.add(new LinkedHashMap<>((Map<String, Object>) itemMap));
                    }
                }
                return rows;
            }
        }
        List<Map<String, Object>> top = new ArrayList<>();
        Object featureImportance = bundle.get("feature_importance");
        if (featureImportance instanceof List<?> list) {
            for (Object item : list) {
                if (item instanceof Map<?, ?> map) {
                    top.add(new LinkedHashMap<>((Map<String, Object>) map));
                }
            }
        }
        return top;
    }

    private List<Map<String, Object>> graphFiles() {
        Path graphDir = artifactDir.resolve("graphs");
        if (!Files.isDirectory(graphDir)) {
            return List.of();
        }
        try {
            return Files.list(graphDir)
                    .filter(path -> Files.isRegularFile(path) && path.getFileName().toString().endsWith(".png"))
                    .sorted()
                    .map(path -> {
                        Map<String, Object> entry = new LinkedHashMap<>();
                        entry.put("name", path.getFileName().toString());
                        entry.put("path", path.toString());
                        try {
                            entry.put("size", Files.size(path));
                        } catch (IOException e) {
                            entry.put("size", 0);
                        }
                        return entry;
                    })
                    .toList();
        } catch (IOException e) {
            return List.of();
        }
    }

    private List<Map<String, Object>> bundleList(String key) {
        Map<String, Object> bundle = readJsonObject("bundle.json");
        Object value = bundle.get(key);
        if (value instanceof List<?> list) {
            List<Map<String, Object>> rows = new ArrayList<>();
            for (Object item : list) {
                if (item instanceof Map<?, ?> map) {
                    rows.add(new LinkedHashMap<>((Map<String, Object>) map));
                }
            }
            return rows;
        }
        return List.of();
    }

    private Map<String, Object> predictFallback(JsonNode event) {
        double duration = 60.0;
        Map<String, Object> metrics = metricsSnapshot();
        duration = asDouble(metrics.getOrDefault("global_median", duration), duration);
        duration += severityBoost(text(event, "priority"));
        duration += closureBoost(text(event, "requires_road_closure"));
        duration += causeBoost(text(event, "event_cause"));
        duration += event.hasNonNull("event_type") && "planned".equalsIgnoreCase(text(event, "event_type")) ? 15.0 : 0.0;
        duration = Math.max(5.0, Math.min(480.0, duration));

        String severity = severityFromDuration(duration);
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("predicted_duration_min", round(duration));
        response.put("predicted_severity", severity);
        response.put("prediction_interval_min", Map.of(
                "p10", round(Math.max(0.0, duration - 18.0)),
                "p90", round(Math.min(480.0, duration + 35.0))
        ));
        response.put("resource_plan", resourcePlan(duration, severity, event));
        response.put("planned_impact", "planned".equalsIgnoreCase(text(event, "event_type")) ? plannedImpactFallback(event) : null);
        response.put("fallback_active", true);
        return response;
    }

    private Map<String, Object> planFallback(JsonNode payload) {
        List<JsonNode> events = new ArrayList<>();
        if (payload.isArray()) {
            payload.forEach(events::add);
        } else if (payload.has("events") && payload.get("events").isArray()) {
            payload.get("events").forEach(events::add);
        }
        int budget = payload.has("budget") ? payload.get("budget").asInt(50) : 50;
        List<Map<String, Object>> scored = new ArrayList<>();
        for (JsonNode event : events) {
            Map<String, Object> prediction = predictFallback(event);
            prediction.put("event", objectMapper.convertValue(event, Map.class));
            scored.add(prediction);
        }
        return Map.of(
                "scored_events", scored,
                "allocation", Map.of(
                        "status", "fallback",
                        "remaining_personnel", Math.max(0, budget - scored.size()),
                        "note", "Fallback allocation uses cached heuristic scoring"
                ),
                "fallback_active", true
        );
    }

    private Map<String, Object> plannedImpactFallback(JsonNode event) {
        String corridor = text(event, "corridor");
        String cause = text(event, "event_cause");
        String hour = String.valueOf(extractHour(text(event, "start_datetime")));
        return Map.of(
                "planned_key", cause + "|" + corridor + "|" + hour,
                "baseline_unplanned_rate", 0.0,
                "spillover_events_per_planned_event", 0.0,
                "impact_multiplier", 1.0,
                "compounding_risk_score", 0.0,
                "recommend_preposition_hours_before", 3,
                "fallback_active", true
        );
    }

    private Map<String, Object> resourcePlan(double duration, String severity, JsonNode event) {
        int manpower = switch (severity) {
            case "critical" -> 6;
            case "high" -> 4;
            case "medium" -> 2;
            default -> 1;
        };
        int barricades = switch (severity) {
            case "critical" -> 4;
            case "high" -> 2;
            case "medium" -> 1;
            default -> 0;
        };
        if (truthy(text(event, "requires_road_closure"))) {
            barricades += 2;
        }
        return Map.of(
                "predicted_duration_min", round(duration),
                "severity_tier", severity,
                "manpower", manpower,
                "barricades", barricades,
                "diversion", "Fallback mode: use local diversion and on-ground control.",
                "risk_score", round(Math.min(100.0, duration / 4.0 + manpower * 8.0))
        );
    }

    private int extractHour(String startDatetime) {
        if (startDatetime == null || startDatetime.isBlank()) {
            return 0;
        }
        try {
            String[] parts = startDatetime.split(" ");
            if (parts.length > 1) {
                String[] timeParts = parts[1].split(":");
                return Integer.parseInt(timeParts[0]);
            }
        } catch (Exception ignored) {
        }
        return 0;
    }

    private double severityBoost(String priority) {
        return switch (priority.toLowerCase(Locale.ROOT)) {
            case "critical" -> 55.0;
            case "high" -> 30.0;
            case "medium" -> 10.0;
            default -> 0.0;
        };
    }

    private double closureBoost(String truth) {
        return truthy(truth) ? 20.0 : 0.0;
    }

    private double causeBoost(String cause) {
        return switch (cause.toLowerCase(Locale.ROOT)) {
            case "public_event", "procession", "vip_movement", "protest" -> 25.0;
            case "water_logging", "tree_fall" -> 15.0;
            case "construction", "road_conditions", "pot_holes", "debris" -> 10.0;
            case "vehicle_breakdown", "accident" -> 18.0;
            default -> 0.0;
        };
    }

    private String severityFromDuration(double duration) {
        if (duration < 30.0) {
            return "low";
        }
        if (duration < 120.0) {
            return "medium";
        }
        if (duration < 480.0) {
            return "high";
        }
        return "critical";
    }

    private boolean truthy(String value) {
        if (value == null) {
            return false;
        }
        String normalized = value.trim().toLowerCase(Locale.ROOT);
        return normalized.equals("true") || normalized.equals("1") || normalized.equals("yes") || normalized.equals("y");
    }

    private String text(JsonNode node, String field) {
        if (node == null || !node.has(field) || node.get(field).isNull()) {
            return "";
        }
        return node.get(field).asText("");
    }

    private double asDouble(Object value, double fallback) {
        if (value instanceof Number number) {
            return number.doubleValue();
        }
        try {
            return Double.parseDouble(String.valueOf(value));
        } catch (Exception e) {
            return fallback;
        }
    }

    private double round(double value) {
        return Math.round(value * 100.0) / 100.0;
    }

    private Map<String, Object> readJsonObject(String filename) {
        Path path = artifactDir.resolve(filename).normalize();
        if (!path.startsWith(artifactDir) || !Files.exists(path)) {
            return new LinkedHashMap<>();
        }
        try {
            JsonNode node = objectMapper.readTree(Files.readString(path));
            return objectMapper.convertValue(node, LinkedHashMap.class);
        } catch (IOException e) {
            return new LinkedHashMap<>();
        }
    }

    private String readJson(String filename, Object fallback) {
        return serialize(readJsonObject(filename).isEmpty() ? fallback : readJsonObject(filename));
    }

    private String readText(String filename, String fallback) {
        Path path = artifactDir.resolve(filename).normalize();
        if (!path.startsWith(artifactDir) || !Files.exists(path)) {
            return fallback;
        }
        try {
            return Files.readString(path);
        } catch (IOException e) {
            return fallback;
        }
    }

    private String serialize(Object value) {
        try {
            return objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(value);
        } catch (Exception e) {
            return "{\"error\":\"fallback serialization failed\"}";
        }
    }
}
