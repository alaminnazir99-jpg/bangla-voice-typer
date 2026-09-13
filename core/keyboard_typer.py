"""System-wide keyboard typing.

Types text into any application (browser, MS Word, Notepad, etc.)
by simulating keyboard input using pynput.
"""

import time
import threading
import logging
from pynput.keyboard import Controller as KeyboardController
from pynput.keyboard import Key

logger = logging.getLogger(__name__)


class KeyboardTyper:
    """Types Unicode Bengali text into the focused application."""

    # Unicode -> key sequences for Bengali via pynput.
    # pynput can type unicode directly on Windows using the
    # TypeString method, which leverages SendInput.
    MAX_CHARS_PER_ACTION = 10000  # Safety limit

    def __init__(self, typing_speed: str = "fast"):
        self.keyboard = KeyboardController()
        self.typing_speed = typing_speed
        self._type_delay = self._compute_delay(typing_speed)
        self._press_duration = 0.01
        self._lock = threading.Lock()

    def _compute_delay(self, speed: str) -> float:
        """Compute delay between key events based on speed setting."""
        speeds = {
            "slow": 0.05,
            "normal": 0.02,
            "fast": 0.005,
            "instant": 0.001,
        }
        return speeds.get(speed, 0.02)

    def set_speed(self, speed: str) -> None:
        """Change typing speed dynamically."""
        self.typing_speed = speed
        self._type_delay = self._compute_delay(speed)

    def type_text(self, text: str) -> bool:
        """Type the given Unicode text into the focused window."""
        if not text:
            return False

        with self._lock:
            try:
                self._type_unicode_safe(text)
                return True
            except Exception as exc:
                logger.error("Typing error: %s", exc)
                return False

    def _type_unicode_safe(self, text: str) -> None:
        """Type text handling Unicode characters safely."""
        # pynput's keyboard.type() handles Unicode via VK on Windows
        # but can be slow for large text; chunk it to avoid lag
        chunk_size = 500
        for i in range(0, len(text), chunk_size):
            chunk = text[i : i + chunk_size]
            self._type_chunk(chunk)
            # Small pause between chunks to prevent input lag
            if i + chunk_size < len(text):
                time.sleep(0.05)

    def _type_chunk(self, text: str) -> None:
        """Type a chunk of text using pynput type method."""
        # Use pynput's native type which handles Unicode
        self.keyboard.type(text)
        # Ensure the text was processed
        time.sleep(self._type_delay * len(text) if len(text) < 100 else 0.1)

    def type_key(self, key) -> None:
        """Send a single key press."""
        with self._lock:
            try:
                self.keyboard.press(key)
                time.sleep(self._press_duration)
                self.keyboard.release(key)
            except Exception as exc:
                logger.error("Key error: %s", exc)

    def type_enter(self) -> None:
        """Press Enter key."""
        self.type_key(Key.enter)

    def type_backspace(self, count: int = 1) -> None:
        """Press Backspace key multiple times."""
        with self._lock:
            for _ in range(count):
                self.keyboard.press(Key.backspace)
                time.sleep(self._press_duration)
                self.keyboard.release(Key.backspace)
                time.sleep(self._type_delay)

    def type_ctrl_a(self) -> None:
        """Select all (Ctrl+A)."""
        with self._lock:
            self.keyboard.press(Key.ctrl)
            self.keyboard.press("a")
            self.keyboard.release("a")
            self.keyboard.release(Key.ctrl)

    def type_ctrl_v(self) -> None:
        """Paste (Ctrl+V)."""
        with self._lock:
            self.keyboard.press(Key.ctrl)
            self.keyboard.press("v")
            self.keyboard.release("v")
            self.keyboard.release(Key.ctrl)

    def clear_field(self) -> None:
        """Select all and delete text in the focused field."""
        self.type_ctrl_a()
        self.type_key(Key.delete)

    def type_paste(self, text: str) -> bool:
        """Type text via clipboard copy-paste (faster, more reliable for Unicode).

        NOTE: On Windows, pynput 'can' handle Unicode with SendInput,
        but using the clipboard with '+'/'+' pasting is more robust.
        """
        import pyperclip

        # Save original clipboard
        original = None
        try:
            original = pyperclip.paste()
        except Exception:
            pass

        try:
            pyperclip.copy(text)
            time.sleep(0.05)
            self.type_ctrl_v()
            # Restore clipboard after a short delay
            if original is not None:
                threading.Timer(1.0, lambda: pyperclip.copy(original)).start()
            return True
        except Exception as exc:
            logger.error("Clipboard typing error: %s", exc)
            return False
