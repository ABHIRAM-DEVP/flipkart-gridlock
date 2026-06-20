package com.astram.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Data;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.ZonedDateTime;
import java.util.UUID;

@Entity
@Table(name = "metrics_snapshots")
@Data
public class MetricsSnapshot {

    @Id
    private UUID id;

    @Column(name = "captured_at")
    private ZonedDateTime capturedAt;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "metrics_payload", columnDefinition = "jsonb")
    private String metricsPayload;
}
