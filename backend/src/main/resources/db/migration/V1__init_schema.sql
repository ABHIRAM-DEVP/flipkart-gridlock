CREATE TABLE prediction_requests (
    id UUID PRIMARY KEY,
    requested_at TIMESTAMPTZ DEFAULT now(),
    request_payload JSONB NOT NULL,
    response_payload JSONB NOT NULL,
    duration_estimate DOUBLE PRECISION NULL,
    severity_label TEXT NULL
);

CREATE TABLE plan_requests (
    id UUID PRIMARY KEY,
    requested_at TIMESTAMPTZ DEFAULT now(),
    budget INT NOT NULL,
    event_count INT NOT NULL,
    request_payload JSONB NOT NULL,
    response_payload JSONB NOT NULL
);

CREATE TABLE planned_impact_requests (
    id UUID PRIMARY KEY,
    requested_at TIMESTAMPTZ DEFAULT now(),
    request_payload JSONB NOT NULL,
    response_payload JSONB NOT NULL
);

CREATE TABLE metrics_snapshots (
    id UUID PRIMARY KEY,
    captured_at TIMESTAMPTZ DEFAULT now(),
    metrics_payload JSONB NOT NULL
);

CREATE INDEX idx_pred_requested_at ON prediction_requests(requested_at DESC);
CREATE INDEX idx_plan_requested_at ON plan_requests(requested_at DESC);
CREATE INDEX idx_impact_requested_at ON planned_impact_requests(requested_at DESC);
CREATE INDEX idx_metrics_captured_at ON metrics_snapshots(captured_at DESC);
