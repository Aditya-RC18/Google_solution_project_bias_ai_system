"""
FairTrace - Gemini AI Helper
Converts bias numbers into plain English for HR/Legal/Compliance teams.
Uses Google Gemini 1.5 Flash (FREE - no credit card needed).

HOW TO GET YOUR FREE API KEY:
1. Go to https://aistudio.google.com
2. Click "Get API Key" (top left)
3. Sign in with your Google account
4. Create API key - copy it
5. Paste it in .env file as GEMINI_API_KEY=your_key_here
"""

import os
import google.generativeai as genai

def get_gemini_explanation(analysis_result: dict) -> str:
    """
    Takes bias analysis numbers and asks Gemini to explain them
    in plain English for a non-technical HR manager.
    Returns a 3-paragraph plain English report.
    """
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key or api_key == "your_gemini_api_key_here":
        # Return a fallback explanation if no API key set
        return _fallback_explanation(analysis_result)

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")

        dir_val = analysis_result.get("dir", "N/A")
        spd_val = analysis_result.get("spd", "N/A")
        severity = analysis_result.get("severity", "unknown")
        flagged = analysis_result.get("flagged", 0)
        total = analysis_result.get("total", 0)
        disadvantaged = analysis_result.get("disadvantaged", "Group A")
        advantaged = analysis_result.get("advantaged", "Group B")
        protected_col = analysis_result.get("protected_col", "protected attribute")
        confidence = analysis_result.get("confidence", "moderate")
        min_n = analysis_result.get("min_n", 0)
        proxies = analysis_result.get("proxies", [])
        proxy_names = [p["column"] for p in proxies] if proxies else []

        prompt = f"""You are FairTrace, an AI bias auditing assistant. 
A non-technical HR manager or compliance officer is reading this report.
They have NO machine learning knowledge. Write in plain, clear English.

Write EXACTLY 3 paragraphs with NO headers, NO bullet points, NO markdown:

Paragraph 1 - What is happening: Explain what the data shows about {protected_col} in simple terms. 
Paragraph 2 - Why it matters legally: Mention EU AI Act and EEOC 80% Rule by name. Include the specific numbers.
Paragraph 3 - Three immediate actions they must take right now. Be specific and actionable.

DATA TO EXPLAIN:
- Protected attribute being analyzed: {protected_col}
- Disadvantaged group: "{disadvantaged}" — gets positive outcomes only {analysis_result.get('disadvantaged_rate', 'less often')}
- Advantaged group: "{advantaged}" — gets positive outcomes more often
- Disparate Impact Ratio: {dir_val} (legal minimum is 0.80 — below this is presumptive discrimination)
- Statistical Parity Difference: {spd_val} (ideal is 0.00)
- Severity level: {severity}
- Decisions flagged for human review: {flagged} out of {total} total
- Statistical confidence: {confidence} (minimum group size: {min_n} records)
- Proxy features detected: {', '.join(proxy_names) if proxy_names else 'None detected'}

IMPORTANT RULES:
- Keep it under 200 words total
- Never use jargon without explaining it
- End the LAST sentence with exactly: "⚠️ This is a statistical risk signal, not a legal determination. Consult your legal counsel before taking any action."
- If confidence is 'low', warn strongly that the sample size is too small to act on"""

        response = model.generate_content(prompt)
        return response.text.strip()

    except Exception as e:
        print(f"Gemini API error: {e}")
        return _fallback_explanation(analysis_result)


def _fallback_explanation(result: dict) -> str:
    """
    If Gemini API key is not set or fails, return a template explanation.
    This ensures the app still works during demo even without API key.
    """
    dir_val = result.get("dir", "N/A")
    severity = result.get("severity", "unknown")
    flagged = result.get("flagged", 0)
    total = result.get("total", 0)
    disadvantaged = result.get("disadvantaged", "the disadvantaged group")
    advantaged = result.get("advantaged", "the advantaged group")
    protected_col = result.get("protected_col", "the protected attribute")
    confidence = result.get("confidence", "moderate")

    if severity == "critical":
        para1 = f"The analysis of {protected_col} reveals a serious disparity in outcomes. The group '{disadvantaged}' is receiving significantly fewer positive decisions compared to '{advantaged}', with a Disparate Impact Ratio of {dir_val} — well below the legal minimum of 0.80."
        para2 = f"This finding triggers concern under the EU AI Act Article 10 (high-risk AI systems) and the US EEOC 80% Rule, which considers any ratio below 0.80 as presumptive discrimination. With {flagged} out of {total} decisions flagged for review, the real-world impact on affected individuals is substantial."
        para3 = f"Immediate actions required: First, suspend automated screening decisions for {protected_col} pending manual review. Second, assign a named compliance officer to review the {flagged} flagged cases within 48 hours. Third, engage your legal team before the next hiring or decision cycle begins. ⚠️ This is a statistical risk signal, not a legal determination. Consult your legal counsel before taking any action."
    elif severity == "medium":
        para1 = f"The analysis shows a moderate disparity in outcomes related to {protected_col}. The group '{disadvantaged}' is receiving positive decisions at a lower rate than '{advantaged}', with a Disparate Impact Ratio of {dir_val}, which falls below the legal safety threshold of 0.80."
        para2 = f"Under the EU AI Act and EEOC 80% Rule, a ratio of {dir_val} is below the minimum acceptable level and warrants formal review. {flagged} decisions have been flagged as statistically anomalous — these are cases where the outcome differs from what would be expected given the applicant's other characteristics."
        para3 = f"Recommended actions: First, initiate a formal internal audit of the screening criteria related to {protected_col}. Second, have a named owner review the {flagged} flagged decisions within one week. Third, consult your legal team to assess exposure before the next decision cycle. ⚠️ This is a statistical risk signal, not a legal determination. Consult your legal counsel before taking any action."
    elif severity == "insufficient_data":
        para1 = f"The system detected a potential disparity in {protected_col} outcomes, but the dataset is too small to draw reliable conclusions. With fewer than 30 records per group, statistical results may reflect random variation rather than systematic bias."
        para2 = f"EU AI Act requirements and EEOC guidelines require sufficiently large datasets to produce valid audit findings. Acting on low-confidence findings can lead to incorrect policy changes. The current sample size limits the reliability of these results."
        para3 = f"Recommended actions: First, collect more decision data — aim for at least 100 records per group before running a formal audit. Second, document this preliminary analysis in your compliance records. Third, schedule a re-audit once sufficient data is available. ⚠️ This is a statistical risk signal, not a legal determination. Consult your legal counsel before taking any action."
    else:
        para1 = f"The analysis of {protected_col} shows outcomes that are within acceptable fairness ranges. The Disparate Impact Ratio of {dir_val} is above the legal minimum of 0.80, suggesting no immediate evidence of systematic discrimination in this dataset."
        para2 = f"Under EU AI Act monitoring requirements and EEOC guidelines, systems that pass the 80% threshold still require ongoing monitoring. Fairness today does not guarantee fairness as data distributions change over time."
        para3 = f"Recommended actions: First, schedule regular re-audits — at minimum quarterly for high-stakes decision systems. Second, continue tracking drift over time using the Bias Drift Tracker. Third, document this audit in your compliance records as evidence of proactive monitoring. ⚠️ This is a statistical risk signal, not a legal determination. Consult your legal counsel before taking any action."

    return f"{para1}\n\n{para2}\n\n{para3}"