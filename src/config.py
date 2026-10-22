"""Configuration settings for Celesto Agent & Control Plane."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

CELESTO_PROVIDER = os.getenv("CELESTO_PROVIDER", "cloud")
CELESTO_API_KEY = os.getenv("CELESTO_API_KEY", "replace-me")
CELESTO_BACKEND = os.getenv("CELESTO_BACKEND", "firecracker")

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://example-llm-host/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "replace-me")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ledger:ledger@localhost:5432/ledger")
API_PORT = int(os.getenv("API_PORT", "8080"))

AUDIT_LOG_PATH = Path(os.getenv("AUDIT_LOG_PATH", str(BASE_DIR / "logs" / "commands.jsonl")))
REPORTS_DIR = Path(os.getenv("REPORTS_DIR", str(BASE_DIR / "reports")))
LOG_LEVEL = os.getenv("LOG_LEVEL", "info")
