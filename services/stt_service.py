"""
services/stt_service.py   ← NOTE: stt (Speech-To-Text), not sst

faster-whisper local STT — completely FREE, no API key.
Downloads model once (~145MB for 'base'), cached after that.

Install: pip install faster-whisper httpx
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")
_model = None


def _get_model():
    """Lazy-load Whisper model (downloaded once, then cached in RAM)."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        logger.info(f"Loading Whisper '{WHISPER_MODEL_SIZE}'...")
        _model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
        logger.info("Whisper ready.")
    return _model


def transcribe_audio_file(audio_path: str) -> str:
    """
    Transcribe a local audio file (MP3, WAV, OGG...).
    Returns transcribed text string.
    """
    model = _get_model()
    segments, info = model.transcribe(
        audio_path,
        language="en",
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )
    transcript = " ".join(seg.text.strip() for seg in segments)
    logger.info(f"Transcribed ({info.duration:.1f}s): '{transcript[:80]}'")
    return transcript.strip()


def transcribe_from_url(recording_url: str, twilio_auth: Optional[tuple] = None) -> str:
    """
    Download a Twilio recording URL and transcribe it.
    twilio_auth = (account_sid, auth_token)
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token  = os.getenv("TWILIO_AUTH_TOKEN")
    auth = twilio_auth or (account_sid, auth_token)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        logger.info(f"Downloading recording: {recording_url}")
        with httpx.Client(auth=auth, timeout=30) as client:
            r = client.get(recording_url)
            r.raise_for_status()
        with open(tmp_path, "wb") as f:
            f.write(r.content)
        return transcribe_audio_file(tmp_path)
    except Exception as e:
        logger.error(f"STT from URL failed: {e}")
        raise RuntimeError(f"Transcription failed: {e}") from e
    finally:
        Path(tmp_path).unlink(missing_ok=True)