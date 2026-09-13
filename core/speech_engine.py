"""Speech recognition engine.

Supports three engines:
1. OpenAI Whisper (offline, best accuracy)
2. Vosk (offline, lightweight)
3. Google (online, free)

All output Bengali Unicode text.
"""

import os
import threading
import tempfile
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class SpeechEngine:
    """Speech recognition wrapper supporting multiple engines."""

    ENGINES = {
        "whisper": "OpenAI Whisper (Offline)",
        "google": "Google Speech (Online)",
        "vosk": "Vosk (Offline)",
    }

    def __init__(self, settings=None, on_status: Optional[Callable[[str], None]] = None):
        self.settings = settings
        self.on_status = on_status
        self._lock = threading.Lock()
        self._whisper_model = None
        self._vosk_model = None
        self._vosk_recognizer = None

    def _set_status(self, msg: str) -> None:
        """Send status update to UI."""
        if self.on_status:
            try:
                self.on_status(msg)
            except Exception:
                pass
        logger.debug("[STT] %s", msg)

    # ------------------------------------------------------------------
    # Engine selection
    # ------------------------------------------------------------------
    def get_available_engines(self) -> dict:
        """Return dict of engine name -> availability."""
        available = {}
        for name in self.ENGINES:
            try:
                available[name] = self._check_engine(name)
            except Exception:
                available[name] = False
        return available

    def _check_engine(self, engine: str) -> bool:
        if engine == "whisper":
            try:
                import whisper
                return True
            except ImportError:
                return False
        elif engine == "vosk":
            try:
                import vosk
                return True
            except ImportError:
                return False
        return True  # Google is always available if speechrecognition is installed

    # ------------------------------------------------------------------
    # Recognition
    # ------------------------------------------------------------------
    def recognize(
        self, audio_data: bytes = None, wav_path: str = None, engine: str = None
    ) -> str:
        """Recognize speech from raw audio bytes or a WAV file path."""
        if engine is None:
            engine = (
                self.settings.get("speech", "engine", "whisper")
                if self.settings else "whisper"
            )

        engine = self._normalize_engine(engine)

        with self._lock:
            self._set_status("প্রসেসিং হচ্ছে...")
            try:
                if engine == "whisper":
                    return self._recognize_whisper(wav_path, audio_data)
                elif engine == "vosk":
                    return self._recognize_vosk(audio_data, wav_path)
                elif engine == "google":
                    return self._recognize_google(wav_path, audio_data)
                return ""
            except Exception as exc:
                self._set_status(f"ত্রুটি: {exc}")
                logger.error("Recognition error: %s", exc)
                return ""

    def _normalize_engine(self, engine: str) -> str:
        """Normalize engine name."""
        if engine == "whisper":
            try:
                import whisper
                return "whisper"
            except ImportError:
                pass
        if engine == "vosk":
            try:
                import vosk
                return "vosk"
            except ImportError:
                pass
        return "google"

    def _recognize_whisper(
        self, wav_path: str = None, audio_data: bytes = None
    ) -> str:
        """Use OpenAI Whisper for recognition."""
        import whisper

        if self._whisper_model is None:
            model_name = (
                self.settings.get("speech", "whisper_model", "small")
                if self.settings
                else "small"
            )
            self._set_status(f"Whisper মডেল লোড হচ্ছে ({model_name})...")
            self._whisper_model = whisper.load_model(model_name)

        if wav_path is None and audio_data is not None:
            wav_path = self._write_temp_wav(audio_data)

        self._set_status("শোনা হচ্ছে...")
        result = self._whisper_model.transcribe(
            wav_path,
            language="bn",
            fp16=False,
            task="transcribe",
        )
        text = (result.get("text") or "").strip()
        if wav_path and (
            wav_path.startswith(tempfile.gettempdir()) or "bangl_voice_temp" in wav_path
        ):
            try:
                os.remove(wav_path)
            except OSError:
                pass
        return text

    def _recognize_vosk(self, audio_data: bytes = None, wav_path: str = None) -> str:
        """Use Vosk for offline recognition."""
        import vosk
        from scipy.io import wavfile

        if self._vosk_model is None:
            model_path = os.path.join(
                os.path.expanduser("~"), "vosk-models", "vosk-model-small-bn-0.2"
            )
            if not os.path.exists(model_path):
                self._set_status(
                    "Vosk বাংলা মডেল পাওয়া যায়নি। ডাউনলোড করুন: "
                    "https://alphacephei.com/vosk/models"
                )
                return ""
            self._set_status("Vosk মডেল লোড হচ্ছে...")
            self._vosk_model = vosk.Model(model_path)

        if self._vosk_recognizer is None:
            self._vosk_recognizer = vosk.KaldiRecognizer(
                self._vosk_model, self.settings.get("speech", "sample_rate", 16000)
                if self.settings else 16000
            )

        if wav_path is None and audio_data is not None:
            wav_path = self._write_temp_wav(audio_data)

        if wav_path is None:
            return ""

        sample_rate, data = wavfile.read(wav_path)
        wav_bytes = data.tobytes()
        if self._vosk_recognizer.AcceptWaveform(wav_bytes):
            result = self._vosk_recognizer.Result()
        else:
            result = self._vosk_recognizer.FinalResult()

        import json as jsonlib
        try:
            parsed = jsonlib.loads(result)
            return (parsed.get("text") or "").strip()
        except jsonlib.JSONDecodeError:
            return ""
        finally:
            if wav_path.startswith(tempfile.gettempdir()) or "bangl_voice_temp" in wav_path:
                try:
                    os.remove(wav_path)
                except OSError:
                    pass

    def _recognize_google(
        self, wav_path: str = None, audio_data: bytes = None
    ) -> str:
        """Use Google Speech Recognition (online)."""
        import speech_recognition as sr

        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 300
        recognizer.dynamic_energy_threshold = True

        if audio_data is not None:
            wav_path = self._write_temp_wav(audio_data)

        self._set_status("Google সার্ভারে পাঠানো হচ্ছে...")
        with sr.AudioFile(wav_path) as source:
            audio = recognizer.record(source)

        try:
            text = recognizer.recognize_google(
                audio, language="bn-BD"
            )
            return text.strip()
        except sr.UnknownValueError:
            self._set_status("কথা শনাক্ত করা যায়নি")
            return ""
        except sr.RequestError as exc:
            self._set_status(f"Google API ত্রুটি: {exc}")
            return ""
        finally:
            if wav_path and wav_path.startswith(tempfile.gettempdir()):
                try:
                    os.remove(wav_path)
                except OSError:
                    pass

    def _write_temp_wav(self, audio_data: bytes) -> str:
        """Write raw PCM audio bytes to a temporary WAV file."""
        import wave

        path = os.path.join(
            tempfile.gettempdir(), "bangl_voice_temp.wav"
        )
        sample_rate = (
            self.settings.get("speech", "sample_rate", 16000)
            if self.settings else 16000
        )
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            if isinstance(audio_data, list):
                audio_data = b"".join(audio_data)
            wf.writeframes(audio_data)
        return path
