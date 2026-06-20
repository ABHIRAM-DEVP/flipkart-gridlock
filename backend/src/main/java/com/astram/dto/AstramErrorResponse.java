package com.astram.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class AstramErrorResponse {
    private String error;
    private String details;
    private int upstreamStatus;
}
