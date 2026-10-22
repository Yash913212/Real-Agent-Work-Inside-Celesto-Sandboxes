-- Ledger runs schema and seed initialization
CREATE TABLE IF NOT EXISTS runs (
    run_id VARCHAR(64) PRIMARY KEY,
    sandbox_name VARCHAR(64) NOT NULL,
    problem_id VARCHAR(64) NOT NULL,
    state VARCHAR(32) NOT NULL,
    execution_target VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Seed row with sbx-seeddemo1, state 'deleted', execution_target 'celesto_sandbox'
-- Idempotent: re-running does not duplicate
INSERT INTO runs (run_id, sandbox_name, problem_id, state, execution_target)
VALUES ('run-seed-001', 'sbx-seeddemo1', 'detonator-prob-01', 'deleted', 'celesto_sandbox')
ON CONFLICT (run_id) DO NOTHING;
