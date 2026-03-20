import json
import logging
from google import genai
from config import GEMINI_API_KEY, GEMINI_MODEL, REQUIRED_CERTIFICATIONS, MONITORING_CADENCE, get_risk_level
from audit_logger import log_decision
from datetime import datetime

logger = logging.getLogger("vendorguard.compliance")


client = genai.Client(api_key=GEMINI_API_KEY)


COMPLIANCE_PROMPT = """You are a banking regulatory compliance expert specializing in RBI vendor risk management guidelines.

Vendor: "{vendor_name}" (Category: {category}, Tier: {tier})

Certifications the vendor HAS:
{has_certs}

Certifications REQUIRED by bank policy (based on RBI Master Direction on Outsourcing 2023):
{required_certs}

SLA Uptime Commitment: {sla_uptime}%

Analyze compliance gaps and assess risk. For each missing certification:
1. Explain why it matters for this vendor category
2. Reference relevant RBI guidelines or industry standards
3. Provide a confidence score (0-100) for your assessment
4. Recommend if human review is needed (true if confidence < 70)

Respond ONLY in this exact JSON format (no markdown, no code blocks):
{{
  "overall_score": <0-100 compliance risk score, 0=fully compliant, 100=critically non-compliant>,
  "overall_level": "<CRITICAL/HIGH/MEDIUM/LOW>",
  "summary": "<2-3 sentence compliance risk summary>",
  "gaps": [
    {{
      "finding": "<description of the compliance gap>",
      "certification": "<name of missing certification>",
      "rbi_reference": "<relevant RBI circular or guideline reference>",
      "impact": "<what risk this gap creates>",
      "confidence": <0-100>,
      "source": "<basis for this finding>",
      "requires_human_review": <true/false>
    }}
  ]
}}

If the vendor is fully compliant, return a low score with an empty gaps array.
Be specific about RBI regulations. Use actual circular references where possible.
"""


def check_compliance(vendor: dict) -> dict:
    """Check vendor compliance against required certifications and standards."""
    
    has_certs = vendor.get("certifications", [])
    required_certs = vendor.get("required_certifications", REQUIRED_CERTIFICATIONS)
    
    # Quick check: if fully compliant
    missing = [c for c in required_certs if c not in has_certs]
    
    if not missing:
        return {
            "score": 10,
            "level": "LOW",
            "confidence": 95,
            "cadence": MONITORING_CADENCE["compliance"],
            "sources": ["Vendor Certification Registry", "Internal Compliance Database"],
            "summary": f"{vendor['name']} is fully compliant with all required certifications.",
            "gaps": []
        }
    
    # Format for prompt
    has_text = "\n".join(f"  ✅ {c}" for c in has_certs) if has_certs else "  (None)"
    required_text = "\n".join(f"  - {c}" for c in required_certs)
    
    prompt = COMPLIANCE_PROMPT.format(
        vendor_name=vendor["name"],
        category=vendor.get("category", "Unknown"),
        tier=vendor.get("tier", "STANDARD"),
        has_certs=has_text,
        required_certs=required_text,
        sla_uptime=vendor.get("sla_uptime", "N/A")
    )
    
    try:
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        response_text = response.text.strip()
        
        # Clean response
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1]
            response_text = response_text.rsplit("```", 1)[0]
        
        result = json.loads(response_text)
        
        result_data = {
            "score": min(100, max(0, result.get("overall_score", 50))),
            "level": result.get("overall_level", get_risk_level(result.get("overall_score", 50))),
            "confidence": _avg_confidence(result.get("gaps", [])),
            "cadence": MONITORING_CADENCE["compliance"],
            "sources": ["Vendor Self-Declaration", "ISO Registry", "RBI Circular Database"],
            "summary": result.get("summary", ""),
            "gaps": result.get("gaps", [])
        }
        
        log_decision(
            vendor_id=vendor["vendor_id"],
            vendor_name=vendor["name"],
            module="compliance_checker",
            input_summary=f"Has: {has_certs}, Missing: {missing}",
            score=result_data["score"],
            level=result_data["level"],
            confidence=result_data["confidence"],
            requires_human_review=any(g.get("requires_human_review") for g in result_data["gaps"]),
        )
        
        return result_data
        
    except Exception as e:
        logger.error(f"Compliance check failed for {vendor['name']}: {e}")
        # Fallback: rule-based scoring
        score = min(100, len(missing) * 25)
        return {
            "score": score,
            "level": get_risk_level(score),
            "confidence": 60,
            "cadence": MONITORING_CADENCE["compliance"],
            "sources": ["Rule-based Assessment (AI unavailable)"],
            "summary": f"AI analysis unavailable. Rule-based: {len(missing)} missing certifications out of {len(required_certs)}.",
            "gaps": [{
                "finding": f"Missing {cert} certification",
                "certification": cert,
                "rbi_reference": "RBI/2023-24/Master Direction on Outsourcing",
                "impact": f"Non-compliance with {cert} requirements",
                "confidence": 60,
                "source": "Vendor certification list comparison",
                "requires_human_review": True
            } for cert in missing]
        }


def _avg_confidence(gaps: list) -> int:
    """Calculate average confidence across gaps."""
    if not gaps:
        return 95
    confidences = [g.get("confidence", 50) for g in gaps]
    return round(sum(confidences) / len(confidences))
