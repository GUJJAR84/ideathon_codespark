import json
from google import genai
from config import GEMINI_API_KEY, GEMINI_MODEL
from datetime import datetime


client = genai.Client(api_key=GEMINI_API_KEY)


REPORT_PROMPT_SUMMARY = """You are a senior compliance officer at an Indian bank generating a vendor risk report.

Vendor Profile:
- Name: {vendor_name}
- Category: {category}
- Tier: {tier}
- Contract Value: ₹{contract_value}
- Dependencies: {dependencies}

Risk Assessment Summary:
- Overall Risk Score: {overall_score}/100 ({risk_level})
- News Sentiment Score: {news_score}/100 — {news_summary}
- Compliance Score: {compliance_score}/100 — {compliance_summary}
- Financial Health Score: {financial_score}/100 — {financial_summary}
- Fourth-Party Risk Score: {fourth_party_score}/100 — {fourth_party_summary}

Compliance Gaps Found: {compliance_gaps}
Financial Red Flags: {financial_flags}
Fourth-Party Risks: {fourth_party_risks}
Remediation Steps Suggested: {remediation}

Generate a professional compliance risk report in {language}.

Structure:
1. **Executive Summary** — 3-4 sentence overview
2. **Risk Assessment** — breakdown of each risk component
3. **Key Findings** — most critical issues
4. **Remediation Plan** — prioritized actions with timelines
5. **Data Sources** — where each finding came from

Write in a formal, professional tone suitable for presenting to the bank's Risk Management Committee.
Output the report in clean markdown format.
"""


REPORT_PROMPT_RBI_AUDIT = """You are a senior compliance officer at an Indian bank generating an RBI audit-ready vendor risk report.

This report must follow the structure mandated by RBI Master Direction on Outsourcing of IT Services (2023) and Master Direction on Managing Risks in Outsourcing of Financial Services by NBFCs (2017, updated 2023).

Vendor Profile:
- Name: {vendor_name}
- Category: {category}
- Tier Classification: {tier}
- Contract Value: ₹{contract_value}
- SLA Uptime Commitment: {sla_uptime}%
- Dependencies (Fourth Parties): {dependencies}

Risk Assessment:
- Overall Risk Score: {overall_score}/100 ({risk_level})
- News Sentiment: {news_score}/100 — {news_summary}
- Compliance: {compliance_score}/100 — {compliance_summary}
- Financial Health: {financial_score}/100 — {financial_summary}
- Fourth-Party Risk: {fourth_party_score}/100 — {fourth_party_summary}

Compliance Gaps: {compliance_gaps}
Financial Flags: {financial_flags}
Fourth-Party Risks: {fourth_party_risks}
Remediation: {remediation}

Generate the report in {language} with these EXACT sections:

1. **Vendor Profile & Classification** — vendor details, tier, and classification rationale
2. **Risk Assessment Summary** — composite score with component breakdown
3. **Regulatory Compliance Status** — mapped to specific RBI circulars:
   - RBI/2023-24/Master Direction on Outsourcing
   - RBI/DoS/2023/CO/CSITE — Cybersecurity framework
   - ISO 27001 / SOC 2 / PCI DSS compliance status
4. **SLA Performance Review** — uptime commitment vs actual
5. **Fourth-Party Dependencies** — sub-contractor risk assessment
6. **Remediation Plan with Timelines** — prioritized actions
7. **Audit Trail & Data Sources** — provenance of every finding

Write in formal regulatory language. Reference actual RBI circular numbers.
Output in clean markdown format.
"""


def generate_report(vendor: dict, assessment: dict, language: str = "english", format: str = "summary") -> str:
    """Generate a compliance report for a vendor."""
    
    # Extract assessment data
    components = assessment.get("components", {})
    news = components.get("news_sentiment", {})
    compliance = components.get("compliance", {})
    financial = components.get("financial_health", {})
    fourth_party = components.get("fourth_party", {})
    
    # Format contract value
    contract_value = vendor.get("tier_factors", {}).get("contract_value", 0)
    if contract_value >= 10000000:
        contract_str = f"{contract_value / 10000000:.1f} Crore"
    elif contract_value >= 100000:
        contract_str = f"{contract_value / 100000:.1f} Lakh"
    else:
        contract_str = str(contract_value)
    
    # Common params
    params = {
        "vendor_name": vendor["name"],
        "category": vendor.get("category", "Unknown"),
        "tier": vendor.get("tier", "STANDARD"),
        "contract_value": contract_str,
        "sla_uptime": vendor.get("sla_uptime", "N/A"),
        "dependencies": ", ".join(vendor.get("dependencies", [])) or "None",
        "overall_score": assessment.get("overall_risk_score", 0),
        "risk_level": assessment.get("risk_level", "UNKNOWN"),
        "news_score": news.get("score", 0),
        "news_summary": news.get("summary", "N/A"),
        "compliance_score": compliance.get("score", 0),
        "compliance_summary": compliance.get("summary", "N/A"),
        "financial_score": financial.get("score", 0),
        "financial_summary": financial.get("summary", "N/A"),
        "fourth_party_score": fourth_party.get("score", 0),
        "fourth_party_summary": fourth_party.get("summary", "N/A"),
        "compliance_gaps": _format_gaps(compliance.get("gaps", [])),
        "financial_flags": ", ".join(financial.get("flags", [])) or "None",
        "fourth_party_risks": _format_fourth_party(fourth_party.get("risks", [])),
        "remediation": _format_remediation(assessment.get("remediation", [])),
        "language": language,
    }
    
    # Select prompt template
    if format == "rbi_audit":
        prompt = REPORT_PROMPT_RBI_AUDIT.format(**params)
    else:
        prompt = REPORT_PROMPT_SUMMARY.format(**params)
    
    try:
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        report_text = response.text.strip()
        
        # Add metadata header
        header = f"""---
Report Type: {"RBI Audit-Ready" if format == "rbi_audit" else "Summary"}
Vendor: {vendor['name']}
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")}
Language: {language.title()}
Risk Level: {assessment.get('risk_level', 'UNKNOWN')}
Overall Score: {assessment.get('overall_risk_score', 0)}/100
---

"""
        return header + report_text
        
    except Exception as e:
        return f"""---
Report Type: Error
Vendor: {vendor['name']}
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")}
---

# Report Generation Error

Unable to generate report: {str(e)}

## Available Data Summary
- Overall Risk Score: {assessment.get('overall_risk_score', 'N/A')}/100
- Risk Level: {assessment.get('risk_level', 'UNKNOWN')}
- Compliance Gaps: {params['compliance_gaps']}
- Financial Flags: {params['financial_flags']}
"""


def _format_gaps(gaps: list) -> str:
    if not gaps:
        return "None"
    return "; ".join(g.get("finding", "") for g in gaps)


def _format_fourth_party(risks: list) -> str:
    if not risks:
        return "None"
    return "; ".join(f"{r.get('dependency', '?')}: {r.get('risk_event', '?')}" for r in risks)


def _format_remediation(remediations: list) -> str:
    if not remediations:
        return "None"
    return "; ".join(f"[{r.get('priority', '?')}] {r.get('action', '?')} (by {r.get('timeline', '?')})" for r in remediations)
