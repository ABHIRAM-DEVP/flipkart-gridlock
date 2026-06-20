package com.astram.repository;

import com.astram.entity.PlanRequest;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.UUID;

@Repository
public interface PlanRequestRepository extends JpaRepository<PlanRequest, UUID> {
}
