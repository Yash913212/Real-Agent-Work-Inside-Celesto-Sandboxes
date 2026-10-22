"""Safety hooks and command inspection callbacks for Celesto sandboxes."""
import re
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple
from src.config import AUDIT_LOG_PATH

# Patterns for destructive or malicious commands
BLOCKED_PATTERNS = [
    re.compile(r"rm\s+(-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*|-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*)\s+(/|/\*|~|~\*)"),
    re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"),  # fork bomb
    re.compile(r"mkfs\.[a-z0-9]+\s+/dev/"),
    re.compile(r"dd\s+if=/dev/(zero|urandom)\s+of=/dev/"),
    re.compile(r">\s*/dev/(sda|vda|nvme)"),
    re.compile(r"(curl|wget)\s+.*(\$CELESTO_API_KEY|\$API_KEY|\$LLM_API_KEY|\.env)"),  # exfiltration
    re.compile(r"cat\s+(/etc/shadow|\.env)"),  # reading sensitive host secrets
    re.compile(r"/dev/tcp/\d+\.\d+\.\d+\.\d+/\d+"),  # reverse shell
    re.compile(r"curl\s+.*\|\s*(bash|sh)"),  # unverified piped execution
]


def audit_command(
    sandbox_name: str,
    command: str,
    decision: str,
    audit_file: Path = AUDIT_LOG_PATH
) -> dict:
    """Append a structured command record to logs/commands.jsonl."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "sandbox_name": sandbox_name,
        "command": command.strip(),
        "decision": decision,
        "execution_target": "celesto_sandbox",
    }
    audit_file.parent.mkdir(parents=True, exist_ok=True)
    with open(audit_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def evaluate_command_safety(sandbox_name: str, command: str) -> Tuple[bool, str]:
    """
    Evaluate command against safety policies.
    Returns (is_allowed: bool, reason: str).
    Always logs the evaluation decision to the audit log.
    """
    stripped_cmd = command.strip()
    if not stripped_cmd:
        audit_command(sandbox_name, command, "block")
        return False, "Empty command not allowed"

    for pattern in BLOCKED_PATTERNS:
        if pattern.search(stripped_cmd):
            audit_command(sandbox_name, stripped_cmd, "block")
            return False, f"Command blocked by safety hook: matched hostile pattern '{pattern.pattern}'"

    audit_command(sandbox_name, stripped_cmd, "allow")
    return True, "Command permitted"
