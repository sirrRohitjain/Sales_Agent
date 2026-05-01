"""
graph/graph_builder.py
Assembles the full LangGraph StateGraph.

The graph is compiled ONCE at startup and reused for all calls.
Each call uses AgentState stored in Redis between API requests —
we don't run the full graph in one shot. Instead:
  - /call/start  → runs intro_node
  - /call/respond → runs next_node based on current state
This gives us a truly multi-turn, stateful conversation.
"""

import logging
from langgraph.graph import StateGraph, END
from graph.state import AgentState
from graph.nodes import (
    intro_node,
    verify_interest_node,
    recommend_node,
    objection_node,
    confirm_node,
    save_to_db_node,
)
from graph.edges import (
    route_after_verify,
   # route_after_collect,
    route_after_recommend,
    route_after_objection,
)

logger = logging.getLogger(__name__)


def build_graph() -> StateGraph:
    """
    Build and compile the full conversation graph.
    Returns the compiled graph ready for invocation.
    """
    g = StateGraph(AgentState)

    # ── Register nodes ─────────────────────────────────────────────
    g.add_node("intro",            intro_node)
    g.add_node("verify_interest",  verify_interest_node)
    #g.add_node("collect_info",     collect_info_node)
    g.add_node("recommend",        recommend_node)
    g.add_node("objection",        objection_node)
    g.add_node("confirm",          confirm_node)
    g.add_node("save_to_db",       save_to_db_node)

    # ── Entry point ────────────────────────────────────────────────
    g.set_entry_point("intro")

    # ── Fixed edges ────────────────────────────────────────────────
    g.add_edge("intro",     "verify_interest")
    g.add_edge("confirm",   "save_to_db")
    g.add_edge("save_to_db", END)

    # ── Conditional edges ──────────────────────────────────────────
    g.add_conditional_edges(
        "verify_interest",
        route_after_verify,
        {"recommend": "recommend", END: END}   # was collect_info, now recommend
    )
    # g.add_conditional_edges(
    #     "collect_info",
    #     route_after_collect,
    #     {"collect_info": "collect_info", "recommend": "recommend"}
    # )
    g.add_conditional_edges(
        "recommend",
        route_after_recommend,
        {"objection": "objection", "confirm": "confirm"}
    )
    g.add_conditional_edges(
        "objection",
        route_after_objection,
        {"recommend": "recommend", END: END}
    )

    compiled = g.compile()
    logger.info("✅ LangGraph compiled successfully")
    return compiled


# ── Singleton — compiled once at startup ───────────────────────────
sales_graph = build_graph()
print(sales_graph.get_graph().draw_mermaid())  # Print Mermaid diagram to verify structure

# ── Node execution map for turn-by-turn API mode ──────────────────
# Instead of running the whole graph, we run ONE node per API call.
# The next node is determined by current_node + next_action in state.

NODE_FUNCTIONS = {
    "intro":           intro_node,
    "verify_interest": verify_interest_node,
    # "collect_info"  ← REMOVED (node no longer exists)
    "recommend":       recommend_node,
    "objection":       objection_node,
    "confirm":         confirm_node,
    "save_to_db":      save_to_db_node,
}

# Maps (current_node, next_action) → next node to run
TRANSITION_MAP = {
    ("intro",           "continue"):        "verify_interest",
    ("verify_interest", "continue"):        "recommend",   # was "collect_info" → now "recommend"
    ("verify_interest", "not_interested"):  None,          # END
    # ("collect_info", ...) ← ALL REMOVED
    ("recommend",       "confirm"):         "confirm",
    ("recommend",       "objection"):       "objection",
    ("recommend",       "continue"):        "confirm",
    ("objection",       "continue"):        "recommend",
    ("objection",       "end"):             None,          # END
    ("confirm",         "end"):             "save_to_db",
    ("save_to_db",      "end"):             None,          # END
}


def get_next_node(state: AgentState) -> str | None:
    """
    Given current state, return the name of the next node to run.
    Returns None when the conversation should end.
    """
    current = state.get("current_node", "intro")
    action  = state.get("next_action", "continue")

    # Special case: collect_info uses the edge function
    if current == "collect_info":
        from graph.edges import route_after_collect
        result = route_after_collect(state)
        return None if result == END else result

    key = (current, action)
    return TRANSITION_MAP.get(key, None)


def run_next_node(state: AgentState) -> tuple[AgentState, str | None]:
    """
    Determines and runs the next node for this conversation turn.

    Returns:
        (updated_state, next_node_name_or_None)
        None means conversation is over.
    """
    next_node = get_next_node(state)

    if next_node is None:
        return state, None

    node_fn = NODE_FUNCTIONS.get(next_node)
    if not node_fn:
        logger.error(f"No function found for node: {next_node}")
        return state, None

    updated_state = node_fn(state)
    return updated_state, next_node