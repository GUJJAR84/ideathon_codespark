import json
import logging
from google import genai
from config import GEMINI_API_KEY, GEMINI_MODEL, MONITORING_CADENCE, get_risk_level
from audit_logger import log_decision
from datetime import datetime

logger = logging.getLogger("vendorguard.financial")


client = genai.Client(api_key=GEMINI_API_KEY)


FINANCIAL_PROMPT = """You are a financial risk analyst evaluating the financial health of a bank vendor.

Vendor: "{vendor_name}" (Category: {category})

Financial Data:
- Revenue Trend (last 4 quarters, % change): {revenue_trend}
- Current Credit Rating: {credit_rating}
- Previous Credit Rating: {previous_credit_rating}

Analyze the financial health and identify any red flags:
1. Revenue trajectory — is it stable, growing, or declining?
2. Credit rating changes — any downgrades?
3. Overall financial viability — can this vendor sustain operations?

Respond ONLY in this exact JSON format (no markdown, no code blocks):
{{
  "overall_score": <0-100 financial risk score, 0=very healthy, 100=imminent failure>,
  "overall_level": "<CRITICAL/HIGH/MEDIUM/LOW>",
  "summary": "<2-3 sentence financial health assessment>",
  "flags": [
    "<specific financial red flag or positive indicator>"
  ],
  "confidence": <0-100>,
  "analysis": "<detailed 2-3 paragraph analysis of the vendor's financial position, future outlook, and implications for the bank>"
}}

Be precise. Consider industry benchmarks for the vendor's category.
"""


def score_financial_health(vendor: dict) -> dict:
    """Assess vendor's financial health using rule-based scoring + Gemini analysis."""
    
    financials = vendor.get("financials", {})
    revenue_trend = financials.get("revenue_trend", [])
    credit_rating = financials.get("credit_rating", "N/A")
    previous_credit_rating = financials.get("previous_credit_rating", credit_rating)
    
    # ---------- Rule-based pre-scoring ----------
    rule_score = 0
    rule_flags = []
    
    # Revenue trend analysis
    if len(revenue_trend) >= 3:
        declining_quarters = sum(1 for r in revenue_trend if r < 0)
        if declining_quarters >= 3:
            rule_score += 35
            rule_flags.append(f"Revenue declining {declining_quarters} out of {len(revenue_trend)} quarters")
        elif declining_quarters >= 2:
            rule_score += 20
            rule_flags.append(f"Revenue declining {declining_quarters} out of {len(revenue_trend)} quarters")
        
        # Accelerating decline
        if len(revenue_trend) >= 2 and revenue_trend[-1] < revenue_trend[-2] < 0:
            rule_score += 15
            rule_flags.append("Revenue decline is accelerating")
    
    # Credit rating analysis
    rating_order = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "CC", "C", "D"]
    if credit_rating in rating_order and previous_credit_rating in rating_order:
        current_idx = rating_order.index(credit_rating)
        previous_idx = rating_order.index(previous_credit_rating)
        if current_idx > previous_idx:
            downgrade_steps = current_idx - previous_idx
            rule_score += downgrade_steps * 15
            rule_flags.append(f"Credit downgraded from {previous_credit_rating} to {credit_rating}")
    
    # Low credit rating
    if credit_rating in ["BB", "B", "CCC", "CC", "C", "D"]:
        rule_score += 20
        rule_flags.append(f"Below investment grade credit rating: {credit_rating}")
    
    rule_score = min(100, rule_score)
    
    # ---------- Gemini analysis for explanation ----------
    prompt = FINANCIAL_PROMPT.format(
        vendor_name=vendor["name"],
        category=vendor.get("category", "Unknown"),
        revenue_trend=str(revenue_trend),
        credit_rating=credit_rating,
        previous_credit_rating=previous_credit_rating
    )
    
    try:
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        response_text = response.text.strip()
        
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1]
            response_text = response_text.rsplit("```", 1)[0]
        
        result = json.loads(response_text)
        
        # Blend rule-based and AI scores (60% rule, 40% AI) for reliability
        ai_score = result.get("overall_score", 50)
        blended_score = round(rule_score * 0.6 + ai_score * 0.4)
        blended_score = min(100, max(0, blended_score))
        
        # Merge flags
        all_flags = list(set(rule_flags + result.get("flags", [])))
        
        result_data = {
            "score": blended_score,
            "level": get_risk_level(blended_score),
            "confidence": result.get("confidence", 80),
            "cadence": MONITORING_CADENCE["financial_health"],
            "sources": ["CRISIL Rating", "Vendor Quarterly Filing", "Financial Analysis Model"],
            "flags": all_flags,
            "summary": result.get("summary", ""),
            "analysis": result.get("analysis", "")
        }
        
        log_decision(
            vendor_id=vendor["vendor_id"],
            vendor_name=vendor["name"],
            module="financial_scorer",
            input_summary=f"Revenue: {revenue_trend}, Rating: {previous_credit_rating}->{credit_rating}",
            score=blended_score,
            level=result_data["level"],
            confidence=result_data["confidence"],
            details={"rule_score": rule_score, "ai_score": ai_score}
        )
        
        return result_data
        
    except Exception as e:
        logger.error(f"Financial analysis failed for {vendor['name']}: {e}")
        # Pure rule-based fallback
        return {
            "score": rule_score,
            "level": get_risk_level(rule_score),
            "confidence": 65,
            "cadence": MONITORING_CADENCE["financial_health"],
            "sources": ["Rule-based Financial Model (AI unavailable)"],
            "flags": rule_flags if rule_flags else ["No significant financial red flags detected"],
            "summary": f"Rule-based assessment: Financial risk score {rule_score}/100. {'; '.join(rule_flags) if rule_flags else 'No major concerns.'}",
            "analysis": f"AI analysis unavailable. Based on rules: {str(e)}"
        }
