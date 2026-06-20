package com.astram.service;

import com.astram.exception.AstramClientException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.ClientResponse;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@Service
public class AstramClientService {

    private final WebClient webClient;
    private final ObjectMapper objectMapper;
    private final FallbackResponseService fallbackResponseService;

    public AstramClientService(WebClient webClient, ObjectMapper objectMapper, FallbackResponseService fallbackResponseService) {
        this.webClient = webClient;
        this.objectMapper = objectMapper;
        this.fallbackResponseService = fallbackResponseService;
    }

    public Mono<String> get(String uri) {
        return webClient.get()
                .uri(uri)
                .retrieve()
                .onStatus(status -> status.isError(), this::handleError)
                .bodyToMono(String.class)
                .onErrorMap(e -> {
                    if (e instanceof AstramClientException) return e;
                    return new AstramClientException("Failed to connect to Astram Service", e);
                })
                .onErrorResume(this::shouldFallback, e -> fallbackResponseService.fallbackGet(uri));
    }

    public Mono<String> post(String uri, String body) {
        return webClient.post()
                .uri(uri)
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(body)
                .retrieve()
                .onStatus(status -> status.isError(), this::handleError)
                .bodyToMono(String.class)
                .onErrorMap(e -> {
                    if (e instanceof AstramClientException) return e;
                    return new AstramClientException("Failed to connect to Astram Service", e);
                })
                .onErrorResume(this::shouldFallback, e -> fallbackResponseService.fallbackPost(uri, body));
    }

    public Flux<DataBuffer> getStream(String uri) {
        return webClient.get()
                .uri(uri)
                .retrieve()
                .onStatus(status -> status.isError(), this::handleError)
                .bodyToFlux(DataBuffer.class)
                .onErrorMap(e -> {
                    if (e instanceof AstramClientException) return e;
                    return new AstramClientException("Failed to connect to Astram Service", e);
                })
                .onErrorResume(this::shouldFallback, e -> fallbackResponseService.fallbackStream(uri));
    }

    private boolean shouldFallback(Throwable throwable) {
        if (throwable instanceof AstramClientException ex) {
            return ex.getStatusCode() == 503 || ex.getStatusCode() == 502 || ex.getCause() != null;
        }
        return true;
    }

    private Mono<Throwable> handleError(ClientResponse response) {
        return response.bodyToMono(String.class)
                .defaultIfEmpty("Unknown error")
                .flatMap(body -> {
                    String errorMessage = "Astram Service Error";
                    String details = body;
                    
                    try {
                        JsonNode jsonNode = objectMapper.readTree(body);
                        if (jsonNode.has("error")) {
                            errorMessage = jsonNode.get("error").asText();
                            details = jsonNode.toString();
                        }
                    } catch (Exception e) {
                        // Not JSON, body is plain text error
                    }
                    return Mono.error(new AstramClientException(errorMessage, response.statusCode().value(), details));
                });
    }
}
