"""Microphone audio recorder using PyAudio.

Handles real-time audio capture with silence detection
and automatic chunking for speech recognition.
"""

import threading
import time
import wave
import tempfile
import os
import numpy as np


class AudioRecorder:
    """Record audio from the microphone with silence detection."""

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        silence_threshold: float = 500,
        max_duration: float = 30.0,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.silence_threshold = silence_threshold
        self._default_threshold = silence_threshold
        self.max_duration = max_duration
        self._recording = False
        self._frames = []
        self._lock = threading.Lock()
        # Guards PyAudio stream open/close so start_recording and
        # stop_recording can never run concurrently (a race that crashes
        # the whole app with a native error from PyAudio). Reentrant so
        # stop_recording -> _close_stream works without deadlocking.
        self._io_lock = threading.RLock()
        self._stream = None
        self._pyaudio = None

    def _import_pyaudio(self):
        """Lazy import PyAudio."""
        try:
            import pyaudio
        except ImportError as exc:
            raise RuntimeError(
                "PyAudio not installed. Run: pip install pyaudio"
            ) from exc
        return pyaudio

    def _calculate_silence_threshold(self, pyaudio, stream) -> float:
        """Dynamically calculate a baseline noise threshold."""
        # Record a short sample to determine ambient noise
        samples = []
        for _ in range(5):
            data = stream.read(1024, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16)
            samples.append(np.abs(audio_data).mean())
        if samples:
            baseline = float(np.mean(samples))
            return max(baseline * 2.0, 500.0)
        return self.silence_threshold

    def start_recording(self, dynamic_threshold: bool = True) -> None:
        """Start recording from the microphone."""
        with self._io_lock:
            if self._recording:
                return

            pyaudio_mod = self._import_pyaudio()
            self._pyaudio = pyaudio_mod.PyAudio()

            try:
                self._stream = self._pyaudio.open(
                    format=pyaudio_mod.paInt16,
                    channels=self.channels,
                    rate=self.sample_rate,
                    input=True,
                    frames_per_buffer=1024,
                )
                if dynamic_threshold:
                    self.silence_threshold = self._calculate_silence_threshold(
                        pyaudio_mod, self._stream
                    )
            except OSError as exc:
                raise RuntimeError(
                    "No microphone detected or microphone is in use."
                ) from exc

            self._frames = []
            self._recording = True

        self._record_thread = threading.Thread(
            target=self._record_loop, daemon=True
        )
        self._record_thread.start()

    def _record_loop(self) -> None:
        """Internal recording loop that captures audio with silence detection."""
        silence_frames = 0
        speech_started = False
        recorded_frames = []
        start_time = time.time()

        while self._recording:
            try:
                data = self._stream.read(1024, exception_on_overflow=False)
                audio_data = np.frombuffer(data, dtype=np.int16)
                amplitude = np.abs(audio_data).mean()

                with self._lock:
                    recorded_frames.append(data)

                if amplitude > self.silence_threshold:
                    silence_frames = 0
                    speech_started = True
                else:
                    silence_frames += 1
                    if (
                        speech_started
                        and silence_frames > int(
                            self.sample_rate / 1024
                        )
                    ):
                        # Enough silence after speech -> stop
                        break

                # Check max duration
                if time.time() - start_time > self.max_duration:
                    break

            except (OSError, IOError):
                # Stream may be closed
                break

        self._frames = recorded_frames
        self._close_stream()
        self._recording = False

    def _close_stream(self) -> None:
        """Close the audio stream and PyAudio instance without clearing frames."""
        with self._io_lock:
            if self._stream:
                try:
                    self._stream.stop_stream()
                    self._stream.close()
                except OSError:
                    pass
                self._stream = None

            if self._pyaudio:
                try:
                    self._pyaudio.terminate()
                except Exception:
                    pass
                self._pyaudio = None

    def stop_recording(self) -> bytes | None:
        """Stop recording and return the raw audio data."""
        with self._io_lock:
            if not self._recording and not self._frames:
                return None

            self._recording = False
            self._close_stream()

        with self._lock:
            if not self._frames:
                return None
            audio_data = b"".join(self._frames)
            self._frames = []
        return audio_data

    def reset(self) -> None:
        """Hard-reset the recorder (used after system sleep/resume).

        Closes any stale PyAudio stream, clears captured frames and restores
        the configured silence threshold. The next start_recording() will
        then open a brand-new PyAudio instance, which is what Windows needs
        after the audio devices have been re-enumerated on resume.
        """
        with self._io_lock:
            self._recording = False
            with self._lock:
                self._frames = []
            self._close_stream()
        self.silence_threshold = self._default_threshold

    def save_to_wav(self, filename: str | None = None) -> str | None:
        """Save the recorded audio to a WAV file."""
        audio_data = self.stop_recording()
        if audio_data is None:
            return None

        if filename is None:
            filename = os.path.join(tempfile.gettempdir(), "bangl_voice_temp.wav")

        with wave.open(filename, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_data)

        return filename
