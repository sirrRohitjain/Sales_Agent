"""
routes/voice_routes.py

Twilio webhook endpoints for outbound voice calls.
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import PlainTextResponse

from db.db_utils import get_lead_by_id, update_call_status
from graph.graph_builder import build_graph
from services.session_manager import SessionManager
from services.tts_service import text_to_speech_async, cleanup_audio_file
from services.twilio_service import (
    get_base_url,
    twiml_play_and_gather,
    twiml_say_and_gather,
    twiml_end_call,
    twiml_voicemail_detected,
)

router = APIRouter(prefix="/voice", tags=["voice"])
logger = logging.getLogger(__name__)
session_manager = SessionManager()

# ── 1. Call Answer Webhook ──────────────────────────────────────────────────────

@router.post("/answer/{call_id}")
async def answer_call(
    call_id: str,
    request: Request = None,
    AnsweredBy: Optional[str] = Form(default=None),
    CallSid: Optional[str] = Form(default=None),
    CallStatus: Optional[str] = Form(default=None),
):
    logger.info(f"Call answered | call_id={call_id} | answered_by={AnsweredBy} | sid={CallSid}")

    if AnsweredBy in ("machine_start", "machine_end_beep", "machine_end_other"):
        logger.info(f"Voicemail detected for call {call_id}")
        return PlainTextResponse(
            content=twiml_voicemail_detected(),
            media_type="application/xml",
        )

    session = await session_manager.get_session(call_id)
    if not session:
        logger.error(f"No session found for call_id={call_id}")
        return _error_twiml("Sorry, there was a technical issue. Goodbye.")

    if CallSid:
        session["twilio_call_sid"] = CallSid
        await session_manager.save_session(call_id, session)

    graph = build_graph()
    state = session.get("graph_state", {})
    state = graph.invoke(state, config={"configurable": {"node": "intro"}})

    agent_reply = _get_last_agent_message(state)
    gather_url = f"{get_base_url()}/voice/gather/{call_id}"
    
    try:
        audio_filename = await text_to_speech_async(agent_reply)
        twiml = twiml_play_and_gather(audio_filename, gather_url)
    except Exception as e:
        logger.warning(f"TTS failed, using Twilio Say fallback: {e}")
        twiml = twiml_say_and_gather(agent_reply, gather_url)

    session["graph_state"] = state
    await session_manager.save_session(call_id, session)

    return PlainTextResponse(content=twiml, media_type="application/xml")


# ── 2. Speech Gather Webhook ────────────────────────────────────────────────────

@router.post("/gather/{call_id}")
async def gather_speech(
    call_id: str,
    SpeechResult: Optional[str] = Form(default=None),
    Confidence: Optional[float] = Form(default=None),
    CallSid: Optional[str] = Form(default=None),
    CallStatus: Optional[str] = Form(default=None),
):
    logger.info(
        f"Speech received | call_id={call_id} | "
        f"confidence={Confidence} | speech='{SpeechResult}'"
    )

    if not SpeechResult or SpeechResult.strip() == "":
        return _reprompt_twiml(call_id, "Sorry, I couldn't hear you. Could you say that again?")

    session = await session_manager.get_session(call_id)
    if not session:
        return _error_twiml("Session expired. Please call us back. Goodbye.")

    state = session.get("graph_state", {})
    customer_text = SpeechResult.strip()
    
    if "messages" not in state:
        state["messages"] = []
    state["messages"].append({"role": "user", "content": customer_text})

    graph = build_graph()
    try:
        state = graph.invoke(state)
    except Exception as e:
        logger.error(f"Graph error for call {call_id}: {e}")
        return _error_twiml("I'm having a small technical issue. Let me call you back shortly. Goodbye.")

    agent_reply = _get_last_agent_message(state)
    current_node = state.get("current_node", "")

    if current_node in ("save_to_db", "end") or state.get("next_action") == "end":
        session["graph_state"] = state
        await session_manager.save_session(call_id, session)
        return await _end_call_twiml(agent_reply)

    gather_url = f"{get_base_url()}/voice/gather/{call_id}"
    try:
        audio_filename = await text_to_speech_async(agent_reply)
        twiml = twiml_play_and_gather(audio_filename, gather_url)
    except Exception as e:
        logger.warning(f"TTS failed, using fallback: {e}")
        twiml = twiml_say_and_gather(agent_reply, gather_url)

    session["graph_state"] = state
    await session_manager.save_session(call_id, session)

    return PlainTextResponse(content=twiml, media_type="application/xml")


# ── 3. Call Status Webhook ──────────────────────────────────────────────────────

@router.post("/status/{call_id}")
async def call_status(
    call_id: str,
    CallStatus: Optional[str] = Form(default=None),
    CallDuration: Optional[int] = Form(default=None),
    CallSid: Optional[str] = Form(default=None),
):
    logger.info(f"Call status | call_id={call_id} | status={CallStatus} | duration={CallDuration}s")

    terminal_statuses = {"completed", "failed", "busy", "no-answer", "canceled"}

    if CallStatus in terminal_statuses:
        try:
            update_call_status(
                call_id=call_id,
                status=CallStatus,
                duration_seconds=CallDuration or 0,
            )
        except Exception as e:
            logger.warning(f"Could not update call status in DB: {e}")

        if CallStatus in ("completed", "failed"):
            await session_manager.delete_session(call_id)
            logger.info(f"Session cleaned up for call {call_id}")

    return PlainTextResponse(content="OK", media_type="text/plain")


# ── Helper functions ─────────────────────────────────────────────────────────────

def _get_last_agent_message(state: dict) -> str:
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            return msg.get("content", "").strip()
    return "Hi, this is Priya from QuickBank. How are you today?"

def _reprompt_twiml(call_id: str, text: str) -> PlainTextResponse:
    gather_url = f"{get_base_url()}/voice/gather/{call_id}"
    twiml = twiml_say_and_gather(text, gather_url, timeout=6)
    return PlainTextResponse(content=twiml, media_type="application/xml")

def _error_twiml(message: str) -> PlainTextResponse:
    twiml = twiml_end_call(farewell_text=message)
    return PlainTextResponse(content=twiml, media_type="application/xml")

async def _end_call_twiml(agent_reply: str) -> PlainTextResponse:
    try:
        audio_filename = await text_to_speech_async(agent_reply)
        twiml = twiml_end_call(farewell_audio_filename=audio_filename)
    except Exception:
        twiml = twiml_end_call(farewell_text=agent_reply)
    return PlainTextResponse(content=twiml, media_type="application/xml")