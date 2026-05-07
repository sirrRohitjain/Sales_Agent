"""
db/db_utils.py
All database CRUD operations.
Every function uses the get_db() context manager.
"""

import uuid
import json
import logging
from datetime import datetime
from sqlalchemy import text
from db.database import get_db

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
#  LEADS
# ══════════════════════════════════════════════════════════════════

def get_next_lead() -> dict | None:
    """
    Pick the highest priority pending lead that is not currently locked.
    Called by the call scheduler to decide who to call next.
    """
    query = text("""
        SELECT id, name, phone, age, income, credit_score,
               employment_type, status, priority_score
        FROM leads
        WHERE status = 'pending'
          AND id NOT IN (
              SELECT lead_id FROM calls
              WHERE outcome IS NULL  -- currently active call
          )
        ORDER BY priority_score DESC, created_at ASC
        LIMIT 1
    """)
    with get_db() as db:
        row = db.execute(query).mappings().first()
        return dict(row) if row else None


def get_lead_by_id(lead_id: str) -> dict | None:
    query = text("SELECT * FROM leads WHERE id = :id")
    with get_db() as db:
        row = db.execute(query, {"id": lead_id}).mappings().first()
        return dict(row) if row else None


def get_lead_by_phone(phone: str) -> dict | None:
    query = text("SELECT * FROM leads WHERE phone = :phone")
    with get_db() as db:
        row = db.execute(query, {"phone": phone}).mappings().first()
        return dict(row) if row else None


def update_lead_status(lead_id: str, status: str):
    """
    Status values: pending | called | not_interested | applied | retry | unreachable
    """
    query = text("""
        UPDATE leads SET status = :status, updated_at = NOW()
        WHERE id = :id
    """)
    with get_db() as db:
        db.execute(query, {"id": lead_id, "status": status})
    logger.info(f"Lead {lead_id} status → {status}")


def get_all_leads(limit: int = 50, offset: int = 0, status: str = None) -> list[dict]:
    if status:
        query = text("""
            SELECT * FROM leads WHERE status = :status
            ORDER BY priority_score DESC LIMIT :limit OFFSET :offset
        """)
        params = {"status": status, "limit": limit, "offset": offset}
    else:
        query = text("SELECT * FROM leads ORDER BY priority_score DESC LIMIT :limit OFFSET :offset")
        params = {"limit": limit, "offset": offset}

    with get_db() as db:
        rows = db.execute(query, params).mappings().all()
        return [dict(r) for r in rows]


def insert_lead(data: dict) -> str:
    lead_id = str(uuid.uuid4())
    query = text("""
        INSERT INTO leads (id, name, phone, age, income, credit_score,
                           employment_type, status, priority_score, created_at)
        VALUES (:id, :name, :phone, :age, :income, :credit_score,
                :employment_type, 'pending', :priority_score, NOW())
    """)
    with get_db() as db:
        db.execute(query, {
            "id": lead_id,
            "name": data["name"],
            "phone": data["phone"],
            "age": data.get("age"),
            "income": data.get("income"),
            "credit_score": data.get("credit_score"),
            "employment_type": data.get("employment_type"),
            "priority_score": data.get("priority_score", 50),
        })
    return lead_id


def get_pending_leads(limit: int = 10) -> list[dict]:
    """
    Fetch leads with status='pending' — used by Celery beat auto-dialer.
    """
    return get_all_leads(limit=limit, status="pending")


# ══════════════════════════════════════════════════════════════════
#  CALLS
# ══════════════════════════════════════════════════════════════════

def create_call_record(
    call_id: str,
    lead_id: str,
    status: str = "initiated",
    initiated_at: datetime = None,
    twilio_sid: str = None,
) -> str:
    """
    Insert a new call record.
    """
    query = text("""
        INSERT INTO calls (id, lead_id, start_time, outcome, created_at)
        VALUES (:id, :lead_id, :start_time, NULL, NOW())
        ON CONFLICT (id) DO NOTHING
    """)
    with get_db() as db:
        db.execute(query, {
            "id": call_id,
            "lead_id": lead_id,
            "start_time": initiated_at or datetime.utcnow(),
        })
    logger.info(f"Call record created: {call_id}")
    return call_id


def update_call_status(
    call_id: str,
    status: str,
    twilio_sid: str = None,
    duration_seconds: int = None,
    consent_given: bool = None,
    card_recommended: str = None,
) -> None:
    """
    Called by voice_routes.py status webhook.
    Maps Twilio status strings → our outcome column values.
    """
    outcome_map = {
        "completed":   "completed",
        "failed":      "failed",
        "busy":        "busy",
        "no-answer":   "not_answered",
        "canceled":    "failed",
        "ringing":     None,       # still live — don't write outcome yet
        "in-progress": None,
    }
    outcome = outcome_map.get(status, status)

    fields = ["updated_at = NOW()"]
    params: dict = {"id": call_id}

    if outcome is not None:
        fields.append("outcome = :outcome")
        params["outcome"] = outcome

    if status in ("completed", "failed", "busy", "no-answer", "canceled"):
        fields.append("end_time = NOW()")

    if duration_seconds is not None:
        fields.append("duration_seconds = :duration")
        params["duration"] = duration_seconds

    if twilio_sid is not None:
        logger.info(f"Twilio SID for call {call_id}: {twilio_sid}")

    query = text(f"UPDATE calls SET {', '.join(fields)} WHERE id = :id")
    with get_db() as db:
        db.execute(query, params)

    logger.info(f"Call {call_id} → {status}")


def update_call_outcome(call_id: str, outcome: str, duration_seconds: int = 0):
    """
    outcome: connected | not_answered | busy | failed | completed
    """
    query = text("""
        UPDATE calls
        SET outcome = :outcome,
            end_time = NOW(),
            duration_seconds = :duration,
            updated_at = NOW()
        WHERE id = :id
    """)
    with get_db() as db:
        db.execute(query, {
            "id": call_id,
            "outcome": outcome,
            "duration": duration_seconds
        })


def get_call_by_id(call_id: str) -> dict | None:
    query = text("SELECT * FROM calls WHERE id = :id")
    with get_db() as db:
        row = db.execute(query, {"id": call_id}).mappings().first()
        return dict(row) if row else None


# ══════════════════════════════════════════════════════════════════
#  APPLICATIONS
# ══════════════════════════════════════════════════════════════════

def save_application(state: dict) -> str:
    """
    Called from save_to_db_node in LangGraph.
    Saves the complete application after call ends.
    """
    app_id = str(uuid.uuid4())
    extracted = state.get("extracted_data", {})
    transcript = state.get("messages", [])

    query = text("""
        INSERT INTO applications (
            id, lead_id, call_id, income_stated, employment_type,
            existing_cards, spending_habits, card_recommended,
            consent_given, status, extracted_data, transcript,
            objection_count, turn_count, created_at
        ) VALUES (
            :id, :lead_id, :call_id, :income, :employment,
            :existing_cards, :spending_habits, :card_recommended,
            :consent, :status, :extracted_data, :transcript,
            :objection_count, :turn_count, NOW()
        )
    """)

    status = "applied" if state.get("consent_given") else "not_converted"

    with get_db() as db:
        db.execute(query, {
            "id": app_id,
            "lead_id": state["lead"]["id"],
            "call_id": state["call_id"],
            "income": extracted.get("income"),
            "employment": extracted.get("employment_type"),
            "existing_cards": extracted.get("existing_cards"),
            "spending_habits": extracted.get("spending_habits"),
            "card_recommended": state.get("card_recommended"),
            "consent": state.get("consent_given", False),
            "status": status,
            "extracted_data": json.dumps(extracted),
            "transcript": json.dumps(transcript),
            "objection_count": state.get("objection_count", 0),
            "turn_count": state.get("turn_count", 0),
        })

    logger.info(f"Application saved: {app_id} | status: {status}")
    return app_id


def create_application_record(
    application_id: str,
    call_id: str,
    lead_id: str,
    card_name: str,
    status: str = "pending_kyc",
    created_at: datetime = None,
) -> None:
    """
    Lightweight insert — called by Celery process_application task after consent.
    """
    query = text("""
        INSERT INTO applications (
            id, lead_id, call_id, card_recommended,
            consent_given, status, created_at
        ) VALUES (
            :id, :lead_id, :call_id, :card_name,
            true, :status, :created_at
        )
        ON CONFLICT (id) DO NOTHING
    """)
    with get_db() as db:
        db.execute(query, {
            "id": application_id,
            "lead_id": lead_id,
            "call_id": call_id,
            "card_name": card_name,
            "status": status,
            "created_at": created_at or datetime.utcnow(),
        })
    logger.info(f"Application record created: {application_id} | card={card_name}")


def get_application_by_call(call_id: str) -> dict | None:
    query = text("SELECT * FROM applications WHERE call_id = :call_id")
    with get_db() as db:
        row = db.execute(query, {"call_id": call_id}).mappings().first()
        return dict(row) if row else None


def update_application_status(app_id: str, status: str):
    """status: applied | approved | rejected | pending_kyc"""
    query = text("""
        UPDATE applications SET status = :status, updated_at = NOW()
        WHERE id = :id
    """)
    with get_db() as db:
        db.execute(query, {"id": app_id, "status": status})


# ══════════════════════════════════════════════════════════════════
#  TRANSCRIPTS
# ══════════════════════════════════════════════════════════════════

def save_transcript_chunk(call_id: str, role: str, message: str):
    """Save individual transcript lines during the call (real-time)."""
    query = text("""
        INSERT INTO transcripts (id, call_id, role, message, created_at)
        VALUES (:id, :call_id, :role, :message, NOW())
    """)
    with get_db() as db:
        db.execute(query, {
            "id": str(uuid.uuid4()),
            "call_id": call_id,
            "role": role,
            "message": message,
        })


def get_full_transcript(call_id: str) -> list[dict]:
    query = text("""
        SELECT role, message as content, created_at
        FROM transcripts WHERE call_id = :call_id
        ORDER BY created_at ASC
    """)
    with get_db() as db:
        rows = db.execute(query, {"call_id": call_id}).mappings().all()
        return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════
#  CARD ISSUANCES
# ══════════════════════════════════════════════════════════════════

def create_card_issuance(application_id: str, card_type: str) -> str:
    issuance_id = str(uuid.uuid4())
    query = text("""
        INSERT INTO card_issuances (id, application_id, card_type, status, created_at)
        VALUES (:id, :app_id, :card_type, 'pending', NOW())
    """)
    with get_db() as db:
        db.execute(query, {
            "id": issuance_id,
            "app_id": application_id,
            "card_type": card_type,
        })
    return issuance_id


def update_card_issuance_status(issuance_id: str, status: str, reference: str = None):
    """status: pending | issued | rejected"""
    query = text("""
        UPDATE card_issuances
        SET status = :status, bank_reference = :reference, updated_at = NOW()
        WHERE id = :id
    """)
    with get_db() as db:
        db.execute(query, {"id": issuance_id, "status": status, "reference": reference})


# ══════════════════════════════════════════════════════════════════
#  AUDIT LOG
# ══════════════════════════════════════════════════════════════════

def log_audit_event(entity_type: str, entity_id: str, event_type: str, details: dict = None):
    query = text("""
        INSERT INTO audit_log (id, entity_type, entity_id, event_type, details, created_at)
        VALUES (:id, :entity_type, :entity_id, :event_type, :details, NOW())
    """)
    with get_db() as db:
        db.execute(query, {
            "id": str(uuid.uuid4()),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "event_type": event_type,
            "details": json.dumps(details or {}),
        })


# ══════════════════════════════════════════════════════════════════
#  ANALYTICS
# ══════════════════════════════════════════════════════════════════

def get_daily_stats() -> dict:
    query = text("""
        SELECT
            COUNT(DISTINCT c.id)                                          AS total_calls,
            COUNT(DISTINCT CASE WHEN c.outcome='completed' THEN c.id END) AS connected,
            COUNT(DISTINCT CASE WHEN a.consent_given=true THEN a.id END)  AS converted,
            COUNT(DISTINCT CASE WHEN ci.status='issued' THEN ci.id END)   AS cards_issued
        FROM calls c
        LEFT JOIN applications a ON a.call_id = c.id
        LEFT JOIN card_issuances ci ON ci.application_id = a.id
        WHERE c.created_at >= CURRENT_DATE
    """)
    with get_db() as db:
        row = db.execute(query).mappings().first()
        return dict(row) if row else {}