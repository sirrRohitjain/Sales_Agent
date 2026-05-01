"""
services/llm_service.py
LLM setup using Groq (free, fast) with Google Gemini Flash as fallback.
All nodes call call_llm() to get responses.
"""

import os
import re
import json
import logging
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ── Primary: Groq (free, very fast ~500 tokens/sec) ───────────────
groq_llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.75,   # higher = more natural/human-like variation
    max_tokens=350,     # keep replies short like a real salesperson
    timeout=10,
)
# response = groq_llm.invoke([SystemMessage(content="Hello i am priya a credit card sales agent working for axis bank")])
# print("Groq test response:", response.content[:100])  # Print first 100 chars to verify connection

# ── Fallback: Google Gemini Flash (free tier) ──────────────────────
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    gemini_llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.75,
        max_output_tokens=350,
    )
    GEMINI_AVAILABLE = bool(os.getenv("GOOGLE_API_KEY"))
except Exception:
    gemini_llm = None
    GEMINI_AVAILABLE = False


def _build_messages(system_prompt: str, conversation: list) -> list:
    """Convert our message dicts to LangChain message objects."""
    msgs = [SystemMessage(content=system_prompt)]
    for m in conversation:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "user":
            msgs.append(HumanMessage(content=content))
        elif role == "assistant":
            msgs.append(AIMessage(content=content))
    return msgs


def _parse_response(raw: str) -> dict:
    """
    Safely parse LLM response to dict.
    Handles: clean JSON, JSON with markdown fences, JSON buried in text.
    """
    # Strip markdown code fences
    raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()

    # Direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Find JSON block inside text
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Last resort — treat entire response as the reply
    logger.warning(f"LLM response was not valid JSON. Raw: {raw[:200]}")
    return {
        "reply": raw,
        "extracted": {},
        "next_action": "continue"
    }


def call_llm(system_prompt: str, conversation: list) -> dict:
    """
    Main LLM call used by all LangGraph nodes.

    Args:
        system_prompt: Node-specific instructions + persona
        conversation:  Full message history [{role, content}]

    Returns:
        dict with keys: reply, extracted, next_action
    """
    msgs = _build_messages(system_prompt, conversation)

    # Try Groq first
    try:
        response = groq_llm.invoke(msgs)
        result = _parse_response(response.content)
        logger.debug(f"Groq response: {result}")
        return result
    except Exception as e:
        logger.warning(f"Groq failed: {e}. Trying Gemini fallback...")

    # Try Gemini fallback
    if GEMINI_AVAILABLE and gemini_llm:
        try:
            response = gemini_llm.invoke(msgs)
            result = _parse_response(response.content)
            logger.debug(f"Gemini fallback response: {result}")
            return result
        except Exception as e:
            logger.error(f"Gemini also failed: {e}")

    # Hardcoded fallback so the call doesn't crash
    logger.error("Both LLMs failed. Using emergency fallback response.")
    return {
        "reply": "Sorry, I'm having a small technical issue. Can you hold on for just a second?",
        "extracted": {},
        "next_action": "continue"
    }