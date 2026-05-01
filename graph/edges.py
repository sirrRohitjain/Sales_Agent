"""
graph/edges.py
Conditional edge functions for LangGraph.
Each function reads AgentState and returns the name of the next node.
"""

import logging
from langgraph.graph import END
from graph.state import AgentState

logger = logging.getLogger(__name__)

MAX_OBJECTIONS = 3
MAX_TURNS      = 20    # safety valve — end call if it goes too long


def route_after_verify(state: AgentState) -> str:
    """
    After verify_interest_node:
    - not_interested → END
    - continue       → recommend
    """
    action = state.get("next_action", "continue")

    if action == "not_interested":
        logger.info(f"[{state['call_id']}] Route: verify → END (not interested)")
        return END

    logger.info(f"[{state['call_id']}] Route: verify → recommend")
    return "recommend"



def route_after_recommend(state: AgentState) -> str:
    """
    After recommend_node:
    - objection → objection_node
    - anything else → confirm
    """
    action = state.get("next_action", "confirm")
    if action == "objection":
        logger.info(f"[{state['call_id']}] Route: recommend → objection")
        return "objection"
    logger.info(f"[{state['call_id']}] Route: recommend → confirm")
    return "confirm"


def route_after_objection(state: AgentState) -> str:
    """
    After objection_node:
    - end (>= 3 objections) → END
    - continue              → back to recommend
    """
    action = state.get("next_action", "continue")
    count  = state.get("objection_count", 0)

    if action == "end" or count >= MAX_OBJECTIONS:
        logger.info(f"[{state['call_id']}] Route: objection → END (max objections)")
        return END

    logger.info(f"[{state['call_id']}] Route: objection → recommend (retry)")
    return "recommend"


def route_after_confirm(state: AgentState) -> str:
    """
    After confirm_node:
    - Always goes to save_to_db (whether consent=True or False)
    """
    logger.info(f"[{state['call_id']}] Route: confirm → save_to_db")
    return "save_to_db"


def safety_check(state: AgentState) -> str:
    """
    Emergency route — if anything is broken or call went too long, end it.
    Wrap any node with this to add a safety valve.
    """
    if state.get("error"):
        logger.error(f"[{state['call_id']}] Safety check: error detected → END")
        return END
    if state.get("turn_count", 0) >= MAX_TURNS:
        logger.warning(f"[{state['call_id']}] Safety check: max turns reached → END")
        return END
    return "continue"