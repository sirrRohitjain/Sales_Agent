"""
services/session_manager.py
Manages call sessions in Redis.
Each active call has its AgentState stored here with a 15-min TTL.
"""

import os
import json
import logging
import redis
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

REDIS_URL     = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SESSION_TTL   = 60 * 15      # 15 minutes — a call won't last longer
LOCK_TTL      = 60 * 30      # 30 minutes — prevent re-calling same lead

# ── Redis client ───────────────────────────────────────────────────
_redis_client = None

def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


def test_redis():
    try:
        get_redis().ping()
        logger.info("✅ Redis connected successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        return False


# ══════════════════════════════════════════════════════════════════
#  SESSION OPERATIONS
# ══════════════════════════════════════════════════════════════════

def save_state(call_id: str, state: dict):
    """Serialize and store AgentState in Redis."""
    key = f"call:{call_id}:state"
    try:
        get_redis().setex(key, SESSION_TTL, json.dumps(state, default=str))
        logger.debug(f"State saved for call {call_id}")
    except Exception as e:
        logger.error(f"Failed to save state for {call_id}: {e}")
        raise


def get_state(call_id: str) -> dict | None:
    """Load AgentState from Redis. Returns None if expired or missing."""
    key = f"call:{call_id}:state"
    try:
        raw = get_redis().get(key)
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
        get_redis().delete(key)
        logger.info(f"Session deleted for call {call_id}")
    except Exception as e:
        logger.error(f"Failed to delete state for {call_id}: {e}")


def refresh_ttl(call_id: str):
    """Reset the 15-min timer on each user message (call is still active)."""
    key = f"call:{call_id}:state"
    try:
        get_redis().expire(key, SESSION_TTL)
    except Exception as e:
        logger.warning(f"Could not refresh TTL for {call_id}: {e}")


def session_exists(call_id: str) -> bool:
    return get_redis().exists(f"call:{call_id}:state") == 1


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
    result = get_redis().set(key, "1", ex=LOCK_TTL, nx=True)
    if result:
        logger.info(f"Lead {lead_id} locked")
    else:
        logger.warning(f"Lead {lead_id} already locked (call in progress)")
    return bool(result)


def unlock_lead(lead_id: str):
    key = f"lead:{lead_id}:locked"
    get_redis().delete(key)
    logger.info(f"Lead {lead_id} unlocked")


def is_lead_locked(lead_id: str) -> bool:
    return get_redis().exists(f"lead:{lead_id}:locked") == 1


# ══════════════════════════════════════════════════════════════════
#  CALL METADATA (lightweight, separate from full state)
# ══════════════════════════════════════════════════════════════════

def set_call_meta(call_id: str, key: str, value: str):
    """Store small metadata values separately (e.g., current node name)."""
    redis_key = f"call:{call_id}:meta:{key}"
    get_redis().setex(redis_key, SESSION_TTL, value)


def get_call_meta(call_id: str, key: str) -> str | None:
    redis_key = f"call:{call_id}:meta:{key}"
    return get_redis().get(redis_key)


def get_active_call_count() -> int:
    """Count how many calls are currently active (for monitoring)."""
    keys = get_redis().keys("call:*:state")
    return len(keys)