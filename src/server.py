"""FastAPI Control Plane Server for Celesto Agent Run Ledger."""
import re
from contextlib import asynccontextmanager
from typing import Dict, Any, List

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.config import API_PORT
from src.db import db
from src.models import SANDBOX_NAME_REGEX, VALID_STATES, VALID_EXECUTION_TARGET, RunCreate


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schema and seed on boot
    db.init_db()
    yield


app = FastAPI(title="Celesto Run Ledger Control Plane", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Ensure schema validation failures return HTTP 400 as required."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "Validation error", "details": exc.errors()},
    )


@app.get("/health")
def health() -> Dict[str, str]:
    """Health check endpoint required by docker-compose and monitors."""
    return {"status": "ok"}


@app.get("/api/runs")
def list_runs() -> List[Dict[str, Any]]:
    """List all registered sandbox runs from the ledger."""
    return db.list_runs()


@app.post("/api/runs", status_code=status.HTTP_201_CREATED)
async def create_run(request: Request):
    """
    Register a new run in the ledger.
    Enforces strict validation:
    - sandbox_name must match sbx-[a-z0-9]{8,}
    - state must be one of: created, ready, running, succeeded, failed, deleted
    - execution_target must be exactly celesto_sandbox
    Returns HTTP 400 on any invalid input.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    run_id = body.get("run_id")
    sandbox_name = body.get("sandbox_name")
    problem_id = body.get("problem_id")
    state = body.get("state")
    execution_target = body.get("execution_target")

    if not run_id or not isinstance(run_id, str):
        raise HTTPException(status_code=400, detail="Missing or invalid run_id")

    if not sandbox_name or not isinstance(sandbox_name, str) or not SANDBOX_NAME_REGEX.match(sandbox_name):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sandbox_name '{sandbox_name}'; must match pattern '^sbx-[a-z0-9]{{8,}}$'",
        )

    if not problem_id or not isinstance(problem_id, str):
        raise HTTPException(status_code=400, detail="Missing or invalid problem_id")

    if state not in VALID_STATES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state '{state}'; must be one of {sorted(VALID_STATES)}",
        )

    if execution_target != VALID_EXECUTION_TARGET:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid execution_target '{execution_target}'; must be exactly '{VALID_EXECUTION_TARGET}'",
        )

    record = db.insert_run(
        run_id=run_id,
        sandbox_name=sandbox_name,
        problem_id=problem_id,
        state=state,
        execution_target=execution_target,
    )
    return record


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)
