"""
FairTrace - Bias Detection Engine
All math happens here. No ML knowledge needed to read this.
Each function does ONE job and returns a simple result.
"""

import pandas as pd
import numpy as np
from scipy.stats import chi2_contingency, pearsonr


def load_csv(file_bytes):
    """Read uploaded CSV file into a pandas DataFrame."""
    import io
    try:
        df = pd.read_csv(io.BytesIO(file_bytes))
        # Clean column names - remove spaces
        df.columns = df.columns.str.strip()
        return df, None
    except Exception as e:
        return None, str(e)


def calculate_dir(df, protected_col, outcome_col, positive_val):
    """
    Disparate Impact Ratio (DIR)
    Formula: (positive_rate_of_worst_group) / (positive_rate_of_best_group)
    Legal minimum: 0.80 (EEOC 80% Rule)
    Below 0.80 = presumptive discrimination
    """
    groups = df[protected_col].dropna().unique()
    if len(groups) < 2:
        return None, "Need at least 2 groups in protected column"

    rates = {}
    for group in groups:
        subset = df[df[protected_col] == group]
        if len(subset) == 0:
            continue
        positive_count = (subset[outcome_col] == positive_val).sum()
        rates[group] = positive_count / len(subset)

    if not rates:
        return None, "Could not compute rates"

    max_rate = max(rates.values())
    min_rate = min(rates.values())

    if max_rate == 0:
        return 1.0, None  # No positives at all, no bias detectable

    dir_value = round(min_rate / max_rate, 3)
    return dir_value, None


def calculate_spd(df, protected_col, outcome_col, positive_val):
    """
    Statistical Parity Difference (SPD)
    Formula: positive_rate_advantaged - positive_rate_disadvantaged
    Ideal value: 0.0 (perfectly equal)
    Above 0.2 = significant concern
    """
    groups = df[protected_col].dropna().unique()
    rates = {}
    for group in groups:
        subset = df[df[protected_col] == group]
        if len(subset) == 0:
            continue
        positive_count = (subset[outcome_col] == positive_val).sum()
        rates[group] = positive_count / len(subset)

    if len(rates) < 2:
        return None, "Need at least 2 groups"

    max_rate = max(rates.values())
    min_rate = min(rates.values())
    spd_value = round(max_rate - min_rate, 3)
    return spd_value, None


def get_group_stats(df, protected_col, outcome_col, positive_val):
    """
    Get per-group breakdown: count, positive rate, etc.
    This powers the bar chart in the UI.
    """
    groups = df[protected_col].dropna().unique()
    stats = []

    rates = {}
    for group in groups:
        subset = df[df[protected_col] == group]
        positive_count = int((subset[outcome_col] == positive_val).sum())
        total = len(subset)
        rate = round(positive_count / total * 100, 1) if total > 0 else 0
        rates[str(group)] = rate / 100
        stats.append({
            "group": str(group),
            "total": total,
            "positive": positive_count,
            "rate_pct": rate
        })

    # Mark advantaged and disadvantaged
    if stats:
        max_rate = max(s["rate_pct"] for s in stats)
        min_rate = min(s["rate_pct"] for s in stats)
        for s in stats:
            if s["rate_pct"] == max_rate:
                s["status"] = "advantaged"
            elif s["rate_pct"] == min_rate:
                s["status"] = "disadvantaged"
            else:
                s["status"] = "neutral"

    return stats


def get_confidence(df, protected_col):
    """
    Sample size confidence scoring using chi-squared test logic.
    Low confidence = don't act on findings, sample too small.
    """
    groups = df[protected_col].dropna().unique()
    min_n = min(len(df[df[protected_col] == g]) for g in groups)

    if min_n < 30:
        return "low", min_n
    elif min_n < 100:
        return "moderate", min_n
    else:
        return "high", min_n


def get_severity(dir_value, confidence):
    """
    Convert DIR + confidence into severity level.
    Low confidence = never show Critical even if DIR is terrible.
    """
    if confidence == "low":
        return "insufficient_data"
    if dir_value < 0.6:
        return "critical"
    elif dir_value < 0.8:
        return "medium"
    elif dir_value < 0.9:
        return "low"
    else:
        return "clear"


def count_flagged(df, protected_col, outcome_col, positive_val):
    """
    Count decisions that need human review.
    Logic: how many more positives would the disadvantaged group have
    if they were treated at the same rate as the advantaged group?
    These are the 'flagged' decisions.
    """
    groups = df[protected_col].dropna().unique()
    rates = {}
    counts = {}
    for group in groups:
        subset = df[df[protected_col] == group]
        positive_count = (subset[outcome_col] == positive_val).sum()
        rates[str(group)] = positive_count / len(subset) if len(subset) > 0 else 0
        counts[str(group)] = {"total": len(subset), "positive": int(positive_count)}

    if len(rates) < 2:
        return 0

    max_rate = max(rates.values())
    max_group = max(rates, key=rates.get)
    min_group = min(rates, key=rates.get)

    disadvantaged_total = counts[min_group]["total"]
    disadvantaged_actual = counts[min_group]["positive"]
    expected_if_fair = round(disadvantaged_total * max_rate)
    flagged = max(0, expected_if_fair - disadvantaged_actual)
    return flagged


def detect_proxies(df, protected_col, outcome_col):
    """
    Proxy bias detection using Pearson correlation.
    Finds numeric columns that correlate with the protected attribute.
    If Gender is removed but Age is correlated with Gender,
    the model still learns gender indirectly through Age.
    """
    groups = df[protected_col].dropna().unique()
    if len(groups) != 2:
        return []  # Only works cleanly for binary protected attributes

    # Encode protected attribute as 0/1
    encoded = df[protected_col].map({groups[0]: 0, groups[1]: 1})
    proxies = []

    for col in df.columns:
        if col in [protected_col, outcome_col]:
            continue
        try:
            numeric_vals = pd.to_numeric(df[col], errors='coerce')
            if numeric_vals.isna().mean() > 0.5:
                continue  # Skip columns that are mostly non-numeric

            combined = pd.DataFrame({"feature": numeric_vals, "protected": encoded}).dropna()
            if len(combined) < 20:
                continue

            r, p_value = pearsonr(combined["feature"], combined["protected"])

            if abs(r) > 0.25:  # Meaningful correlation threshold
                strength = "Strong" if abs(r) > 0.5 else "Moderate"
                proxies.append({
                    "column": col,
                    "correlation": round(r, 3),
                    "strength": strength,
                    "direction": "positive" if r > 0 else "negative"
                })
        except Exception:
            continue

    # Sort by absolute correlation strength
    proxies.sort(key=lambda x: abs(x["correlation"]), reverse=True)
    return proxies[:5]  # Return top 5 at most


def run_full_analysis(df, protected_col, outcome_col, positive_val):
    """
    Master function - runs all algorithms and returns one clean result dict.
    This is what the API endpoint calls.
    """
    dir_value, dir_err = calculate_dir(df, protected_col, outcome_col, positive_val)
    spd_value, spd_err = calculate_spd(df, protected_col, outcome_col, positive_val)
    confidence, min_n = get_confidence(df, protected_col)
    group_stats = get_group_stats(df, protected_col, outcome_col, positive_val)
    proxies = detect_proxies(df, protected_col, outcome_col)
    flagged = count_flagged(df, protected_col, outcome_col, positive_val)

    severity = get_severity(dir_value if dir_value else 1.0, confidence)

    # Find advantaged/disadvantaged group names
    disadvantaged = next((s["group"] for s in group_stats if s.get("status") == "disadvantaged"), "Unknown")
    advantaged = next((s["group"] for s in group_stats if s.get("status") == "advantaged"), "Unknown")

    # Legal regulation check
    regulations = []
    if dir_value and dir_value < 0.8:
        regulations = [
        "EU AI Act (High-Risk AI)",
        "US EEOC 80% Rule",
        "UK Equality Act 2010",
        "India DPDP Act 2023 — Automated Decision Accountability",
        "India Constitution Article 15 & 16 — Non-Discrimination"
    ]
    else:
        regulations = [
        "EU AI Act — Monitoring Recommended",
        "India DPDP Act 2023 — Monitoring Recommended"
    ]

    return {
        "dir": dir_value,
        "spd": spd_value,
        "confidence": confidence,
        "min_n": min_n,
        "severity": severity,
        "flagged": flagged,
        "total": len(df),
        "group_stats": group_stats,
        "proxies": proxies,
        "disadvantaged": disadvantaged,
        "advantaged": advantaged,
        "regulations": regulations,
        "protected_col": protected_col,
        "outcome_col": outcome_col,
        "positive_val": positive_val,
    }