"""
graph/state.py
Defines AgentState — the single object that flows through
every LangGraph node. Think of it as the "memory" of the call.
"""

from typing import TypedDict, Optional, List, Any


class AgentState(TypedDict):
    # ── Identity ──────────────────────────────────────────────────
    call_id: str               # unique per call, used as Redis key
    lead: dict                 # full lead row from PostgreSQL

    # ── Conversation ──────────────────────────────────────────────
    messages: List[dict]       # [{role: user|assistant, content: str}]
    current_node: str          # last node that ran
    turn_count: int            # number of user messages so far

    # ── Flow Control ──────────────────────────────────────────────
    next_action: str           # continue | not_interested | objection | confirm | end
    objection_count: int       # how many times user objected

    # ── Extracted Data ────────────────────────────────────────────
    extracted_data: dict       # income, employment_type, existing_cards, spending_habits
    card_recommended: Optional[str]
    consent_given: bool

    # ── Meta ──────────────────────────────────────────────────────
    call_start_time: Optional[str]
    error: Optional[str]       # set if something goes wrong in a node


def initial_state(call_id: str, lead: dict) -> AgentState:
    """
    Factory — creates a fresh AgentState for a new call.
    Call this in /call/start to initialize the session.
    """
    from datetime import datetime
    return AgentState(
        call_id=call_id,
        lead=lead,
        messages=[],
        current_node="start",
        turn_count=0,
        next_action="continue",
        objection_count=0,
        extracted_data={},
        card_recommended=None,
        consent_given=False,
        call_start_time=datetime.utcnow().isoformat(),
        error=None,
    )