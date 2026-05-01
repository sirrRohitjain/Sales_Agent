"""
services/extractor.py
We only extract ONE thing from conversation: consent_given.
Everything else (income, score, employment) comes from the DB.
"""

TRACKED_FIELDS = ["consent_given", "best_call_time"]


def merge_extracted(existing: dict, new_data: dict) -> dict:
    merged = dict(existing)
    for key, value in new_data.items():
        if key not in TRACKED_FIELDS:
            continue  # silently ignore income, employment, spending etc.
        if value is not None and value != "":
            merged[key] = value
    return merged


def get_profile_for_recommendation(lead: dict) -> dict:
    """
    Build complete card recommendation profile from DB alone.
    No conversation data needed.
    """
    return {
        "income":          lead.get("income", 0),
        "credit_score":    lead.get("credit_score", 700),
        "employment_type": lead.get("employment_type", "salaried"),
        "age":             lead.get("age"),
        "city":            lead.get("city"),
    }