import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# ============================================================
# Load .env file
# ============================================================
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# ============================================================
# Gemini API Configuration
# ============================================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

if not GEMINI_API_KEY:
    logging.warning("GEMINI_API_KEY not set. AI modules will fail. Set it in .env file.")

# ============================================================
# Server Configuration
# ============================================================
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
AUDIT_LOG_DIR = os.environ.get("AUDIT_LOG_DIR", "./logs")

# ============================================================
# Logging Setup
# ============================================================
LOG_DIR = Path(AUDIT_LOG_DIR)
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "vendorguard.log", encoding="utf-8"),
    ]
)

logger = logging.getLogger("vendorguard")

# ============================================================
# Risk Profile Weights
# ============================================================
RISK_PROFILES = {
    "conservative": {
        "news_sentiment": 0.25,
        "compliance": 0.35,
        "financial_health": 0.20,
        "fourth_party": 0.20,
    },
    "balanced": {
        "news_sentiment": 0.30,
        "compliance": 0.30,
        "financial_health": 0.20,
        "fourth_party": 0.20,
    },
    "tech_focused": {
        "news_sentiment": 0.30,
        "compliance": 0.20,
        "financial_health": 0.20,
        "fourth_party": 0.30,
    },
}

# ============================================================
# Risk Level Thresholds
# ============================================================
RISK_THRESHOLDS = {
    "CRITICAL": 80,
    "HIGH": 60,
    "MEDIUM": 40,
    "LOW": 0,
}

def get_risk_level(score: float) -> str:
    """Convert a numeric risk score (0-100) to a risk level."""
    if score >= RISK_THRESHOLDS["CRITICAL"]:
        return "CRITICAL"
    elif score >= RISK_THRESHOLDS["HIGH"]:
        return "HIGH"
    elif score >= RISK_THRESHOLDS["MEDIUM"]:
        return "MEDIUM"
    return "LOW"

# ============================================================
# Required Certifications (RBI + Industry Standards)
# ============================================================
REQUIRED_CERTIFICATIONS = [
    "ISO 27001",   # Information Security Management
    "SOC 2",       # Service Organization Control
    "PCI DSS",     # Payment Card Industry Data Security
    "ISO 22301",   # Business Continuity Management
]

# ============================================================
# Known Fourth-Party Providers
# ============================================================
KNOWN_FOURTH_PARTIES = [
    "AWS", "Azure", "GCP",
    "Razorpay", "PayU", "Paytm", "PhonePe",
    "Cloudflare", "Akamai",
    "Salesforce", "SAP",
    "MongoDB Atlas", "Snowflake",
]

# ============================================================
# Monitoring Cadence Settings
# ============================================================
MONITORING_CADENCE = {
    "news_sentiment": "6_hourly",
    "compliance": "event_driven",
    "financial_health": "quarterly",
    "fourth_party": "6_hourly",
}

# ============================================================
# Vendor Tier Classification
# ============================================================
TIER_THRESHOLDS = {
    "contract_critical": 50_000_000,   # Rs. 5 Crore
    "contract_important": 5_000_000,   # Rs. 50 Lakh
}

def classify_vendor_tier(handles_pii: bool, contract_value: float, operational_dependency: str) -> str:
    """Classify vendor into CRITICAL / IMPORTANT / STANDARD tier."""
    if handles_pii or contract_value > TIER_THRESHOLDS["contract_critical"] or operational_dependency == "high":
        return "CRITICAL"
    if contract_value > TIER_THRESHOLDS["contract_important"] or operational_dependency == "medium":
        return "IMPORTANT"
    return "STANDARD"

# ============================================================
# Rate Limiting (requests per minute per module)
# ============================================================
RATE_LIMIT_RPM = int(os.environ.get("RATE_LIMIT_RPM", "15"))

# ============================================================
# API Authentication
# ============================================================
API_AUTH_KEY = os.environ.get("API_AUTH_KEY", "")

if not API_AUTH_KEY:
    logging.warning("API_AUTH_KEY not set. API will be unauthenticated.")

# ============================================================
# Historical Database
# ============================================================
HISTORY_DB = os.environ.get("HISTORY_DB", "./data/history.db")
