package com.astram.exception;

import com.astram.dto.AstramErrorResponse;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.bind.annotation.ExceptionHandler;

import java.net.ConnectException;

@ControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(AstramClientException.class)
    public ResponseEntity<AstramErrorResponse> handleAstramClientException(AstramClientException ex) {
        AstramErrorResponse response = new AstramErrorResponse(
                ex.getMessage(),
                ex.getDetails(),
                ex.getStatusCode()
        );
        return ResponseEntity.status(resolveStatus(ex.getStatusCode())).body(response);
    }

    @ExceptionHandler(ConnectException.class)
    public ResponseEntity<AstramErrorResponse> handleConnectException(ConnectException ex) {
        AstramErrorResponse response = new AstramErrorResponse(
                "Service Unavailable",
                "Astram prediction service is unreachable.",
                503
        );
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(response);
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<AstramErrorResponse> handleGenericException(Exception ex) {
        AstramErrorResponse response = new AstramErrorResponse(
                "Internal Server Error",
                ex.getMessage(),
                500
        );
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(response);
    }

    private HttpStatus resolveStatus(int statusCode) {
        HttpStatus status = HttpStatus.resolve(statusCode);
        return status != null ? status : HttpStatus.INTERNAL_SERVER_ERROR;
    }
}
