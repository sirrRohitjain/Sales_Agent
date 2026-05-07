"""
services/tts_service.py

Text-to-Speech using Microsoft Edge-TTS (FREE).
Voice: en-IN-NeerjaNeural  — Indian English female, natural tone.

Install: pip install edge-tts
"""

import asyncio
import logging
import os
import uuid
from pathlib import Path

import edge_tts

logger = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────────────
VOICE    = "en-IN-NeerjaNeural"
AUDIO_DIR = Path("static/audio")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


# ── Sync version (used by tests + Celery tasks) ─────────────────────────────────

def text_to_speech(text: str) -> str:
    """
    Convert text → MP3. Returns filename (e.g. 'abc123.mp3').
    File saved to static/audio/{filename}.
    """
    filename = f"{uuid.uuid4().hex}.mp3"
    filepath = AUDIO_DIR / filename
    try:
        asyncio.run(_generate(text, str(filepath)))
        logger.info(f"TTS OK: {filename} ({len(text)} chars)")
        return filename
    except Exception as e:
        logger.error(f"TTS failed: {e}")
        raise RuntimeError(f"TTS generation failed: {e}") from e


# ── Async version (used in FastAPI route handlers) ──────────────────────────────

async def text_to_speech_async(text: str) -> str:
    """
    Async version — use inside async FastAPI routes.
    Returns filename (str).
    """
    filename = f"{uuid.uuid4().hex}.mp3"
    filepath = AUDIO_DIR / filename
    await _generate(text, str(filepath))
    logger.info(f"TTS async OK: {filename}")
    return filename


# ── Cleanup ─────────────────────────────────────────────────────────────────────

def cleanup_audio_file(filename: str) -> None:
    """Delete audio file after Twilio has played it."""
    try:
        path = AUDIO_DIR / filename
        if path.exists():
            path.unlink()
            logger.debug(f"Deleted audio: {filename}")
    except Exception as e:
        logger.warning(f"Could not delete {filename}: {e}")


# ── Internal ─────────────────────────────────────────────────────────────────────

async def _generate(text: str, filepath: str) -> None:
    communicate = edge_tts.Communicate(text=text, voice=VOICE)
    await communicate.save(filepath)