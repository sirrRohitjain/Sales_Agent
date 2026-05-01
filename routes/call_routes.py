"""
routes/call_routes.py
All API endpoints for managing calls.

POST /call/start    — Initialize a new call session
POST /call/respond  — Submit user's reply, get agent's next reply
POST /call/end      — Forcefully end a call (e.g., user hung up)
GET  /call/{id}/state      — Debug: see full AgentState
GET  /call/{id}/transcript — Get full conversation transcript
GET  /calls/active         — How many calls are active right now
"""

import uuid
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from graph.state import initial_state
from graph.graph_builder import run_next_node, NODE_FUNCTIONS
from services.session_manager import (
    save_state, get_state, delete_state,
    lock_lead, unlock_lead, refresh_ttl,
    get_active_call_count, session_exists
)
from db.db_utils import (
    get_lead_by_id, get_next_lead,
    create_call_record, update_call_outcome,
    get_full_transcript, save_transcript_chunk,
    update_lead_status
)

router  = APIRouter(prefix="/call", tags=["Calls"])
logger  = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
#  REQUEST / RESPONSE MODELS
# ══════════════════════════════════════════════════════════════════

class StartCallRequest(BaseModel):
    lead_id: str | None = None   # if None, auto-picks next priority lead

class StartCallResponse(BaseModel):
    call_id: str
    lead_name: str
    lead_phone: str
    agent_reply: str             # first thing agent says
    current_node: str

class RespondRequest(BaseModel):
    call_id: str
    user_text: str               # transcribed user speech (from STT)

class RespondResponse(BaseModel):
    call_id: str
    agent_reply: str
    current_node: str
    is_done: bool                # True = call should end now
    extracted_so_far: dict       # what we've collected

class EndCallRequest(BaseModel):
    call_id: str
    reason: str = "user_hangup"  # user_hangup | timeout | error


# ══════════════════════════════════════════════════════════════════
#  POST /call/start
# ══════════════════════════════════════════════════════════════════

@router.post("/start", response_model=StartCallResponse)
async def start_call(req: StartCallRequest):
    """
    Initialize a new call:
    1. Pick lead from DB (or use provided lead_id)
    2. Lock lead to prevent duplicate calls
    3. Create AgentState and run intro_node
    4. Save state to Redis
    5. Return first agent reply
    """
    # ── Pick lead ──────────────────────────────────────────────────
    if req.lead_id:
        lead = get_lead_by_id(req.lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail=f"Lead {req.lead_id} not found")
    else:
        lead = get_next_lead()
        if not lead:
            raise HTTPException(status_code=404, detail="No pending leads available")

    lead_id = str(lead["id"])

    # ── Lock lead (prevent duplicate calls) ───────────────────────
    if not lock_lead(lead_id):
        raise HTTPException(status_code=409, detail=f"Lead {lead_id} is already being called")

    # ── Create call record in DB ───────────────────────────────────
    call_id = str(uuid.uuid4())
    try:
        create_call_record(call_id, lead_id)
    except Exception as e:
        unlock_lead(lead_id)
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    # ── Initialize AgentState ──────────────────────────────────────
    state = initial_state(call_id, lead)

    # ── Run intro_node ─────────────────────────────────────────────
    try:
        from graph.nodes import intro_node
        state = intro_node(state)
    except Exception as e:
        unlock_lead(lead_id)
        update_call_outcome(call_id, "failed")
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")

    # ── Save state to Redis ────────────────────────────────────────
    save_state(call_id, state)

    # ── Save intro to transcript ───────────────────────────────────
    agent_reply = state["messages"][-1]["content"]
    save_transcript_chunk(call_id, "agent", agent_reply)

    logger.info(f"Call started: {call_id} | Lead: {lead.get('name')} | {lead.get('phone')}")

    return StartCallResponse(
        call_id=call_id,
        lead_name=lead.get("name", ""),
        lead_phone=lead.get("phone", ""),
        agent_reply=agent_reply,
        current_node=state["current_node"],
    )


# ══════════════════════════════════════════════════════════════════
#  POST /call/respond
# ══════════════════════════════════════════════════════════════════

@router.post("/respond", response_model=RespondResponse)
async def respond(req: RespondRequest):
    """
    Process one user message and return the next agent reply.
    Called once per user speaking turn.

    Flow:
    1. Load state from Redis
    2. Append user message to conversation
    3. Run next LangGraph node
    4. Save updated state to Redis
    5. Return agent reply
    """
    # ── Load session ───────────────────────────────────────────────
    state = get_state(req.call_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Call session {req.call_id} not found or expired")

    # ── Append user message ────────────────────────────────────────
    user_text = req.user_text.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="user_text cannot be empty")

    state["messages"].append({"role": "user", "content": user_text})

    # ── Save user transcript ───────────────────────────────────────
    save_transcript_chunk(req.call_id, "customer", user_text)

    # ── Run next graph node ────────────────────────────────────────
    try:
        state, next_node = run_next_node(state)
    except Exception as e:
        logger.error(f"[{req.call_id}] Node execution error: {e}")
        raise HTTPException(status_code=500, detail=f"Agent processing error: {e}")

    # ── Check if conversation ended ────────────────────────────────
    is_done = (next_node is None) or (state.get("current_node") == "saved")

    # ── Get agent reply ────────────────────────────────────────────
    agent_reply = ""
    for m in reversed(state["messages"]):
        if m["role"] == "assistant":
            agent_reply = m["content"]
            break

    # ── Save agent transcript ──────────────────────────────────────
    if agent_reply:
        save_transcript_chunk(req.call_id, "agent", agent_reply)

    # ── Update Redis or clean up if done ──────────────────────────
    if is_done:
        _cleanup_call(req.call_id, state)
    else:
        save_state(req.call_id, state)
        refresh_ttl(req.call_id)

    logger.info(
        f"[{req.call_id}] Turn {state.get('turn_count')} | "
        f"node: {state.get('current_node')} | done: {is_done}"
    )

    return RespondResponse(
        call_id=req.call_id,
        agent_reply=agent_reply,
        current_node=state.get("current_node", ""),
        is_done=is_done,
        extracted_so_far=state.get("extracted_data", {}),
    )


# ══════════════════════════════════════════════════════════════════
#  POST /call/end
# ══════════════════════════════════════════════════════════════════

@router.post("/end")
async def end_call(req: EndCallRequest, background_tasks: BackgroundTasks):
    """
    Force-end a call (user hung up, timeout, etc.)
    Saves whatever we have collected so far.
    """
    state = get_state(req.call_id)

    if state:
        # Save partial data
        background_tasks.add_task(_save_partial_call, state, req.reason)

    _cleanup_call(req.call_id, state)

    return {
        "message": "Call ended",
        "call_id": req.call_id,
        "reason": req.reason,
        "data_collected": state.get("extracted_data", {}) if state else {}
    }


# ══════════════════════════════════════════════════════════════════
#  GET /call/{call_id}/state  (debug)
# ══════════════════════════════════════════════════════════════════

@router.get("/{call_id}/state")
async def get_call_state(call_id: str):
    """Debug endpoint — returns full AgentState for a call."""
    state = get_state(call_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    # Remove messages from response (too verbose) — use /transcript for that
    debug_state = {k: v for k, v in state.items() if k != "messages"}
    debug_state["message_count"] = len(state.get("messages", []))
    return debug_state


# ══════════════════════════════════════════════════════════════════
#  GET /call/{call_id}/transcript
# ══════════════════════════════════════════════════════════════════

@router.get("/{call_id}/transcript")
async def get_transcript(call_id: str):
    """Returns the full conversation transcript from PostgreSQL."""
    rows = get_full_transcript(call_id)
    if not rows:
        # Fallback to Redis (call might still be active)
        state = get_state(call_id)
        if state:
            return {"call_id": call_id, "source": "redis", "transcript": state["messages"]}
        raise HTTPException(status_code=404, detail="Transcript not found")

    return {"call_id": call_id, "source": "db", "transcript": rows}


# ══════════════════════════════════════════════════════════════════
#  GET /calls/active
# ══════════════════════════════════════════════════════════════════

@router.get("/active/count")
async def active_calls():
    count = get_active_call_count()
    return {"active_calls": count, "timestamp": datetime.utcnow().isoformat()}


# ══════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════

def _cleanup_call(call_id: str, state: dict | None):
    """Clean up Redis session and unlock lead after call ends."""
    delete_state(call_id)
    if state:
        lead_id = str(state["lead"]["id"])
        unlock_lead(lead_id)
        update_call_outcome(call_id, "completed")


def _save_partial_call(state: dict, reason: str):
    """Save whatever data we have even if call ended early."""
    from db.db_utils import save_application, update_lead_status, log_audit_event
    try:
        save_application(state)
        update_lead_status(str(state["lead"]["id"]), "retry" if reason == "user_hangup" else "called")
        log_audit_event("call", state["call_id"], f"early_end_{reason}", {
            "turn_count": state.get("turn_count", 0),
            "current_node": state.get("current_node"),
        })
    except Exception as e:
        logger.error(f"Failed to save partial call data: {e}")