package com.astram.repository;

import com.astram.entity.PlannedImpactRequest;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.UUID;

@Repository
public interface PlannedImpactRequestRepository extends JpaRepository<PlannedImpactRequest, UUID> {
}
