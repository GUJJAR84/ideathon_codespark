import json
import logging
from google import genai
from config import GEMINI_API_KEY, GEMINI_MODEL, KNOWN_FOURTH_PARTIES, MONITORING_CADENCE, get_risk_level
from audit_logger import log_decision
from datetime import datetime

logger = logging.getLogger("vendorguard.fourth_party")


client = genai.Client(api_key=GEMINI_API_KEY)


FOURTH_PARTY_PROMPT = """You are a supply chain risk analyst specializing in fourth-party risk for the banking sector.

A bank uses vendor "{vendor_name}" ({category}).
This vendor depends on the following third-party services (fourth parties to the bank):
{dependencies}

Recent news about these fourth-party providers:
{fourth_party_news}

Assess the fourth-party risk:
1. For each dependency, evaluate if there are any risk signals
2. Analyze how a disruption in the fourth party would impact the vendor and ultimately the bank
3. Identify chain-reaction risks (if the fourth party fails, what happens?)

Respond ONLY in this exact JSON format (no markdown, no code blocks):
{{
  "overall_score": <0-100 fourth-party risk score>,
  "overall_level": "<CRITICAL/HIGH/MEDIUM/LOW>",
  "summary": "<2-3 sentence fourth-party risk assessment>",
  "risks": [
    {{
      "dependency": "<name of the fourth-party provider>",
      "risk_event": "<what risk event was detected or could occur>",
      "impact": "<how this would impact the vendor and the bank>",
      "confidence": <0-100>,
      "source": "<basis for this assessment>",
      "requires_human_review": <true/false>
    }}
  ]
}}

If no fourth-party risks are detected, return a low score with empty risks array.
"""

# Simulated fourth-party news (in production, this would come from news APIs)
FOURTH_PARTY_NEWS_DB = {
    "AWS": [
        "AWS ap-south-1 region experiences major outage affecting Mumbai availability zone - AWS Status Page",
        "AWS reports intermittent latency issues in India regions - DownDetector"
    ],
    "Razorpay": [
        "Razorpay faces RBI inquiry over merchant onboarding compliance - Economic Times"
    ],
    "Azure": [],
    "GCP": [],
    "Cloudflare": [],
    "Akamai": [],
    "Salesforce": [],
    "SAP": [],
    "MongoDB Atlas": [],
    "Snowflake": [],
    "PayU": [],
    "Paytm": [
        "Paytm Payments Bank faces continued regulatory restrictions from RBI - Moneycontrol"
    ],
    "PhonePe": [],
}


def assess_fourth_party_risk(vendor: dict, all_vendors: list = None) -> dict:
    """Assess fourth-party risk for a vendor based on its dependencies."""
    
    dependencies = vendor.get("dependencies", [])
    dep_details = vendor.get("dependency_details", {})
    
    # If no dependencies, no fourth-party risk
    if not dependencies:
        return {
            "score": 5,
            "level": "LOW",
            "confidence": 95,
            "cadence": MONITORING_CADENCE["fourth_party"],
            "sources": [],
            "summary": f"{vendor['name']} has no known third-party dependencies tracked.",
            "risks": [],
            "affected_vendors": []
        }
    
    # Gather news for this vendor's dependencies
    dep_news = {}
    has_risky_deps = False
    for dep in dependencies:
        news = FOURTH_PARTY_NEWS_DB.get(dep, [])
        if news:
            dep_news[dep] = news
            has_risky_deps = True
    
    # Find other vendors sharing the same risky dependencies (for contagion)
    affected_vendors = []
    if all_vendors and has_risky_deps:
        for dep_name in dep_news.keys():
            for v in all_vendors:
                if v["vendor_id"] != vendor["vendor_id"] and dep_name in v.get("dependencies", []):
                    affected_vendors.append({
                        "vendor_id": v["vendor_id"],
                        "vendor_name": v["name"],
                        "shared_dependency": dep_name
                    })
    
    # If there are risky dependencies, use Gemini for analysis
    if has_risky_deps:
        dep_text = "\n".join(f"- {dep}: {dep_details.get(dep, 'Service provider')}" for dep in dependencies)
        news_text = ""
        for dep, headlines in dep_news.items():
            news_text += f"\n{dep}:\n"
            for h in headlines:
                news_text += f"  - {h}\n"
        
        if not news_text.strip():
            news_text = "No negative news found for any fourth-party provider."
        
        prompt = FOURTH_PARTY_PROMPT.format(
            vendor_name=vendor["name"],
            category=vendor.get("category", "Unknown"),
            dependencies=dep_text,
            fourth_party_news=news_text
        )
        
        try:
            response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
            response_text = response.text.strip()
            
            if response_text.startswith("```"):
                response_text = response_text.split("\n", 1)[1]
                response_text = response_text.rsplit("```", 1)[0]
            
            result = json.loads(response_text)
            
            # Add affected vendors to each risk
            risks = result.get("risks", [])
            for risk in risks:
                dep_name = risk.get("dependency", "")
                risk["affected_vendors"] = [
                    av["vendor_id"] for av in affected_vendors 
                    if av["shared_dependency"] == dep_name
                ]
            
            result_data = {
                "score": min(100, max(0, result.get("overall_score", 30))),
                "level": result.get("overall_level", "LOW"),
                "confidence": _avg_confidence(risks),
                "cadence": MONITORING_CADENCE["fourth_party"],
                "sources": list(dep_news.keys()),
                "summary": result.get("summary", ""),
                "risks": risks,
                "affected_vendors": affected_vendors
            }
            
            log_decision(
                vendor_id=vendor["vendor_id"],
                vendor_name=vendor["name"],
                module="fourth_party_risk",
                input_summary=f"Dependencies: {dependencies}, Risky: {list(dep_news.keys())}",
                score=result_data["score"],
                level=result_data["level"],
                confidence=result_data["confidence"],
                details={"affected_vendors": [av["vendor_id"] for av in affected_vendors]}
            )
            
            return result_data
            
        except Exception as e:
            logger.error(f"Fourth-party analysis failed for {vendor['name']}: {e}")
            # Fallback
            score = 40 if has_risky_deps else 10
            return {
                "score": score,
                "level": get_risk_level(score),
                "confidence": 50,
                "cadence": MONITORING_CADENCE["fourth_party"],
                "sources": list(dep_news.keys()),
                "summary": f"Fourth-party analysis unavailable: {str(e)}",
                "risks": [],
                "affected_vendors": affected_vendors
            }
    else:
        # No risky deps — low score
        return {
            "score": 10,
            "level": "LOW",
            "confidence": 85,
            "cadence": MONITORING_CADENCE["fourth_party"],
            "sources": dependencies,
            "summary": f"No negative signals detected for {vendor['name']}'s dependencies: {', '.join(dependencies)}.",
            "risks": [],
            "affected_vendors": []
        }


def _avg_confidence(risks: list) -> int:
    if not risks:
        return 85
    confidences = [r.get("confidence", 50) for r in risks]
    return round(sum(confidences) / len(confidences))
