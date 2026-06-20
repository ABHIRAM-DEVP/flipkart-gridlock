package com.astram.exception;

import lombok.Getter;
import org.springframework.http.HttpStatus;

@Getter
public class AstramClientException extends RuntimeException {
    private final int statusCode;
    private final String details;

    public AstramClientException(String message, int statusCode, String details) {
        super(message);
        this.statusCode = statusCode;
        this.details = details;
    }

    public AstramClientException(String message, Throwable cause) {
        super(message, cause);
        this.statusCode = HttpStatus.SERVICE_UNAVAILABLE.value();
        this.details = "Astram prediction service is unreachable.";
    }
}
