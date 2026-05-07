"""
tasks/celery_tasks.py

Celery background tasks:
  1. make_outbound_call  → dials lead, initiates voice session
  2. process_application → post-consent card processing
  3. schedule_retry_call → reschedule failed/busy calls
  4. send_sms_confirmation → SMS after consent captured
"""

import logging
import os
import uuid
import asyncio
from datetime import datetime, timedelta

from celery import Celery
from celery.utils.log import get_task_logger

from db.db_utils import (
    get_lead_by_id,
    create_call_record,
    update_call_status,
    get_pending_leads,
    create_application_record # Added missing import
)
from services.session_manager import SessionManager

# ── MUST BE AT TOP LEVEL FOR PYTEST @patch TO WORK ────────────────────────────
from services.twilio_service import make_outbound_call as twilio_dial

# ── Celery app ────────────────────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "sales_agent",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_acks_late=True,            # re-queue on worker crash
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,   # one task at a time (voice calls are heavy)
)

logger = get_task_logger(__name__)
session_manager = SessionManager()


# ── Task 1: Make Outbound Call ─────────────────────────────────────────────────

@celery_app.task(
    name="tasks.make_outbound_call",
    bind=True,
    max_retries=3,
    default_retry_delay=60,         # retry after 60 seconds
)
def make_outbound_call(self, lead_id: str) -> dict:
    """
    Main task: picks up a lead and makes an outbound voice call.
    """
    logger.info(f"[make_outbound_call] Starting for lead_id={lead_id}")

    # ── 1. Fetch lead ─────────────────────────────────────────────────────────
    lead = get_lead_by_id(lead_id)
    if not lead:
        logger.error(f"Lead {lead_id} not found")
        return {"success": False, "error": "Lead not found"}

    if not lead.get("phone"):
        logger.error(f"Lead {lead_id} has no phone number")
        return {"success": False, "error": "No phone number"}

    # ── 2. Acquire lead lock (prevent duplicate calls) ────────────────────────
    lock_acquired = asyncio.run(session_manager.acquire_lead_lock(lead_id))
    if not lock_acquired:
        logger.warning(f"Lead {lead_id} is already being called")
        return {"success": False, "error": "Lead already in call"}

    # ── 3. Create call record in DB ───────────────────────────────────────────
    call_id = str(uuid.uuid4())
    try:
        create_call_record(
            call_id=call_id,
            lead_id=lead_id,
            status="initiated",
            initiated_at=datetime.utcnow(),
        )
    except Exception as e:
        logger.error(f"Could not create call record: {e}")
        asyncio.run(session_manager.release_lead_lock(lead_id))
        return {"success": False, "error": str(e)}

    # ── 4. Initialize LangGraph state in Redis ────────────────────────────────
    initial_state = {
        "call_id": call_id,
        "lead": lead,
        "messages": [],
        "current_node": "intro",
        "turn_count": 0,
        "next_action": None,
        "objection_count": 0,
        "extracted_data": {},
        "card_recommended": None,
        "consent_given": False,
        "call_start_time": datetime.utcnow().isoformat(),
        "error": None,
    }
    asyncio.run(session_manager.create_session(call_id, initial_state))

    # ── 5. Dial via Twilio ────────────────────────────────────────────────────
    try:
        twilio_sid = twilio_dial(
            to_number=lead["phone"],
            call_id=call_id,
        )
        update_call_status(call_id=call_id, status="ringing", twilio_sid=twilio_sid)
        logger.info(f"Call initiated | call_id={call_id} | twilio_sid={twilio_sid}")
        return {"success": True, "call_id": call_id, "twilio_sid": twilio_sid}

    except Exception as exc:
        logger.error(f"Twilio dial failed for lead {lead_id}: {exc}")
        update_call_status(call_id=call_id, status="failed")
        asyncio.run(session_manager.release_lead_lock(lead_id))
        raise self.retry(exc=exc)


# ── Task 2: Process Application (post-consent) ─────────────────────────────────

@celery_app.task(
    name="tasks.process_application",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
)
def process_application(self, call_id: str, lead_id: str, card_name: str) -> dict:
    logger.info(f"[process_application] call_id={call_id} | card={card_name}")
    try:
        application_id = str(uuid.uuid4())
        create_application_record(
            application_id=application_id,
            call_id=call_id,
            lead_id=lead_id,
            card_name=card_name,
            status="pending_kyc",
            created_at=datetime.utcnow(),
        )
        send_sms_confirmation.delay(lead_id=lead_id, card_name=card_name)
        logger.info(f"Application created: {application_id}")
        return {"success": True, "application_id": application_id}
    except Exception as exc:
        logger.error(f"process_application failed: {exc}")
        raise self.retry(exc=exc)


# ── Task 3: Schedule Retry Call ────────────────────────────────────────────────

@celery_app.task(name="tasks.schedule_retry_call")
def schedule_retry_call(lead_id: str, delay_minutes: int = 60) -> None:
    logger.info(f"[schedule_retry_call] lead_id={lead_id} | delay={delay_minutes}m")
    make_outbound_call.apply_async(
        args=[lead_id],
        countdown=delay_minutes * 60,
    )


# ── Task 4: Send SMS Confirmation ──────────────────────────────────────────────

@celery_app.task(
    name="tasks.send_sms_confirmation",
    bind=True,
    max_retries=2,
)
def send_sms_confirmation(self, lead_id: str, card_name: str) -> dict:
    from twilio.rest import Client
    lead = get_lead_by_id(lead_id)
    if not lead or not lead.get("phone"):
        return {"success": False, "error": "No phone"}

    name = lead.get("name", "").split()[0]
    message = (
        f"Hi {name}! Your {card_name} application is submitted. "
        f"Our team will contact you in 24-48 hours for KYC. - QuickBank"
    )

    try:
        client = Client(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN"),
        )
        msg = client.messages.create(
            body=message,
            from_=os.getenv("TWILIO_FROM_NUMBER"),
            to=lead["phone"],
        )
        logger.info(f"SMS sent to {lead['phone']} | sid={msg.sid}")
        return {"success": True, "sms_sid": msg.sid}
    except Exception as exc:
        logger.error(f"SMS failed for lead {lead_id}: {exc}")
        raise self.retry(exc=exc)

@celery_app.task(name="tasks.dial_pending_leads")
def dial_pending_leads(batch_size: int = 5) -> dict:
    leads = get_pending_leads(limit=batch_size)
    if not leads:
        logger.info("No pending leads to dial.")
        return {"dialed": 0}

    count = 0
    for lead in leads:
        make_outbound_call.delay(str(lead["id"]))
        count += 1

    logger.info(f"Queued {count} calls from pending leads")
    return {"dialed": count}