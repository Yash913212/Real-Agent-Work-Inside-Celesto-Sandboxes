import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import re
import math
import json
from dateutil.parser import isoparse
import pytest
from starlette.testclient import TestClient

from src.server import app
from src.db import db
from src.models import SANDBOX_NAME_REGEX


def test_req_1_docker_compose_and_dockerfile():
    """Requirement 1: docker-compose.yml and Dockerfile exist, valid services & healthchecks."""
    compose_path = REPO_ROOT / "docker-compose.yml"
    dockerfile_path = REPO_ROOT / "Dockerfile"
    assert compose_path.exists(), "docker-compose.yml must exist"
    assert dockerfile_path.exists(), "Dockerfile must exist"

    compose_text = compose_path.read_text()
    assert "api:" in compose_text, "api service must exist in docker-compose.yml"
    assert "ledger:" in compose_text, "ledger service must exist in docker-compose.yml"
    assert "8080:8080" in compose_text, "api must publish port 8080"
    assert "service_healthy" in compose_text, "api must wait for ledger condition: service_healthy"
    assert "pg_isready" in compose_text, "ledger healthcheck must use pg_isready"
    assert "/health" in compose_text, "api healthcheck must curl /health"
    assert "interval:" in compose_text, "healthchecks must specify interval"
    assert "timeout:" in compose_text, "healthchecks must specify timeout"
    assert "retries:" in compose_text, "healthchecks must specify retries"
    assert "start_period:" in compose_text, "healthchecks must specify start_period"
    assert "./seeds" in compose_text, "ledger must mount ./seeds"


def test_req_2_env_example_and_no_live_env():
    """Requirement 2: .env.example exists with placeholders, no .env file in root."""
    env_example = REPO_ROOT / ".env.example"
    live_env = REPO_ROOT / ".env"
    assert env_example.exists(), ".env.example must exist"
    assert not live_env.exists(), ".env must NOT be present in repository root"

    content = env_example.read_text()
    required_keys = [
        "CELESTO_PROVIDER",
        "CELESTO_API_KEY",
        "LLM_API_KEY",
        "LLM_MODEL",
        "DATABASE_URL",
        "API_PORT",
    ]
    for key in required_keys:
        assert f"{key}=" in content, f".env.example must contain required key {key}"


def test_req_3_problem_statement():
    """Requirement 3: reports/problem.json has valid keys, types, lengths, and source."""
    prob_path = REPO_ROOT / "reports" / "problem.json"
    assert prob_path.exists(), "reports/problem.json must exist"

    data = json.loads(prob_path.read_text())
    assert "who" in data and len(data["who"]) >= 40, "who must be >= 40 chars"
    assert "agent_work" in data and len(data["agent_work"]) >= 40, "agent_work must be >= 40 chars"
    assert "proof_output" in data and len(data["proof_output"]) >= 20, "proof_output must be >= 20 chars"
    assert data.get("idea_source") in ["idea_bank", "original"], "idea_source must be 'idea_bank' or 'original'"


def test_req_4_command_audit_log():
    """Requirement 4: logs/commands.jsonl has valid lines, correct execution_target and format."""
    log_path = REPO_ROOT / "logs" / "commands.jsonl"
    assert log_path.exists(), "logs/commands.jsonl must exist"

    lines = [line.strip() for line in log_path.read_text().splitlines() if line.strip()]
    assert len(lines) >= 1, "logs/commands.jsonl must have at least one line"

    has_blocked = False
    for line in lines:
        entry = json.loads(line)
        assert "ts" in entry, "Missing ts field"
        isoparse(entry["ts"])  # Ensure valid ISO-8601
        assert SANDBOX_NAME_REGEX.match(entry["sandbox_name"]), f"Invalid sandbox_name {entry['sandbox_name']}"
        assert entry["command"], "Command cannot be empty"
        assert entry["decision"] in ["allow", "block"], f"Invalid decision {entry['decision']}"
        assert entry["execution_target"] == "celesto_sandbox", "execution_target must be exactly celesto_sandbox"
        if entry["decision"] == "block":
            has_blocked = True

    assert has_blocked, "Audit log should record blocked commands from containment testing"


def test_req_5_capabilities_report():
    """Requirement 5: reports/capabilities.json has at least 2 valid unique capabilities."""
    cap_path = REPO_ROOT / "reports" / "capabilities.json"
    assert cap_path.exists(), "reports/capabilities.json must exist"

    data = json.loads(cap_path.read_text())
    caps = data.get("capabilities", [])
    assert len(caps) >= 2, "Must contain at least 2 capabilities"

    allowed_ids = {
        "persistence", "snapshots", "celestofs", "browser", "published_ports",
        "network_policy", "safety_hooks", "host_mounts", "coding_agent_preset", "agentor_durable"
    }
    seen_ids = set()
    for cap in caps:
        cap_id = cap.get("id")
        assert cap_id in allowed_ids, f"Unknown capability ID: {cap_id}"
        assert cap_id not in seen_ids, f"Duplicate capability ID: {cap_id}"
        seen_ids.add(cap_id)

        why = cap.get("why", "")
        assert len(why) >= 80, f"Capability {cap_id} 'why' must be >= 80 chars, got {len(why)}"

        ev_path = REPO_ROOT / cap.get("evidence_path", "")
        assert ev_path.exists(), f"Evidence path for {cap_id} does not exist: {ev_path}"


def test_req_6_lifecycle_report():
    """Requirement 6: reports/lifecycle.json cleanup flags true, unique valid sandbox names."""
    lf_path = REPO_ROOT / "reports" / "lifecycle.json"
    assert lf_path.exists(), "reports/lifecycle.json must exist"

    data = json.loads(lf_path.read_text())
    assert data.get("cleanup_on_success") is True, "cleanup_on_success must be true"
    assert data.get("cleanup_on_failure") is True, "cleanup_on_failure must be true"
    assert data.get("cleanup_on_interrupt") is True, "cleanup_on_interrupt must be true"

    names = data.get("sandbox_names", [])
    assert len(names) > 0, "sandbox_names must be non-empty"
    assert len(names) == len(set(names)), "sandbox_names must be unique"

    log_text = (REPO_ROOT / "logs" / "commands.jsonl").read_text()
    rel_text = (REPO_ROOT / "reports" / "reliability.json").read_text()

    for name in names:
        assert SANDBOX_NAME_REGEX.match(name), f"Sandbox name {name} invalid pattern"
        assert (name in log_text) or (name in rel_text), f"Sandbox name {name} must appear in logs or reliability"


def test_req_7_reliability_evaluation():
    """Requirement 7: reports/reliability.json arithmetic, 20+ fresh runs, postmortem."""
    rel_path = REPO_ROOT / "reports" / "reliability.json"
    assert rel_path.exists(), "reports/reliability.json must exist"

    data = json.loads(rel_path.read_text())
    runs = data.get("runs", [])
    run_count = data.get("run_count")

    assert run_count == len(runs), "run_count must match length of runs array"
    assert run_count >= 20, "run_count must be at least 20"

    names = set()
    for r in runs:
        name = r.get("sandbox_name", "")
        assert SANDBOX_NAME_REGEX.match(name), f"Invalid sandbox_name {name}"
        assert name not in names, f"Duplicate sandbox_name {name}"
        names.add(name)
        assert r.get("fresh") is True, f"Run {name} fresh must be true"
        assert isinstance(r.get("success"), bool), "success must be a boolean"
        assert r.get("wall_clock_s", -1) >= 0, "wall_clock_s must be >= 0"
        assert r.get("boot_to_ready_s", -1) >= 0, "boot_to_ready_s must be >= 0"
        assert r.get("cost_usd", -1) >= 0, "cost_usd must be >= 0"

    # Math checks
    expected_success_rate = sum(1 for r in runs if r["success"]) / float(run_count)
    assert abs(data["success_rate"] - expected_success_rate) <= 0.001, "success_rate mismatch"

    sorted_wall = sorted([r["wall_clock_s"] for r in runs])
    # For even n, median is mean of 2 central values (1-based: n/2 and n/2 + 1)
    mid_low = sorted_wall[len(runs) // 2 - 1]
    mid_high = sorted_wall[len(runs) // 2]
    expected_median_wall = (mid_low + mid_high) / 2.0
    assert abs(data["median_wall_clock_s"] - expected_median_wall) <= 0.001, "median_wall_clock_s mismatch"

    # p90 is 1-based rank ceil(0.90 * n)
    p90_rank = math.ceil(0.90 * len(runs))
    expected_p90 = sorted_wall[p90_rank - 1]
    assert abs(data["p90_wall_clock_s"] - expected_p90) <= 0.001, "p90_wall_clock_s mismatch"

    sorted_boot = sorted([r["boot_to_ready_s"] for r in runs])
    mid_boot_low = sorted_boot[len(runs) // 2 - 1]
    mid_boot_high = sorted_boot[len(runs) // 2]
    expected_median_boot = (mid_boot_low + mid_boot_high) / 2.0
    assert abs(data["median_boot_to_ready_s"] - expected_median_boot) <= 0.001, "median_boot_to_ready_s mismatch"

    expected_total_cost = sum(r["cost_usd"] for r in runs)
    assert abs(data["total_cost_usd"] - expected_total_cost) <= 0.01, "total_cost_usd mismatch"

    postmortem_file = REPO_ROOT / data["postmortem_path"]
    assert postmortem_file.exists(), f"Postmortem file not found: {postmortem_file}"
    assert len(postmortem_file.read_text()) >= 200, "Postmortem must be at least 200 characters"


def test_req_8_containment():
    """Requirement 8: reports/containment.json attack blocked, host untouched, evidence exists."""
    ct_path = REPO_ROOT / "reports" / "containment.json"
    assert ct_path.exists(), "reports/containment.json must exist"

    data = json.loads(ct_path.read_text())
    assert data.get("attack") in ["prompt_injection_exfil", "destructive_command", "suspicious_package"]
    assert data.get("blocked") is True, "blocked must be true"
    assert data.get("host_untouched") is True, "host_untouched must be true"

    ev_paths = data.get("evidence_paths", [])
    assert len(ev_paths) >= 1, "evidence_paths must have at least one entry"
    for p in ev_paths:
        full_p = REPO_ROOT / p
        assert full_p.exists(), f"Evidence file not found: {full_p}"


def test_req_9_failure_policy_and_trace():
    """Requirement 9: reports/failure_policy.json and failure_trace.jsonl step 7 recovery."""
    pol_path = REPO_ROOT / "reports" / "failure_policy.json"
    assert pol_path.exists(), "reports/failure_policy.json must exist"

    data = json.loads(pol_path.read_text())
    assert data.get("failed_step") == 7, "failed_step must be 7"
    assert data.get("total_steps") == 10, "total_steps must be 10"
    assert data.get("policy") in ["resume", "rollback", "fresh"], "policy must be resume, rollback, or fresh"
    assert len(data.get("rationale", "")) >= 200, "rationale must be at least 200 chars"

    trace_path = REPO_ROOT / data.get("trace_path", "")
    assert trace_path.exists(), f"trace_path does not exist: {trace_path}"

    lines = [json.loads(line) for line in trace_path.read_text().splitlines() if line.strip()]
    policy_events = [line for line in lines if line.get("event") == "policy_applied"]
    assert len(policy_events) >= 1, "Trace must contain at least one policy_applied event"
    assert policy_events[0].get("policy") == data["policy"], "Trace policy must match failure_policy.json"


def test_req_10_concurrency_report():
    """Requirement 10: reports/concurrency.json >= 5 jobs, unique names, breakage notes."""
    con_path = REPO_ROOT / "reports" / "concurrency.json"
    assert con_path.exists(), "reports/concurrency.json must exist"

    data = json.loads(con_path.read_text())
    jobs = data.get("jobs", [])
    assert len(jobs) >= 5, "Must have at least 5 jobs"

    seen_names = set()
    for j in jobs:
        name = j.get("sandbox_name", "")
        assert SANDBOX_NAME_REGEX.match(name), f"Invalid sandbox_name {name}"
        assert name not in seen_names, f"Duplicate job sandbox_name: {name}"
        seen_names.add(name)
        assert j.get("started_at"), "started_at must be non-empty"

    assert len(data.get("breakage_notes", "")) >= 40, "breakage_notes must be >= 40 chars"


def test_req_11_ledger_api():
    """Requirement 11: GET /health, GET /api/runs (includes seeded), POST /api/runs (validation)."""
    client = TestClient(app)

    # 1. Health check
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json() == {"status": "ok"}

    # 2. Seeded run in GET /api/runs
    res_runs = client.get("/api/runs")
    assert res_runs.status_code == 200
    runs = res_runs.json()
    assert isinstance(runs, list)
    seed_found = any(r.get("sandbox_name") == "sbx-seeddemo1" for r in runs)
    assert seed_found, "Seeded sandbox sbx-seeddemo1 must be in GET /api/runs"

    # 3. Valid POST /api/runs
    valid_payload = {
        "run_id": "run-test-valid-001",
        "sandbox_name": "sbx-validrun01",
        "problem_id": "test-prob-01",
        "state": "running",
        "execution_target": "celesto_sandbox",
    }
    res_post = client.post("/api/runs", json=valid_payload)
    assert res_post.status_code == 201
    created_obj = res_post.json()
    assert created_obj["sandbox_name"] == "sbx-validrun01"
    assert created_obj["execution_target"] == "celesto_sandbox"

    # 4. Invalid execution_target -> 400
    bad_target_payload = dict(valid_payload, run_id="run-bad-target", execution_target="host")
    res_bad_target = client.post("/api/runs", json=bad_target_payload)
    assert res_bad_target.status_code == 400

    # 5. Invalid state -> 400
    bad_state_payload = dict(valid_payload, run_id="run-bad-state", state="invalid_state")
    res_bad_state = client.post("/api/runs", json=bad_state_payload)
    assert res_bad_state.status_code == 400

    # 6. Invalid sandbox_name -> 400
    bad_name_payload = dict(valid_payload, run_id="run-bad-name", sandbox_name="invalid-name")
    res_bad_name = client.post("/api/runs", json=bad_name_payload)
    assert res_bad_name.status_code == 400


def test_req_12_readme_required_phrases():
    """Requirement 12: README.md contains all required phrases."""
    readme_path = REPO_ROOT / "README.md"
    assert readme_path.exists(), "README.md must exist"

    text = readme_path.read_text()
    required_phrases = [
        "Problem statement",
        "How I used Celesto",
        "Eval report",
        "Containment test",
        "State and failure design",
        "Setup",
    ]
    for phrase in required_phrases:
        assert phrase in text, f"README.md missing required phrase: '{phrase}'"
