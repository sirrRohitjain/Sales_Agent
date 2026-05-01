"""
services/session_manager.py
Manages call sessions using Upstash Redis (Serverless REST API).
Each active call has its AgentState stored here with a 15-min TTL.
"""

import os
import json
import logging
import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Upstash REST credentials
UPSTASH_URL = os.getenv("UPSTASH_REDIS_REST_URL")
UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")
UPSTASH_HEADERS = {"Authorization": f"Bearer {UPSTASH_TOKEN}"} if UPSTASH_TOKEN else {}

SESSION_TTL   = 60 * 15      # 15 minutes — a call won't last longer
LOCK_TTL      = 60 * 30      # 30 minutes — prevent re-calling same lead

# ── Upstash REST Helper ────────────────────────────────────────────

def _run_redis_cmd(*args):
    """Helper to execute Redis commands via Upstash REST API."""
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        logger.error("❌ Missing UPSTASH_REDIS_REST_URL or UPSTASH_REDIS_REST_TOKEN in .env")
        return None
        
    try:
        res = requests.post(UPSTASH_URL, headers=UPSTASH_HEADERS, json=list(args))
        res.raise_for_status()
        return res.json().get("result")
    except Exception as e:
        logger.error(f"Upstash request failed for {args[0]}: {e}")
        return None

def test_redis():
    result = _run_redis_cmd("PING")
    if result == "PONG":
        logger.info("✅ Upstash Redis connected successfully")
        return True
    logger.error("❌ Upstash Redis connection failed")
    return False

# ══════════════════════════════════════════════════════════════════
#  SESSION OPERATIONS
# ══════════════════════════════════════════════════════════════════

def save_state(call_id: str, state: dict):
    """Serialize and store AgentState in Redis."""
    key = f"call:{call_id}:state"
    try:
        _run_redis_cmd("SET", key, json.dumps(state, default=str), "EX", SESSION_TTL)
        logger.debug(f"State saved for call {call_id}")
    except Exception as e:
        logger.error(f"Failed to save state for {call_id}: {e}")
        raise

def get_state(call_id: str) -> dict | None:
    """Load AgentState from Redis. Returns None if expired or missing."""
    key = f"call:{call_id}:state"
    try:
        raw = _run_redis_cmd("GET", key)
        if raw is None:
            logger.warning(f"No session found for call {call_id}")
            return None
        return json.loads(raw)
    except Exception as e:
        logger.error(f"Failed to get state for {call_id}: {e}")
        return None

def delete_state(call_id: str):
    """Remove session after call ends."""
    key = f"call:{call_id}:state"
    try:
        _run_redis_cmd("DEL", key)
        logger.info(f"Session deleted for call {call_id}")
    except Exception as e:
        logger.error(f"Failed to delete state for {call_id}: {e}")

def refresh_ttl(call_id: str):
    """Reset the 15-min timer on each user message (call is still active)."""
    key = f"call:{call_id}:state"
    try:
        _run_redis_cmd("EXPIRE", key, SESSION_TTL)
    except Exception as e:
        logger.warning(f"Could not refresh TTL for {call_id}: {e}")

def session_exists(call_id: str) -> bool:
    return _run_redis_cmd("EXISTS", f"call:{call_id}:state") == 1

# ══════════════════════════════════════════════════════════════════
#  LEAD LOCK — prevent duplicate calls to same lead
# ══════════════════════════════════════════════════════════════════

def lock_lead(lead_id: str) -> bool:
    """
    Atomically set a lock for this lead.
    Returns True if lock acquired, False if lead is already being called.
    """
    key = f"lead:{lead_id}:locked"
    # NX = only set if not exists (atomic)
    result = _run_redis_cmd("SET", key, "1", "EX", LOCK_TTL, "NX")
    
    # Upstash REST returns "OK" if NX succeeds, and None if it was already set
    if result == "OK":
        logger.info(f"Lead {lead_id} locked")
        return True
    else:
        logger.warning(f"Lead {lead_id} already locked (call in progress)")
        return False

def unlock_lead(lead_id: str):
    key = f"lead:{lead_id}:locked"
    _run_redis_cmd("DEL", key)
    logger.info(f"Lead {lead_id} unlocked")

def is_lead_locked(lead_id: str) -> bool:
    return _run_redis_cmd("EXISTS", f"lead:{lead_id}:locked") == 1

# ══════════════════════════════════════════════════════════════════
#  CALL METADATA (lightweight, separate from full state)
# ══════════════════════════════════════════════════════════════════

def set_call_meta(call_id: str, key: str, value: str):
    """Store small metadata values separately (e.g., current node name)."""
    redis_key = f"call:{call_id}:meta:{key}"
    _run_redis_cmd("SET", redis_key, value, "EX", SESSION_TTL)

def get_call_meta(call_id: str, key: str) -> str | None:
    redis_key = f"call:{call_id}:meta:{key}"
    return _run_redis_cmd("GET", redis_key)

def get_active_call_count() -> int:
    """Count how many calls are currently active (for monitoring)."""
    keys = _run_redis_cmd("KEYS", "call:*:state")
    return len(keys) if keys else 0