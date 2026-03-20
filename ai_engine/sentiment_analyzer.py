import json
import logging
from google import genai
from config import GEMINI_API_KEY, GEMINI_MODEL, get_risk_level, MONITORING_CADENCE
from audit_logger import log_decision
from datetime import datetime

logger = logging.getLogger("vendorguard.sentiment")


client = genai.Client(api_key=GEMINI_API_KEY)


SENTIMENT_PROMPT = """You are a vendor risk analyst specializing in news-based risk assessment for the banking sector.

Analyze the following news headlines about vendor "{vendor_name}" (category: {category}).

News Headlines:
{news_headlines}

For each headline, assess:
1. Risk category (cybersecurity / financial / legal / reputational / operational / regulatory)
2. Severity (CRITICAL / HIGH / MEDIUM / LOW)
3. Confidence score (0-100) — how confident you are in this assessment
4. Whether human review is recommended (true if confidence < 70)

Then provide an OVERALL assessment.

Respond ONLY in this exact JSON format (no markdown, no code blocks):
{{
  "overall_score": <0-100 risk score, 0=safe, 100=extremely risky>,
  "overall_level": "<CRITICAL/HIGH/MEDIUM/LOW>",
  "summary": "<2-3 sentence summary of the vendor's news risk profile>",
  "findings": [
    {{
      "finding": "<description of the risk found>",
      "risk_category": "<cybersecurity/financial/legal/reputational/operational/regulatory>",
      "confidence": <0-100>,
      "source": "<which headline this finding is based on>",
      "requires_human_review": <true/false>
    }}
  ]
}}

If there are no negative news items, return a low score with appropriate findings.
Be precise and analytical. Base your assessment ONLY on the provided headlines.
"""


def analyze_sentiment(vendor: dict) -> dict:
    """Analyze news sentiment for a vendor and return risk assessment."""
    
    news = vendor.get("recent_news", [])
    
    # If no news available, return low risk
    if not news:
        return {
            "score": 10,
            "level": "LOW",
            "confidence": 90,
            "cadence": MONITORING_CADENCE["news_sentiment"],
            "last_checked": datetime.now().isoformat(),
            "sources": [],
            "summary": "No recent news found for this vendor.",
            "findings": []
        }
    
    # Format headlines for prompt
    headlines_text = "\n".join(f"- {headline}" for headline in news)
    
    # Build prompt
    prompt = SENTIMENT_PROMPT.format(
        vendor_name=vendor["name"],
        category=vendor.get("category", "Unknown"),
        news_headlines=headlines_text
    )
    
    try:
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        response_text = response.text.strip()
        
        # Clean response — remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1]
            response_text = response_text.rsplit("```", 1)[0]
        
        result = json.loads(response_text)
        
        # Extract source names from headlines
        sources = []
        for headline in news:
            parts = headline.rsplit(" - ", 1)
            if len(parts) > 1:
                sources.append(parts[1])
        
        result_data = {
            "score": min(100, max(0, result.get("overall_score", 50))),
            "level": result.get("overall_level", get_risk_level(result.get("overall_score", 50))),
            "confidence": _avg_confidence(result.get("findings", [])),
            "cadence": MONITORING_CADENCE["news_sentiment"],
            "last_checked": datetime.now().isoformat(),
            "sources": list(set(sources)) if sources else ["News Analysis"],
            "summary": result.get("summary", ""),
            "findings": result.get("findings", [])
        }
        
        # Audit trail
        log_decision(
            vendor_id=vendor["vendor_id"],
            vendor_name=vendor["name"],
            module="sentiment_analyzer",
            input_summary=f"{len(news)} headlines analyzed",
            score=result_data["score"],
            level=result_data["level"],
            confidence=result_data["confidence"],
            requires_human_review=any(f.get("requires_human_review") for f in result_data["findings"]),
        )
        
        return result_data
        
    except Exception as e:
        logger.error(f"Sentiment analysis failed for {vendor['name']}: {e}")
        log_decision(
            vendor_id=vendor["vendor_id"],
            vendor_name=vendor["name"],
            module="sentiment_analyzer",
            input_summary=f"ERROR: {str(e)[:200]}",
            score=50, level="MEDIUM", confidence=30,
            requires_human_review=True,
        )
        return {
            "score": 50,
            "level": "MEDIUM",
            "confidence": 30,
            "cadence": MONITORING_CADENCE["news_sentiment"],
            "last_checked": datetime.now().isoformat(),
            "sources": ["Analysis Error"],
            "summary": f"Unable to complete sentiment analysis: {str(e)}",
            "findings": [{
                "finding": "Sentiment analysis could not be completed",
                "risk_category": "operational",
                "confidence": 30,
                "source": "System",
                "requires_human_review": True
            }]
        }


def _avg_confidence(findings: list) -> int:
    """Calculate average confidence across findings."""
    if not findings:
        return 90
    confidences = [f.get("confidence", 50) for f in findings]
    return round(sum(confidences) / len(confidences))
