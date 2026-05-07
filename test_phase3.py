"""
tests/test_phase3.py  — FIXED VERSION

Fixes applied:
  1. sst_service → stt_service (filename corrected)
  2. @patch paths updated to match actual module locations
  3. __init__.py presence assumed in routes/, tasks/, services/

Run:
  pytest tests/test_phase3.py -v
  pytest tests/test_phase3.py::TestTTSService -v      # just TTS
  pytest tests/test_phase3.py::TestTwilioService -v   # just TwiML
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from db import db_utils
from routes import lead_routes, voice_routes
from services import tts_service, stt_service, twilio_service
from services import *      # to check for import errors in __init__.py     
from tasks import celery_tasks
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))


# ─────────────────────────────────────────────────────────────────────────────
# 1. TTS SERVICE
# ─────────────────────────────────────────────────────────────────────────────

class TestTTSService:

    def test_tts_generates_file(self):
        """Edge-TTS creates a real .mp3 file."""
        from services.tts_service import text_to_speech, AUDIO_DIR

        filename = text_to_speech("Hi, this is Priya from QuickBank!")
        filepath = AUDIO_DIR / filename

        assert filename.endswith(".mp3")
        assert filepath.exists(), f"File not found: {filepath}"
        assert filepath.stat().st_size > 1000, "File too small"
        print(f"\n  ✓ {filepath} ({filepath.stat().st_size} bytes)")
        filepath.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_tts_async_generates_file(self):
        """Async TTS version works."""
        from services.tts_service import text_to_speech_async, AUDIO_DIR

        filename = await text_to_speech_async("Testing async.")
        filepath = AUDIO_DIR / filename
        assert filepath.exists()
        filepath.unlink(missing_ok=True)

    def test_tts_cleanup(self):
        """cleanup_audio_file deletes the file."""
        from services.tts_service import cleanup_audio_file, AUDIO_DIR

        dummy = AUDIO_DIR / "test_cleanup_dummy.mp3"
        dummy.write_text("dummy")
        cleanup_audio_file("test_cleanup_dummy.mp3")
        assert not dummy.exists()

    def test_tts_cleanup_nonexistent(self):
        """cleanup_audio_file doesn't crash on missing file."""
        from services.tts_service import cleanup_audio_file
        cleanup_audio_file("does_not_exist_xyz.mp3")   # should not raise


# ─────────────────────────────────────────────────────────────────────────────
# 2. STT SERVICE
# ─────────────────────────────────────────────────────────────────────────────

class TestSTTService:

    def test_stt_model_loads(self):
        """Whisper model loads without error."""
        from services.stt_service import _get_model      # ← stt not sst
        model = _get_model()
        assert model is not None
        print(f"\n  ✓ Whisper model loaded")

    def test_stt_transcribes_file(self):
        """Transcribe a TTS-generated audio file end-to-end."""
        from services.tts_service import text_to_speech, AUDIO_DIR
        from services.stt_service import transcribe_audio_file  # ← stt not sst

        text = "Yes I am interested in the credit card offer."
        filename = text_to_speech(text)
        filepath = str(AUDIO_DIR / filename)

        result = transcribe_audio_file(filepath)
        print(f"\n  Original:    '{text}'")
        print(f"  Transcribed: '{result}'")

        assert len(result) > 5
        assert any(w in result.lower() for w in ["yes", "interested", "credit", "card"])
        Path(filepath).unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# 3. TWILIO SERVICE  (no real calls — TwiML XML only)
# ─────────────────────────────────────────────────────────────────────────────

class TestTwilioService:

    @pytest.fixture(autouse=True)
    def set_env(self, monkeypatch):
        monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest123")
        monkeypatch.setenv("TWILIO_AUTH_TOKEN",  "test_token")
        monkeypatch.setenv("TWILIO_FROM_NUMBER", "+919999999999")
        monkeypatch.setenv("SERVER_BASE_URL",    "https://test.ngrok.io")

    def test_twiml_play_and_gather(self):
        from services.twilio_service import twiml_play_and_gather
        xml = twiml_play_and_gather("test.mp3", "https://test.ngrok.io/voice/gather/abc")
        assert "<Gather" in xml
        assert "<Play>" in xml
        assert "test.mp3" in xml
        print(f"\n  TwiML play+gather OK")

    def test_twiml_say_and_gather(self):
        from services.twilio_service import twiml_say_and_gather
        xml = twiml_say_and_gather("Hello Priya here.", "https://test.ngrok.io/voice/gather/abc")
        assert "<Gather" in xml
        assert "<Say" in xml
        assert "Priya" in xml

    def test_twiml_end_call(self):
        from services.twilio_service import twiml_end_call
        xml = twiml_end_call(farewell_text="Thank you! Have a great day.")
        assert "<Hangup" in xml
        assert "Thank you" in xml

    def test_twiml_voicemail(self):
        from services.twilio_service import twiml_voicemail_detected
        xml = twiml_voicemail_detected()
        assert "<Hangup" in xml

    @patch("services.twilio_service.Client")
    def test_make_outbound_call(self, mock_client_class):
        from services.twilio_service import make_outbound_call

        mock_client = MagicMock()
        mock_client.calls.create.return_value = MagicMock(sid="CA_MOCK_SID_99")
        mock_client_class.return_value = mock_client

        sid = make_outbound_call(to_number="+919876543210", call_id="test-call-id")
        assert sid == "CA_MOCK_SID_99"
        call_kwargs = mock_client.calls.create.call_args[1]
        assert call_kwargs["to"] == "+919876543210"
        assert "test-call-id" in call_kwargs["url"]
        print(f"\n  ✓ Outbound call mock SID: {sid}")


# ─────────────────────────────────────────────────────────────────────────────
# 4. VOICE ROUTES  (FastAPI TestClient)
# ─────────────────────────────────────────────────────────────────────────────

class TestVoiceRoutes:

    @pytest.fixture
    def client(self, monkeypatch):
        monkeypatch.setenv("SERVER_BASE_URL", "https://test.ngrok.io")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        from main import app
        return TestClient(app)

    @pytest.fixture
    def mock_session(self):
        return {
            "graph_state": {
                "call_id":        "test-call-123",
                "lead": {
                    "id": "lead-001", "name": "Amit Kumar",
                    "phone": "+919876543210", "income": 60000,
                    "credit_score": 720, "employment_type": "salaried",
                },
                "messages":         [],
                "current_node":     "intro",
                "turn_count":       0,
                "next_action":      None,
                "objection_count":  0,
                "extracted_data":   {},
                "card_recommended": None,
                "consent_given":    False,
                "call_start_time":  "2025-01-01T10:00:00",
                "error":            None,
            }
        }

    # ── patch paths use the module where the name is USED (not defined) ───────
    @patch("routes.voice_routes.text_to_speech_async")
    @patch("routes.voice_routes.build_graph")
    @patch("routes.voice_routes.session_manager")
    def test_answer_human(self, mock_sm, mock_graph_fn, mock_tts, client, mock_session):
        mock_sm.get_session  = AsyncMock(return_value=mock_session)
        mock_sm.save_session = AsyncMock()

        g = MagicMock()
        g.invoke.return_value = {
            **mock_session["graph_state"],
            "messages": [{"role": "assistant", "content": "Hi Amit! Priya here."}],
            "current_node": "intro",
        }
        mock_graph_fn.return_value = g
        mock_tts.return_value = "intro.mp3"

        r = client.post("/voice/answer/test-call-123", data={
            "AnsweredBy": "human", "CallSid": "CA001", "CallStatus": "in-progress"
        })
        assert r.status_code == 200
        assert "<Gather" in r.text
        assert "intro.mp3" in r.text
        print(f"\n  ✓ Answer (human) — Gather returned")

    @patch("routes.voice_routes.session_manager")
    def test_answer_voicemail(self, mock_sm, client):
        mock_sm.get_session = AsyncMock(return_value={"graph_state": {}})
        r = client.post("/voice/answer/test-call-123", data={
            "AnsweredBy": "machine_start", "CallSid": "CA001"
        })
        assert r.status_code == 200
        assert "<Hangup" in r.text
        print(f"\n  ✓ Answer (voicemail) — Hangup returned")

    @patch("routes.voice_routes.text_to_speech_async")
    @patch("routes.voice_routes.build_graph")
    @patch("routes.voice_routes.session_manager")
    def test_gather_yes(self, mock_sm, mock_graph_fn, mock_tts, client, mock_session):
        mock_sm.get_session  = AsyncMock(return_value=mock_session)
        mock_sm.save_session = AsyncMock()

        g = MagicMock()
        g.invoke.return_value = {
            **mock_session["graph_state"],
            "messages": [
                {"role": "user",      "content": "Yes interested"},
                {"role": "assistant", "content": "Great! Gold card for you."},
            ],
            "current_node": "recommend",
            "next_action":  "confirm",
        }
        mock_graph_fn.return_value = g
        mock_tts.return_value = "recommend.mp3"

        r = client.post("/voice/gather/test-call-123",
                        data={"SpeechResult": "Yes interested", "Confidence": "0.95"})
        assert r.status_code == 200
        assert "<Gather" in r.text
        print(f"\n  ✓ Gather (yes) — Gather returned")

    @patch("routes.voice_routes.text_to_speech_async")
    @patch("routes.voice_routes.build_graph")
    @patch("routes.voice_routes.session_manager")
    def test_gather_end(self, mock_sm, mock_graph_fn, mock_tts, client, mock_session):
        mock_sm.get_session  = AsyncMock(return_value=mock_session)
        mock_sm.save_session = AsyncMock()

        g = MagicMock()
        g.invoke.return_value = {
            **mock_session["graph_state"],
            "messages": [{"role": "assistant", "content": "Thanks! Team calls in 24h."}],
            "current_node": "save_to_db",
            "next_action":  "end",
            "consent_given": True,
        }
        mock_graph_fn.return_value = g
        mock_tts.return_value = "farewell.mp3"

        r = client.post("/voice/gather/test-call-123",
                        data={"SpeechResult": "yes go ahead", "Confidence": "0.97"})
        assert r.status_code == 200
        assert "<Hangup" in r.text
        print(f"\n  ✓ Gather (end) — Hangup returned")

    @patch("routes.voice_routes.session_manager")
    def test_gather_no_speech(self, mock_sm, client, mock_session):
        mock_sm.get_session = AsyncMock(return_value=mock_session)
        r = client.post("/voice/gather/test-call-123",
                        data={"SpeechResult": "", "Confidence": "0.0"})
        assert r.status_code == 200
        assert "<Gather" in r.text   # reprompt
        print(f"\n  ✓ No-speech — reprompt returned")

    @patch("routes.voice_routes.session_manager")
    @patch("routes.voice_routes.update_call_status")
    def test_status_completed(self, mock_update, mock_sm, client):
        mock_update.return_value = None
        mock_sm.delete_session   = AsyncMock()
        r = client.post("/voice/status/test-call-123", data={
            "CallStatus": "completed", "CallDuration": "62", "CallSid": "CA001"
        })
        assert r.status_code == 200
        print(f"\n  ✓ Status (completed) — OK")


# ─────────────────────────────────────────────────────────────────────────────
# 5. CELERY TASKS
# ─────────────────────────────────────────────────────────────────────────────

class TestCeleryTasks:

    @patch("tasks.celery_tasks.update_call_status")
    @patch("tasks.celery_tasks.create_call_record")
    @patch("tasks.celery_tasks.session_manager")
    @patch("tasks.celery_tasks.twilio_dial")       # patched where imported inside task
    @patch("tasks.celery_tasks.get_lead_by_id")
    def test_success(self, mock_lead, mock_dial, mock_sm, mock_create, mock_update):
        from tasks.celery_tasks import make_outbound_call

        mock_lead.return_value = {
            "id": "lead-001", "name": "Priya Sharma",
            "phone": "+919876543210", "income": 55000,
            "credit_score": 710, "employment_type": "salaried",
        }
        mock_sm.acquire_lead_lock = AsyncMock(return_value=True)
        mock_sm.create_session    = AsyncMock()
        mock_dial.return_value    = "CA_MOCK_99"

        result = make_outbound_call.run("lead-001")
        assert result["success"] is True
        assert result["twilio_sid"] == "CA_MOCK_99"
        print(f"\n  ✓ Task success: {result}")

    @patch("tasks.celery_tasks.get_lead_by_id")
    def test_lead_not_found(self, mock_lead):
        from tasks.celery_tasks import make_outbound_call
        mock_lead.return_value = None
        result = make_outbound_call.run("bad-id")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @patch("tasks.celery_tasks.get_lead_by_id")
    def test_no_phone(self, mock_lead):
        from tasks.celery_tasks import make_outbound_call
        mock_lead.return_value = {"id": "lead-002", "name": "Test", "phone": None}
        result = make_outbound_call.run("lead-002")
        assert result["success"] is False


# ─────────────────────────────────────────────────────────────────────────────
# 6. FULL FLOW INTEGRATION
# ─────────────────────────────────────────────────────────────────────────────

class TestFullVoiceFlow:
    CALL_ID = "integration-999"
    LEAD = {
        "id": "lead-int", "name": "Rohit Jain",
        "phone": "+919876543210", "income": 65000,
        "credit_score": 730, "employment_type": "salaried",
    }

    def _state(self, node, msgs, consent=False):
        return {
            "call_id": self.CALL_ID, "lead": self.LEAD,
            "messages": msgs, "current_node": node,
            "turn_count": len(msgs), "objection_count": 0,
            "next_action": "end" if node == "save_to_db" else "continue",
            "extracted_data": {"consent_given": consent},
            "card_recommended": "QuickBank Gold Rewards Card",
            "consent_given": consent,
            "call_start_time": "2025-01-01T10:00:00",
            "error": None,
        }

    @patch("routes.voice_routes.text_to_speech_async")
    @patch("routes.voice_routes.build_graph")
    @patch("routes.voice_routes.session_manager")
    def test_full_call_flow(self, mock_sm, mock_graph_fn, mock_tts, monkeypatch):
        monkeypatch.setenv("SERVER_BASE_URL", "https://test.ngrok.io")
        from main import app
        client = TestClient(app)

        store = {}

        async def get(call_id):
            return store.get(call_id, {"graph_state": self._state("intro", [])})

        async def save(call_id, data):
            store[call_id] = data

        mock_sm.get_session  = get
        mock_sm.save_session = save
        mock_sm.delete_session = AsyncMock()
        mock_tts.return_value = "audio.mp3"

        graph = MagicMock()
        mock_graph_fn.return_value = graph

        # Turn 0 — answer
        graph.invoke.return_value = self._state("intro", [
            {"role": "assistant", "content": "Hi Rohit! Priya from QuickBank."}
        ])
        r0 = client.post(f"/voice/answer/{self.CALL_ID}", data={
            "AnsweredBy": "human", "CallSid": "CA001"
        })
        assert r0.status_code == 200 and "<Gather" in r0.text
        print("\n  Turn 0 (answer): ✓")

        # Turn 1 — yes
        graph.invoke.return_value = self._state("recommend", [
            {"role": "assistant", "content": "Gold card — 3x rewards!"}
        ])
        r1 = client.post(f"/voice/gather/{self.CALL_ID}",
                         data={"SpeechResult": "Yes I'm interested", "Confidence": "0.94"})
        assert r1.status_code == 200 and "<Gather" in r1.text
        print("  Turn 1 (yes):    ✓")

        # Turn 2 — confirm
        graph.invoke.return_value = self._state("confirm", [
            {"role": "assistant", "content": "Great! Shall I go ahead?"}
        ], consent=True)
        r2 = client.post(f"/voice/gather/{self.CALL_ID}",
                         data={"SpeechResult": "Yes please", "Confidence": "0.97"})
        assert r2.status_code == 200
        print("  Turn 2 (confirm): ✓")

        # Turn 3 — hangup
        graph.invoke.return_value = self._state("save_to_db", [
            {"role": "assistant", "content": "Thank you Rohit! Have a great day!"}
        ], consent=True)
        r3 = client.post(f"/voice/gather/{self.CALL_ID}",
                         data={"SpeechResult": "thank you", "Confidence": "0.90"})
        assert r3.status_code == 200 and "<Hangup" in r3.text
        print("  Turn 3 (hangup):  ✓")
        print("\n  ✅ Full call flow passed!")


# ─────────────────────────────────────────────────────────────────────────────
# SMOKE TEST  — python tests/test_phase3.py
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  PHASE 3 SMOKE TEST")
    print("="*60)

    checks = [
        ("TTS import",  "from services.tts_service import text_to_speech, text_to_speech_async, cleanup_audio_file, AUDIO_DIR"),
        ("STT import",  "from services.stt_service import transcribe_audio_file, _get_model"),
        ("Twilio import","from services.twilio_service import twiml_play_and_gather, make_outbound_call"),
        ("Voice routes","from routes.voice_routes import router"),
        ("Celery tasks","from tasks.celery_tasks import make_outbound_call, celery_app"),
    ]
    for name, stmt in checks:
        try:
            exec(stmt)
            print(f"  ✅ {name}")
        except Exception as e:
            print(f"  ❌ {name}: {e}")

    print("\n[TTS live test]")
    try:
        from services.tts_service import text_to_speech, AUDIO_DIR
        f = text_to_speech("Hi Rohit! This is Priya from QuickBank.")
        fp = AUDIO_DIR / f
        print(f"  ✅ TTS OK → {fp} ({fp.stat().st_size} bytes)")
        fp.unlink()
    except Exception as e:
        print(f"  ❌ TTS: {e}")

    print("\n[Whisper model load]")
    try:
        from services.stt_service import _get_model
        _get_model()
        print("  ✅ Whisper loaded")
    except Exception as e:
        print(f"  ❌ Whisper: {e}")

    print("\n" + "="*60)
    print("  Full tests: pytest tests/test_phase3.py -v")
    print("="*60 + "\n")