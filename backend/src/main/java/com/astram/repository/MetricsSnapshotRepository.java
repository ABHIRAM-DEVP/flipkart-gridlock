package com.astram.repository;

import com.astram.entity.MetricsSnapshot;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.UUID;

@Repository
public interface MetricsSnapshotRepository extends JpaRepository<MetricsSnapshot, UUID> {
    MetricsSnapshot findTopByOrderByCapturedAtDesc();
}
