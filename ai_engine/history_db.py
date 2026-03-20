"""
History DB - SQLite-based historical assessment storage.

Stores every vendor risk assessment with timestamp for:
- Trend analysis (is this vendor getting worse?)
- Historical comparison (what was the score 3 months ago?)
- Regulatory reporting (show assessment history to RBI)
"""

import json
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from config import HISTORY_DB

logger = logging.getLogger("vendorguard.history")

# Ensure data directory exists
_db_path = Path(HISTORY_DB)
_db_path.parent.mkdir(parents=True, exist_ok=True)


def _get_conn():
    """Get SQLite connection with WAL mode for concurrent reads."""
    conn = sqlite3.connect(str(_db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id TEXT NOT NULL,
            vendor_name TEXT NOT NULL,
            profile TEXT NOT NULL DEFAULT 'balanced',
            overall_score REAL NOT NULL,
            risk_level TEXT NOT NULL,
            news_score REAL,
            compliance_score REAL,
            financial_score REAL,
            fourth_party_score REAL,
            alert_count INTEGER DEFAULT 0,
            assessed_at TEXT NOT NULL,
            full_result TEXT
        );
        
        CREATE INDEX IF NOT EXISTS idx_assessments_vendor 
            ON assessments(vendor_id, assessed_at);
        
        CREATE INDEX IF NOT EXISTS idx_assessments_time 
            ON assessments(assessed_at);

        CREATE TABLE IF NOT EXISTS vendors_custom (
            vendor_id TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            added_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()
    logger.info(f"History DB initialized at {_db_path}")


def save_assessment(vendor_id: str, vendor_name: str, profile: str, assessment: dict):
    """Save a completed assessment to history."""
    conn = _get_conn()
    components = assessment.get("components", {})
    
    conn.execute("""
        INSERT INTO assessments 
        (vendor_id, vendor_name, profile, overall_score, risk_level,
         news_score, compliance_score, financial_score, fourth_party_score,
         alert_count, assessed_at, full_result)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        vendor_id,
        vendor_name,
        profile,
        assessment.get("overall_risk_score", 0),
        assessment.get("risk_level", "UNKNOWN"),
        components.get("news_sentiment", {}).get("score", 0),
        components.get("compliance", {}).get("score", 0),
        components.get("financial_health", {}).get("score", 0),
        components.get("fourth_party", {}).get("score", 0),
        len(assessment.get("alerts", [])),
        datetime.now().isoformat(),
        json.dumps(assessment, ensure_ascii=False),
    ))
    conn.commit()
    conn.close()


def get_vendor_history(vendor_id: str, limit: int = 30) -> list:
    """Get assessment history for a vendor (most recent first)."""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT vendor_id, vendor_name, profile, overall_score, risk_level,
               news_score, compliance_score, financial_score, fourth_party_score,
               alert_count, assessed_at
        FROM assessments 
        WHERE vendor_id = ?
        ORDER BY assessed_at DESC
        LIMIT ?
    """, (vendor_id, limit)).fetchall()
    conn.close()
    
    return [dict(r) for r in rows]


def get_vendor_trend(vendor_id: str) -> dict:
    """Get trend analysis: current vs previous assessments."""
    history = get_vendor_history(vendor_id, limit=10)
    
    if not history:
        return {"status": "no_data", "message": "No historical assessments found."}
    
    current = history[0]
    
    if len(history) < 2:
        return {
            "status": "insufficient_data",
            "current": current,
            "message": "Only one assessment available. Need more data for trend."
        }
    
    previous = history[1]
    
    # Calculate deltas
    delta = current["overall_score"] - previous["overall_score"]
    component_deltas = {
        "news_sentiment": (current["news_score"] or 0) - (previous["news_score"] or 0),
        "compliance": (current["compliance_score"] or 0) - (previous["compliance_score"] or 0),
        "financial_health": (current["financial_score"] or 0) - (previous["financial_score"] or 0),
        "fourth_party": (current["fourth_party_score"] or 0) - (previous["fourth_party_score"] or 0),
    }
    
    # Determine direction
    if delta > 5:
        direction = "WORSENING"
    elif delta < -5:
        direction = "IMPROVING"
    else:
        direction = "STABLE"
    
    return {
        "status": "ok",
        "vendor_id": vendor_id,
        "direction": direction,
        "current_score": current["overall_score"],
        "previous_score": previous["overall_score"],
        "delta": round(delta, 1),
        "component_deltas": component_deltas,
        "current_assessment": current,
        "previous_assessment": previous,
        "total_assessments": len(history),
        "history": history,
    }


# Initialize on import
init_db()
