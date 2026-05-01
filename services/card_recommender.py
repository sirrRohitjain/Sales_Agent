"""
services/card_recommender.py
Fetches customer data directly from DB using lead_id,
then returns the best matching card.
No data is ever collected from the customer.
"""

import logging
from db.db_utils import get_lead_by_id

logger = logging.getLogger(__name__)

CARDS = [
    {
        "id": "platinum_travel",
        "name": "QuickBank Platinum Travel Card",
        "min_income": 80000,
        "min_credit_score": 750,
        "employment_types": ["salaried", "self_employed", "business"],
        "benefits": [
            "Complimentary airport lounge access (domestic + international)",
            "5x reward points on all flight and hotel bookings",
            "Zero forex markup on international transactions",
            "₹5,000 welcome bonus on first spend",
            "Travel insurance up to ₹1 crore",
        ],
        "annual_fee": 2999,
        "joining_fee": 0,
        "tagline": "Made for people who are always on the move",
    },
    {
        "id": "gold_rewards",
        "name": "QuickBank Gold Rewards Card",
        "min_income": 40000,
        "min_credit_score": 700,
        "employment_types": ["salaried", "self_employed", "business"],
        "benefits": [
            "3x reward points on shopping and dining",
            "5% cashback on fuel (up to ₹200/month)",
            "2 free movie tickets every month via BookMyShow",
            "Annual fee waived on spending ₹1.5L+ per year",
            "EMI conversion with 0% interest on select merchants",
        ],
        "annual_fee": 999,
        "joining_fee": 0,
        "tagline": "Rewards on everything you love",
    },
    {
        "id": "silver_cashback",
        "name": "QuickBank Silver Cashback Card",
        "min_income": 15000,
        "min_credit_score": 650,
        "employment_types": ["salaried", "self_employed", "student", "freelancer"],
        "benefits": [
            "1.5% cashback on all spends — no categories, no cap",
            "Zero annual fee, zero joining fee — truly free",
            "Instant EMI on purchases above ₹3,000",
            "Fuel surcharge waiver at all petrol stations",
            "Online fraud protection up to ₹50,000",
        ],
        "annual_fee": 0,
        "joining_fee": 0,
        "tagline": "Simple cashback on every rupee you spend",
    },
]


def recommend_card_for_lead(lead_id: str) -> dict:
    """
    Main function. Takes lead_id, fetches data from DB,
    returns the best card dict.

    Usage in recommend_node:
        card = recommend_card_for_lead(state["lead"]["id"])
    """
    # ── Fetch from DB ──────────────────────────────────────────────
    lead = get_lead_by_id(lead_id)

    if not lead:
        logger.error(f"Lead {lead_id} not found in DB. Defaulting to Silver card.")
        return _format_card(CARDS[-1])

    # ── Read values from DB ────────────────────────────────────────
    income       = _parse_int(lead.get("income", 0))
    credit_score = _parse_int(lead.get("credit_score", 650))
    employment   = str(lead.get("employment_type", "salaried")).lower().strip()

    logger.info(
        f"Recommending card for lead {lead_id} | "
        f"income={income} | score={credit_score} | employment={employment}"
    )

    # ── Filter eligible cards by income + credit score ─────────────
    eligible = [
        card for card in CARDS
        if income >= card["min_income"]
        and credit_score >= card["min_credit_score"]
    ]

    if not eligible:
        # Income or score too low — give basic card anyway
        logger.warning(f"Lead {lead_id} not eligible for any card. Offering Silver.")
        return _format_card(CARDS[-1])

    # ── Among eligible, match by employment type ───────────────────
    for card in eligible:
        if employment in card["employment_types"]:
            logger.info(f"Matched: {card['name']} for lead {lead_id}")
            return _format_card(card)

    # ── Default: highest eligible card ────────────────────────────
    logger.info(f"Default match: {eligible[0]['name']} for lead {lead_id}")
    return _format_card(eligible[0])


def get_all_cards() -> list[dict]:
    return [_format_card(c) for c in CARDS]


# ── Helpers ────────────────────────────────────────────────────────

def _parse_int(value) -> int:
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (ValueError, TypeError):
        return 0


def _format_card(card: dict) -> dict:
    fee_str = (
        "Zero annual fee — completely free"
        if card["annual_fee"] == 0
        else f"₹{card['annual_fee']}/year (first year free)"
    )
    return {
        "id":             card["id"],
        "name":           card["name"],
        "tagline":        card["tagline"],
        "benefits":       card["benefits"],
        "top_3_benefits": card["benefits"][:3],
        "fee":            fee_str,
    }