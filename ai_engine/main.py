"""
VendorGuard AI - Production-Ready FastAPI Server

Features:
- API key authentication (X-API-Key header)
- Rate limiting (in-memory, per-IP)
- Request ID tracing (X-Request-ID header)
- Response time logging
- Health check endpoint (/health)
- Vendor CRUD (POST/PUT/DELETE /vendors)
- Historical assessment tracking with trends
- Contagion impact query (/contagion-map/impact)
- Per-vendor cache invalidation
- Global error handler (no stack traces leaked)
- Startup validation
- Cache with TTL
"""

import json
import os
import time
import uuid
import logging
from datetime import datetime
from collections import defaultdict
from fastapi import FastAPI, HTTPException, Query, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List
from config import RISK_PROFILES, HOST, PORT, GEMINI_API_KEY, RATE_LIMIT_RPM, API_AUTH_KEY
from risk_aggregator import aggregate_risk, build_contagion_map
from report_generator import generate_report
from audit_logger import get_audit_trail, log_decision
from history_db import save_assessment, get_vendor_history, get_vendor_trend

logger = logging.getLogger("vendorguard.api")

# ============================================================
# Load vendor data
# ============================================================
DATA_FILE = os.path.join(os.path.dirname(__file__), "vendor_data.json")

with open(DATA_FILE, "r", encoding="utf-8") as f:
    ALL_VENDORS = json.load(f)

# Build lookup for fast access
_vendor_map = {v["vendor_id"]: v for v in ALL_VENDORS}

# ============================================================
# Cache with TTL
# ============================================================
CACHE_TTL_SECONDS = 3600

_assessment_cache = {}
_cache_timestamps = {}


def _cache_get(key: str):
    if key in _assessment_cache:
        ts = _cache_timestamps.get(key, 0)
        if time.time() - ts < CACHE_TTL_SECONDS:
            return _assessment_cache[key]
        else:
            del _assessment_cache[key]
            del _cache_timestamps[key]
    return None


def _cache_set(key: str, value):
    _assessment_cache[key] = value
    _cache_timestamps[key] = time.time()


def _cache_clear_vendor(vendor_id: str):
    """Clear cache entries for a specific vendor."""
    keys_to_remove = [k for k in _assessment_cache if k.startswith(vendor_id)]
    for k in keys_to_remove:
        del _assessment_cache[k]
        _cache_timestamps.pop(k, None)
    return len(keys_to_remove)


# ============================================================
# Rate Limiter
# ============================================================
_rate_limit_store = defaultdict(list)


def _check_rate_limit(ip: str) -> bool:
    now = time.time()
    window = 60
    _rate_limit_store[ip] = [t for t in _rate_limit_store[ip] if now - t < window]
    if len(_rate_limit_store[ip]) >= RATE_LIMIT_RPM:
        return False
    _rate_limit_store[ip].append(now)
    return True


# ============================================================
# Pydantic Models for Vendor CRUD
# ============================================================
class VendorCreate(BaseModel):
    vendor_id: str = Field(..., description="Unique vendor ID (e.g. V051)")
    name: str = Field(..., description="Vendor name")
    category: str = Field(..., description="e.g. Cloud Infrastructure, Payment Gateway")
    tier: str = Field(default="STANDARD", description="CRITICAL / IMPORTANT / STANDARD")
    certifications: List[str] = Field(default=[], description="e.g. ['ISO 27001', 'SOC 2']")
    dependencies: List[str] = Field(default=[], description="e.g. ['AWS', 'Razorpay']")
    sla_uptime: float = Field(default=99.0, description="SLA uptime percentage")
    recent_news: List[str] = Field(default=[], description="Recent news headlines")
    financials: dict = Field(default={}, description="Financial data")
    tier_factors: dict = Field(default={}, description="Tier classification factors")


class VendorUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    tier: Optional[str] = None
    certifications: Optional[List[str]] = None
    dependencies: Optional[List[str]] = None
    sla_uptime: Optional[float] = None
    recent_news: Optional[List[str]] = None
    financials: Optional[dict] = None
    tier_factors: Optional[dict] = None


# ============================================================
# FastAPI App
# ============================================================
app = FastAPI(
    title="VendorGuard AI - Risk Assessment Engine",
    description="Continuous vendor monitoring for banking risk management & RBI compliance",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Response-Time"],
)


# ============================================================
# Middleware: Auth + Request tracing + Response time + Rate limiting
# ============================================================

# Endpoints that don't require authentication
PUBLIC_PATHS = {"/", "/health", "/docs", "/redoc", "/openapi.json"}


@app.middleware("http")
async def production_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
    start_time = time.time()

    # --- Authentication ---
    # Allow CORS preflight (OPTIONS) and public paths without auth
    if API_AUTH_KEY and request.method != "OPTIONS" and request.url.path not in PUBLIC_PATHS:
        api_key = request.headers.get("X-API-Key", "")
        if api_key != API_AUTH_KEY:
            logger.warning(f"[{request_id}] Auth failed from {request.client.host if request.client else 'unknown'}")
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "message": "Invalid or missing API key. Send X-API-Key header.",
                    "request_id": request_id,
                },
                headers={"X-Request-ID": request_id},
            )

    # --- Rate Limiting (skip health and CORS preflight) ---
    if request.url.path != "/health" and request.method != "OPTIONS":
        client_ip = request.client.host if request.client else "unknown"
        if not _check_rate_limit(client_ip):
            logger.warning(f"[{request_id}] Rate limited: {client_ip}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limited",
                    "message": f"Too many requests. Limit: {RATE_LIMIT_RPM}/min",
                    "request_id": request_id,
                },
                headers={"X-Request-ID": request_id, "Retry-After": "60"},
            )

    # --- Process ---
    try:
        response = await call_next(request)
    except Exception as e:
        logger.error(f"[{request_id}] Unhandled: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "message": "Unexpected error.", "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )

    elapsed = round((time.time() - start_time) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time"] = f"{elapsed}ms"

    logger.info(f"[{request_id}] {request.method} {request.url.path} -> {response.status_code} ({elapsed}ms)")
    return response


# ============================================================
# Error Handlers
# ============================================================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = request.headers.get("X-Request-ID", "unknown")
    logger.error(f"[{request_id}] Unhandled: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"error": "internal_error", "request_id": request_id})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = request.headers.get("X-Request-ID", "unknown")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code, "request_id": request_id},
    )


# ============================================================
# Startup
# ============================================================
@app.on_event("startup")
def startup_checks():
    checks = {
        "GEMINI_API_KEY": "OK" if GEMINI_API_KEY else "MISSING",
        "API_AUTH_KEY": "OK" if API_AUTH_KEY else "DISABLED (no auth)",
        "Vendor Data": f"{len(ALL_VENDORS)} vendors",
        "Risk Profiles": f"{len(RISK_PROFILES)} profiles",
    }
    logger.info("=== Startup Checks ===")
    for k, v in checks.items():
        logger.info(f"  {k}: {v}")
    logger.info("=== Server Ready ===")


# ============================================================
# ENDPOINTS
# ============================================================

# ----- Info -----
@app.get("/")
def root():
    return {
        "name": "VendorGuard AI",
        "version": "2.0.0",
        "auth_required": bool(API_AUTH_KEY),
        "endpoints": {
            "health": "GET /health",
            "vendors": "GET /vendors",
            "vendor_create": "POST /vendors",
            "vendor_update": "PUT /vendors/{vendor_id}",
            "vendor_delete": "DELETE /vendors/{vendor_id}",
            "assess": "GET /assess/{vendor_id}",
            "assess_all": "GET /assess/all",
            "history": "GET /history/{vendor_id}",
            "trend": "GET /trend/{vendor_id}",
            "report": "GET /report/{vendor_id}",
            "profiles": "GET /profiles",
            "contagion_map": "GET /contagion-map",
            "contagion_impact": "GET /contagion-map/impact?dependency=AWS",
            "audit_trail": "GET /audit-trail",
            "cache_clear": "POST /cache/clear",
            "cache_clear_vendor": "POST /cache/clear/{vendor_id}",
        }
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "checks": {
            "api_key": bool(GEMINI_API_KEY),
            "auth_enabled": bool(API_AUTH_KEY),
            "vendors": len(ALL_VENDORS),
            "cache_entries": len(_assessment_cache),
            "rate_limit_rpm": RATE_LIMIT_RPM,
        }
    }


# ----- Vendor CRUD -----
@app.get("/vendors")
def get_vendors(
    tier: str = Query(None, description="Filter: CRITICAL/IMPORTANT/STANDARD"),
    category: str = Query(None, description="Filter by category")
):
    """List all vendors. Supports filtering by tier and category."""
    vendors = ALL_VENDORS

    if tier:
        tier = tier.upper()
        if tier not in ["CRITICAL", "IMPORTANT", "STANDARD"]:
            raise HTTPException(400, "Tier must be CRITICAL, IMPORTANT, or STANDARD")
        vendors = [v for v in vendors if v.get("tier") == tier]

    if category:
        vendors = [v for v in vendors if v.get("category", "").lower() == category.lower()]

    return {
        "total": len(vendors),
        "filters": {"tier": tier, "category": category},
        "vendors": [{
            "vendor_id": v["vendor_id"],
            "name": v["name"],
            "category": v.get("category", "Unknown"),
            "tier": v.get("tier", "STANDARD"),
            "certifications": v.get("certifications", []),
            "dependencies": v.get("dependencies", []),
            "contract_value": v.get("tier_factors", {}).get("contract_value", 0),
            "sla_uptime": v.get("sla_uptime", 0)
        } for v in vendors]
    }


@app.post("/vendors", status_code=201)
def create_vendor(vendor: VendorCreate):
    """Add a new vendor to the registry."""
    if vendor.vendor_id in _vendor_map:
        raise HTTPException(409, f"Vendor {vendor.vendor_id} already exists. Use PUT to update.")

    vendor_dict = vendor.model_dump()
    ALL_VENDORS.append(vendor_dict)
    _vendor_map[vendor.vendor_id] = vendor_dict
    _save_vendor_data()

    logger.info(f"Vendor created: {vendor.vendor_id} ({vendor.name})")
    return {"message": "Vendor created", "vendor_id": vendor.vendor_id, "vendor": vendor_dict}


@app.put("/vendors/{vendor_id}")
def update_vendor(vendor_id: str, updates: VendorUpdate):
    """Update an existing vendor. Only provided fields are updated."""
    vendor = _find_vendor(vendor_id)

    update_data = updates.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(400, "No fields to update. Provide at least one field.")

    vendor.update(update_data)
    _cache_clear_vendor(vendor_id)
    _save_vendor_data()

    logger.info(f"Vendor updated: {vendor_id} (fields: {list(update_data.keys())})")
    return {"message": "Vendor updated", "vendor_id": vendor_id, "updated_fields": list(update_data.keys())}


@app.delete("/vendors/{vendor_id}")
def delete_vendor(vendor_id: str):
    """Remove a vendor from the registry."""
    vendor = _find_vendor(vendor_id)

    ALL_VENDORS.remove(vendor)
    del _vendor_map[vendor_id]
    _cache_clear_vendor(vendor_id)
    _save_vendor_data()

    logger.info(f"Vendor deleted: {vendor_id}")
    return {"message": "Vendor deleted", "vendor_id": vendor_id}


# ----- Assessment -----
@app.get("/assess/all")
def assess_all_vendors(profile: str = Query("balanced", description="Risk profile")):
    """Batch assess all vendors."""
    if profile not in RISK_PROFILES:
        raise HTTPException(400, f"Invalid profile. Choose from: {list(RISK_PROFILES.keys())}")

    results = []
    for vendor in ALL_VENDORS:
        cache_key = f"{vendor['vendor_id']}_{profile}"
        assessment = _cache_get(cache_key)
        if not assessment:
            assessment = aggregate_risk(vendor, ALL_VENDORS, profile)
            _cache_set(cache_key, assessment)
            save_assessment(vendor["vendor_id"], vendor["name"], profile, assessment)

        results.append({
            "vendor_id": assessment["vendor_id"],
            "vendor_name": assessment["vendor_name"],
            "vendor_tier": assessment["vendor_tier"],
            "overall_risk_score": assessment["overall_risk_score"],
            "risk_level": assessment["risk_level"],
            "risk_profile_used": assessment["risk_profile_used"],
            "component_scores": {
                "news_sentiment": assessment["components"]["news_sentiment"]["score"],
                "compliance": assessment["components"]["compliance"]["score"],
                "financial_health": assessment["components"]["financial_health"]["score"],
                "fourth_party": assessment["components"]["fourth_party"]["score"]
            },
            "alert_count": len(assessment.get("alerts", [])),
        })

    scores = [r["overall_risk_score"] for r in results]
    return {
        "profile": profile,
        "total_assessed": len(results),
        "summary": {
            "avg_risk": round(sum(scores) / len(scores), 1) if scores else 0,
            "max_risk": max(scores) if scores else 0,
            "critical": sum(1 for r in results if r["risk_level"] == "CRITICAL"),
            "high": sum(1 for r in results if r["risk_level"] == "HIGH"),
        },
        "assessments": results
    }


@app.get("/assess/{vendor_id}")
def assess_vendor(vendor_id: str, profile: str = Query("balanced")):
    """Full risk assessment for a single vendor."""
    if profile not in RISK_PROFILES:
        raise HTTPException(400, f"Invalid profile. Choose from: {list(RISK_PROFILES.keys())}")

    vendor = _find_vendor(vendor_id)
    cache_key = f"{vendor_id}_{profile}"
    assessment = _cache_get(cache_key)
    if assessment:
        return assessment

    assessment = aggregate_risk(vendor, ALL_VENDORS, profile)
    _cache_set(cache_key, assessment)
    save_assessment(vendor_id, vendor["name"], profile, assessment)

    return assessment


# ----- History & Trends -----
@app.get("/history/{vendor_id}")
def vendor_history(vendor_id: str, limit: int = Query(30, ge=1, le=200)):
    """Get historical assessments for a vendor."""
    _find_vendor(vendor_id)  # Validate vendor exists
    history = get_vendor_history(vendor_id, limit)
    return {
        "vendor_id": vendor_id,
        "total": len(history),
        "assessments": history
    }


@app.get("/trend/{vendor_id}")
def vendor_trend(vendor_id: str):
    """Get trend analysis: is this vendor getting better or worse?"""
    _find_vendor(vendor_id)
    trend = get_vendor_trend(vendor_id)
    return trend


# ----- Reports -----
@app.get("/report/{vendor_id}")
def get_report(
    vendor_id: str,
    lang: str = Query("english", description="english/hindi"),
    format: str = Query("summary", description="summary/rbi_audit")
):
    """Generate AI compliance report."""
    if lang not in ["english", "hindi"]:
        raise HTTPException(400, "Language must be 'english' or 'hindi'")
    if format not in ["summary", "rbi_audit"]:
        raise HTTPException(400, "Format must be 'summary' or 'rbi_audit'")

    vendor = _find_vendor(vendor_id)

    cache_key = f"{vendor_id}_balanced"
    assessment = _cache_get(cache_key)
    if not assessment:
        assessment = aggregate_risk(vendor, ALL_VENDORS, "balanced")
        _cache_set(cache_key, assessment)

    report = generate_report(vendor, assessment, language=lang, format=format)
    return {
        "vendor_id": vendor_id,
        "vendor_name": vendor["name"],
        "language": lang,
        "format": format,
        "generated_at": datetime.now().isoformat(),
        "report": report
    }


# ----- Profiles -----
@app.get("/profiles")
def get_profiles():
    return {
        "profiles": [
            {"name": n, "weights": w, "description": _profile_desc(n)}
            for n, w in RISK_PROFILES.items()
        ]
    }


# ----- Contagion Map -----
@app.get("/contagion-map")
def get_contagion_map():
    """Full vendor dependency network."""
    return build_contagion_map(ALL_VENDORS)


@app.get("/contagion-map/impact")
def get_contagion_impact(dependency: str = Query(..., description="e.g. AWS, Razorpay, Azure")):
    """Blast radius: what happens if a specific dependency goes down?"""
    from fourth_party_risk import FOURTH_PARTY_NEWS_DB

    affected = []
    total_contract_value = 0

    for v in ALL_VENDORS:
        if dependency in v.get("dependencies", []):
            cv = v.get("tier_factors", {}).get("contract_value", 0)
            affected.append({
                "vendor_id": v["vendor_id"],
                "name": v["name"],
                "tier": v.get("tier", "STANDARD"),
                "category": v.get("category", "Unknown"),
                "contract_value": cv,
                "dependency_role": v.get("dependency_details", {}).get(dependency, "Service provider"),
            })
            total_contract_value += cv

    if not affected:
        raise HTTPException(404, f"No vendors depend on '{dependency}'.")

    # Check if dependency has known issues
    news = FOURTH_PARTY_NEWS_DB.get(dependency, [])

    return {
        "dependency": dependency,
        "status": "AT_RISK" if news else "HEALTHY",
        "known_issues": news,
        "blast_radius": {
            "affected_vendors": len(affected),
            "total_contract_value": total_contract_value,
            "total_contract_value_cr": round(total_contract_value / 10000000, 2),
            "critical_vendors": sum(1 for a in affected if a["tier"] == "CRITICAL"),
        },
        "affected_vendors": affected,
    }


# ----- Cache Management -----
@app.post("/cache/clear")
def clear_cache():
    count = len(_assessment_cache)
    _assessment_cache.clear()
    _cache_timestamps.clear()
    logger.info(f"Full cache cleared ({count} entries)")
    return {"message": "Cache cleared", "entries_removed": count}


@app.post("/cache/clear/{vendor_id}")
def clear_vendor_cache(vendor_id: str):
    """Clear cache for a single vendor (e.g. after cert update)."""
    _find_vendor(vendor_id)
    count = _cache_clear_vendor(vendor_id)
    logger.info(f"Cache cleared for {vendor_id} ({count} entries)")
    return {"message": f"Cache cleared for {vendor_id}", "entries_removed": count}


# ----- Audit Trail -----
@app.get("/audit-trail")
def get_audit_trail_endpoint(
    vendor_id: str = Query(None),
    limit: int = Query(50, ge=1, le=500)
):
    entries = get_audit_trail(vendor_id=vendor_id, limit=limit)
    return {"total": len(entries), "filter": vendor_id or "all", "entries": entries}


# ============================================================
# Helpers
# ============================================================
def _find_vendor(vendor_id: str) -> dict:
    if vendor_id in _vendor_map:
        return _vendor_map[vendor_id]
    raise HTTPException(404, f"Vendor '{vendor_id}' not found. Use GET /vendors to list all.")


def _profile_desc(name: str) -> str:
    return {
        "conservative": "Higher compliance weight. For Public Sector Banks.",
        "balanced": "Equal weight across dimensions. Default.",
        "tech_focused": "Higher fourth-party/tech weight. For fintech.",
    }.get(name, "")


def _save_vendor_data():
    """Persist vendor changes back to JSON file."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(ALL_VENDORS, f, indent=2, ensure_ascii=False)


# ============================================================
# Run
# ============================================================
if __name__ == "__main__":
    import uvicorn
    print("\n=== VendorGuard AI v2.0 ===")
    print("=" * 40)
    print(f"  Vendors:    {len(ALL_VENDORS)}")
    print(f"  API Key:    {'SET' if GEMINI_API_KEY else 'MISSING'}")
    print(f"  Auth:       {'ENABLED' if API_AUTH_KEY else 'DISABLED'}")
    print(f"  Rate Limit: {RATE_LIMIT_RPM} req/min")
    print(f"  Server:     http://{HOST}:{PORT}")
    print(f"  Docs:       http://{HOST}:{PORT}/docs")
    print("=" * 40)

    uvicorn.run(app, host=HOST, port=PORT)
