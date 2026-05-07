"""
services/twilio_service.py

Handles:
  1. Making outbound calls via Twilio REST API
  2. Building TwiML responses for each call turn

Install: pip install twilio

Required .env vars:
  TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxx
  TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxx
  TWILIO_FROM_NUMBER=+1XXXXXXXXXX          (your Twilio trial number)
  SERVER_BASE_URL=https://your-ngrok-url.io  (public URL for webhooks + audio)
"""

import logging
import os

from twilio.rest import Client
from twilio.twiml.voice_response import Gather, Play, Say, VoiceResponse, Hangup

logger = logging.getLogger(__name__)

# ── Twilio client ───────────────────────────────────────────────────────────────

def _get_client() -> Client:
    return Client(
        os.getenv("TWILIO_ACCOUNT_SID"),
        os.getenv("TWILIO_AUTH_TOKEN"),
    )


def get_base_url() -> str:
    url = os.getenv("SERVER_BASE_URL", "").rstrip("/")
    if not url:
        raise RuntimeError("SERVER_BASE_URL not set in environment")
    return url


# ── Outbound call ───────────────────────────────────────────────────────────────

def make_outbound_call(to_number: str, call_id: str) -> str:
    """
    Initiate an outbound call to `to_number`.

    When Twilio connects, it hits our webhook: POST /voice/answer/{call_id}
    which returns TwiML to play intro + gather customer speech.

    Returns:
        twilio_call_sid (str)
    """
    client = _get_client()
    base_url = get_base_url()

    call = client.calls.create(
        to=to_number,
        from_=os.getenv("TWILIO_FROM_NUMBER"),
        url=f"{base_url}/voice/answer/{call_id}",       # answer webhook
        status_callback=f"{base_url}/voice/status/{call_id}",  # call events
        status_callback_method="POST",
        method="POST",
        timeout=30,           # ring for 30 seconds max
        machine_detection="Enable",  # detect voicemail/answering machine
    )

    logger.info(f"Outbound call initiated | call_id={call_id} | sid={call.sid} | to={to_number}")
    return call.sid


# ── TwiML builders ──────────────────────────────────────────────────────────────

def twiml_play_and_gather(audio_filename: str, gather_action_url: str, timeout: int = 5) -> str:
    """
    TwiML that:
      1. Plays an audio file (our TTS response)
      2. Records customer speech (sends to gather_action_url)

    Args:
        audio_filename: filename in static/audio/ (e.g. "abc123.mp3")
        gather_action_url: full URL for next turn (e.g. /voice/gather/{call_id})
        timeout: seconds to wait for speech before timeout action

    Returns:
        TwiML XML string
    """
    base_url = get_base_url()
    audio_url = f"{base_url}/audio/{audio_filename}"

    response = VoiceResponse()

    gather = Gather(
        input="speech",
        action=gather_action_url,
        method="POST",
        timeout=timeout,
        speech_timeout="auto",
        language="en-IN",
        profanity_filter=False,      # don't filter — we need raw transcript
    )

    gather.play(audio_url)
    response.append(gather)

    # If customer doesn't speak at all → reprompt once
    response.say(
        "Hello? Are you still there? Please go ahead.",
        voice="Polly.Aditi",         # AWS Polly Indian voice (free with Twilio)
        language="en-IN",
    )
    response.redirect(gather_action_url, method="POST")

    return str(response)


def twiml_say_and_gather(text: str, gather_action_url: str, timeout: int = 5) -> str:
    """
    Fallback TwiML using Twilio's built-in <Say> (no TTS file needed).
    Use when Edge-TTS fails or for quick responses.
    """
    response = VoiceResponse()

    gather = Gather(
        input="speech",
        action=gather_action_url,
        method="POST",
        timeout=timeout,
        speech_timeout="auto",
        language="en-IN",
    )

    gather.say(text, voice="Polly.Aditi", language="en-IN")
    response.append(gather)

    return str(response)


def twiml_end_call(farewell_audio_filename: str = None, farewell_text: str = None) -> str:
    """
    TwiML to play farewell message then hang up.
    Use either audio file or text (not both).
    """
    base_url = get_base_url()
    response = VoiceResponse()

    if farewell_audio_filename:
        audio_url = f"{base_url}/audio/{farewell_audio_filename}"
        response.play(audio_url)
    elif farewell_text:
        response.say(farewell_text, voice="Polly.Aditi", language="en-IN")

    response.hangup()
    return str(response)


def twiml_voicemail_detected() -> str:
    """TwiML when answering machine/voicemail is detected — just hang up."""
    response = VoiceResponse()
    response.say(
        "Please call QuickBank at 1800-XXX-XXXX for exclusive credit card offers.",
        voice="Polly.Aditi",
        language="en-IN",
    )
    response.hangup()
    return str(response)


# ── Call management ──────────────────────────────────────────────────────────────

def end_call(twilio_call_sid: str) -> None:
    """Force-end a live call via Twilio API."""
    try:
        client = _get_client()
        client.calls(twilio_call_sid).update(status="completed")
        logger.info(f"Call ended: {twilio_call_sid}")
    except Exception as e:
        logger.warning(f"Could not end call {twilio_call_sid}: {e}")