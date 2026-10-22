"""Data models and schemas for Celesto Agent & Ledger."""
import re
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator

SANDBOX_NAME_REGEX = re.compile(r"^sbx-[a-z0-9]{8,}$")
VALID_STATES = {"created", "ready", "running", "succeeded", "failed", "deleted"}
VALID_EXECUTION_TARGET = "celesto_sandbox"


class RunCreate(BaseModel):
    run_id: str = Field(..., min_length=1, description="Unique identifier for the run")
    sandbox_name: str = Field(..., description="Sandbox name matching sbx-[a-z0-9]{8,}")
    problem_id: str = Field(..., min_length=1, description="Identifier of the task or problem")
    state: str = Field(..., description="State of the run")
    execution_target: str = Field(..., description="Execution environment, must be celesto_sandbox")

    @field_validator("sandbox_name")
    @classmethod
    def validate_sandbox_name(cls, v: str) -> str:
        if not SANDBOX_NAME_REGEX.match(v):
            raise ValueError(f"sandbox_name '{v}' must match pattern '^sbx-[a-z0-9]{{8,}}$'")
        return v

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        if v not in VALID_STATES:
            raise ValueError(f"state '{v}' must be one of {sorted(VALID_STATES)}")
        return v

    @field_validator("execution_target")
    @classmethod
    def validate_execution_target(cls, v: str) -> str:
        if v != VALID_EXECUTION_TARGET:
            raise ValueError(f"execution_target must be '{VALID_EXECUTION_TARGET}', got '{v}'")
        return v


class RunRecord(BaseModel):
    run_id: str
    sandbox_name: str
    problem_id: str
    state: str
    execution_target: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CommandAuditEntry(BaseModel):
    ts: str
    sandbox_name: str
    command: str
    decision: Literal["allow", "block"]
    execution_target: Literal["celesto_sandbox"]
