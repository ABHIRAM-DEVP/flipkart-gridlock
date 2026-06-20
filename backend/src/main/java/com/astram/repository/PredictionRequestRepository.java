package com.astram.repository;

import com.astram.entity.PredictionRequest;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.UUID;

@Repository
public interface PredictionRequestRepository extends JpaRepository<PredictionRequest, UUID> {
}
