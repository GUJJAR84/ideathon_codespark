import json
from datetime import datetime
from config import RISK_PROFILES, get_risk_level, MONITORING_CADENCE
from sentiment_analyzer import analyze_sentiment
from compliance_checker import check_compliance
from financial_scorer import score_financial_health
from fourth_party_risk import assess_fourth_party_risk


def aggregate_risk(vendor: dict, all_vendors: list = None, profile: str = "balanced") -> dict:
    """
    Run all 4 risk modules and aggregate into a single risk assessment.
    
    Args:
        vendor: Vendor data dict
        all_vendors: Full vendor list (for contagion mapping)
        profile: Risk profile name (conservative/balanced/tech_focused)
    
    Returns:
        Complete risk assessment dict matching the data contract
    """
    
    # Get risk profile weights
    weights = RISK_PROFILES.get(profile, RISK_PROFILES["balanced"])
    
    # Run all 4 analyzers
    news_result = analyze_sentiment(vendor)
    compliance_result = check_compliance(vendor)
    financial_result = score_financial_health(vendor)
    fourth_party_result = assess_fourth_party_risk(vendor, all_vendors)
    
    # Calculate weighted overall score
    overall_score = round(
        news_result["score"] * weights["news_sentiment"] +
        compliance_result["score"] * weights["compliance"] +
        financial_result["score"] * weights["financial_health"] +
        fourth_party_result["score"] * weights["fourth_party"]
    )
    overall_score = min(100, max(0, overall_score))
    
    # Generate alerts from all findings
    alerts = _generate_alerts(vendor, news_result, compliance_result, financial_result, fourth_party_result)
    
    # Generate remediation steps
    remediation = _generate_remediation(compliance_result, financial_result, fourth_party_result)
    
    # Build contagion links
    contagion_links = _build_contagion_links(vendor, all_vendors)
    
    return {
        "vendor_id": vendor["vendor_id"],
        "vendor_name": vendor["name"],
        "vendor_tier": vendor.get("tier", "STANDARD"),
        "risk_profile_used": profile,
        "overall_risk_score": overall_score,
        "risk_level": get_risk_level(overall_score),
        "components": {
            "news_sentiment": {
                "score": news_result["score"],
                "level": news_result["level"],
                "confidence": news_result["confidence"],
                "cadence": news_result["cadence"],
                "last_checked": news_result.get("last_checked", datetime.now().isoformat()),
                "sources": news_result["sources"],
                "summary": news_result.get("summary", ""),
                "findings": news_result.get("findings", [])
            },
            "compliance": {
                "score": compliance_result["score"],
                "level": compliance_result["level"],
                "confidence": compliance_result["confidence"],
                "cadence": compliance_result["cadence"],
                "sources": compliance_result["sources"],
                "summary": compliance_result.get("summary", ""),
                "gaps": compliance_result.get("gaps", [])
            },
            "financial_health": {
                "score": financial_result["score"],
                "level": financial_result["level"],
                "confidence": financial_result["confidence"],
                "cadence": financial_result["cadence"],
                "sources": financial_result["sources"],
                "summary": financial_result.get("summary", ""),
                "flags": financial_result.get("flags", []),
                "analysis": financial_result.get("analysis", "")
            },
            "fourth_party": {
                "score": fourth_party_result["score"],
                "level": fourth_party_result["level"],
                "confidence": fourth_party_result["confidence"],
                "cadence": fourth_party_result["cadence"],
                "sources": fourth_party_result["sources"],
                "summary": fourth_party_result.get("summary", ""),
                "risks": fourth_party_result.get("risks", []),
                "affected_vendors": fourth_party_result.get("affected_vendors", [])
            }
        },
        "alerts": alerts,
        "remediation": remediation,
        "contagion_links": contagion_links
    }


def build_contagion_map(all_vendors: list) -> dict:
    """Build the full contagion map showing vendor dependency network."""
    
    nodes = []
    edges = []
    dependency_map = {}  # dep_name -> list of vendor_ids
    
    for vendor in all_vendors:
        nodes.append({
            "id": vendor["vendor_id"],
            "name": vendor["name"],
            "tier": vendor.get("tier", "STANDARD"),
            "category": vendor.get("category", "Unknown"),
            "contract_value": vendor.get("tier_factors", {}).get("contract_value", 0),
            "dependencies": vendor.get("dependencies", [])
        })
        
        for dep in vendor.get("dependencies", []):
            if dep not in dependency_map:
                dependency_map[dep] = []
            dependency_map[dep].append(vendor["vendor_id"])
    
    # Build dependency nodes and edges
    dependencies = []
    for dep_name, connected_vendors in dependency_map.items():
        # Determine status from fourth-party news DB
        from fourth_party_risk import FOURTH_PARTY_NEWS_DB
        news = FOURTH_PARTY_NEWS_DB.get(dep_name, [])
        status = "RISK" if news else "HEALTHY"
        
        dependencies.append({
            "name": dep_name,
            "status": status,
            "connected_vendors": connected_vendors
        })
        
        # Create edges between vendors sharing this dependency
        for i in range(len(connected_vendors)):
            for j in range(i + 1, len(connected_vendors)):
                edges.append({
                    "from": connected_vendors[i],
                    "to": connected_vendors[j],
                    "shared": dep_name
                })
    
    return {
        "nodes": nodes,
        "dependencies": dependencies,
        "edges": edges
    }


def _generate_alerts(vendor, news, compliance, financial, fourth_party) -> list:
    """Generate alerts from high-risk findings."""
    alerts = []
    now = datetime.now().isoformat()
    
    # News alerts
    if news["score"] >= 60:
        for finding in news.get("findings", []):
            if finding.get("confidence", 0) >= 50:
                alert_type = finding.get("risk_category", "NEWS").upper()
                if alert_type in ["CYBERSECURITY", "SECURITY"]:
                    alert_type = "BREACH"
                elif alert_type in ["LEGAL", "REGULATORY"]:
                    alert_type = "REGULATORY"
                else:
                    alert_type = "NEWS"
                
                alerts.append({
                    "type": alert_type,
                    "severity": finding.get("severity", news["level"]),
                    "message": finding.get("finding", "News-based risk detected"),
                    "confidence": finding.get("confidence", 50),
                    "timestamp": now,
                    "vendor_id": vendor["vendor_id"]
                })
    
    # Compliance alerts
    for gap in compliance.get("gaps", []):
        if gap.get("confidence", 0) >= 50:
            alerts.append({
                "type": "COMPLIANCE",
                "severity": "HIGH" if compliance["score"] >= 60 else "MEDIUM",
                "message": gap.get("finding", "Compliance gap detected"),
                "confidence": gap.get("confidence", 50),
                "timestamp": now,
                "vendor_id": vendor["vendor_id"]
            })
    
    # Financial alerts
    if financial["score"] >= 60:
        alerts.append({
            "type": "FINANCIAL",
            "severity": financial["level"],
            "message": f"Financial health concern: {'; '.join(financial.get('flags', [])[:2])}",
            "confidence": financial.get("confidence", 50),
            "timestamp": now,
            "vendor_id": vendor["vendor_id"]
        })
    
    # Fourth-party alerts
    for risk in fourth_party.get("risks", []):
        alerts.append({
            "type": "FOURTH_PARTY",
            "severity": "HIGH",
            "message": f"Fourth-party risk: {risk.get('dependency', '?')} — {risk.get('risk_event', '?')}",
            "confidence": risk.get("confidence", 50),
            "timestamp": now,
            "vendor_id": vendor["vendor_id"],
            "affected_vendors": risk.get("affected_vendors", [])
        })
    
    return alerts


def _generate_remediation(compliance, financial, fourth_party) -> list:
    """Generate prioritized remediation steps."""
    remediation = []
    
    # From compliance gaps
    for gap in compliance.get("gaps", []):
        cert = gap.get("certification", "")
        remediation.append({
            "action": f"Obtain {cert} certification" if cert else gap.get("finding", "Address compliance gap"),
            "priority": "HIGH" if compliance["score"] >= 60 else "MEDIUM",
            "timeline": "90 days",
            "category": "compliance"
        })
    
    # From financial flags
    if financial["score"] >= 60:
        remediation.append({
            "action": "Conduct detailed financial viability assessment of vendor",
            "priority": "HIGH",
            "timeline": "30 days",
            "category": "financial"
        })
        remediation.append({
            "action": "Prepare vendor exit strategy and identify alternative vendors",
            "priority": "MEDIUM",
            "timeline": "60 days",
            "category": "financial"
        })
    
    # From fourth-party risks
    for risk in fourth_party.get("risks", []):
        remediation.append({
            "action": f"Review dependency on {risk.get('dependency', '?')} and evaluate alternatives",
            "priority": "HIGH" if risk.get("confidence", 0) >= 80 else "MEDIUM",
            "timeline": "45 days",
            "category": "fourth_party"
        })
    
    return remediation


def _build_contagion_links(vendor: dict, all_vendors: list = None) -> list:
    """Build contagion links for a specific vendor."""
    if not all_vendors:
        return []
    
    links = []
    for dep in vendor.get("dependencies", []):
        linked = []
        for v in all_vendors:
            if v["vendor_id"] != vendor["vendor_id"] and dep in v.get("dependencies", []):
                linked.append(v["vendor_id"])
        if linked:
            links.append({
                "shared_dependency": dep,
                "linked_vendors": linked
            })
    
    return links
