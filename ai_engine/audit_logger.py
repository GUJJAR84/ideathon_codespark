"""
Audit Logger - Immutable decision trail for regulatory compliance.

Every AI decision is logged with:
- Timestamp
- Vendor ID
- Module that made the decision
- Input summary
- Output summary (score, level, confidence)
- Whether human review was flagged
- Gemini model used

This satisfies RBI's requirement for a complete audit trail
of all automated risk decisions.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from config import AUDIT_LOG_DIR, GEMINI_MODEL

audit_logger = logging.getLogger("vendorguard.audit")
audit_logger.setLevel(logging.INFO)

# Dedicated audit log file (append-only, never overwritten)
_audit_log_path = Path(AUDIT_LOG_DIR) / "audit_trail.jsonl"
_audit_log_path.parent.mkdir(parents=True, exist_ok=True)


def log_decision(
    vendor_id: str,
    vendor_name: str,
    module: str,
    input_summary: str,
    score: float,
    level: str,
    confidence: float,
    requires_human_review: bool = False,
    details: dict = None
):
    """Log an AI risk decision to the immutable audit trail."""
    
    entry = {
        "timestamp": datetime.now().isoformat(),
        "vendor_id": vendor_id,
        "vendor_name": vendor_name,
        "module": module,
        "model": GEMINI_MODEL,
        "input_summary": input_summary[:500],  # Truncate long inputs
        "output": {
            "score": score,
            "level": level,
            "confidence": confidence,
            "requires_human_review": requires_human_review
        },
        "details": details or {}
    }
    
    # Write as JSON line (append-only)
    with open(_audit_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    # Also log to standard logger
    review_flag = " [HUMAN REVIEW REQUIRED]" if requires_human_review else ""
    audit_logger.info(
        f"DECISION | {vendor_id} | {module} | score={score} level={level} "
        f"confidence={confidence}%{review_flag}"
    )


def get_audit_trail(vendor_id: str = None, limit: int = 100) -> list:
    """Retrieve audit trail entries, optionally filtered by vendor."""
    
    entries = []
    try:
        with open(_audit_log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or not line.startswith("{"):
                    continue
                try:
                    entry = json.loads(line)
                    if vendor_id is None or entry.get("vendor_id") == vendor_id:
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        return []
    
    # Return most recent first, limited
    return entries[-limit:][::-1]
