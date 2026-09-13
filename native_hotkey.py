"""Windows-native global hotkey support.

Uses RegisterHotKey + a Qt native event filter. This is far more reliable
than the 'keyboard' package for a background/system-wide hotkey like
Ctrl+Shift+B, and it does not require administrator rights.
"""

import ctypes
import ctypes.wintypes

from PyQt6.QtCore import QAbstractNativeEventFilter

MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_ALT = 0x0001
WM_HOTKEY = 0x0312
WM_POWERBROADCAST = 0x0218
PBT_APMRESUMESUSPEND = 0x0007
PBT_APMRESUMEAUTOMATIC = 0x0012


class NativeHotkey(QAbstractNativeEventFilter):
    """Register a Windows global hotkey and deliver presses to a callback.

    The callback runs on the Qt main thread (from the native event filter),
    so there are none of the cross-thread issues seen with the keyboard pkg.

    An optional ``on_resume`` callback is fired when the system wakes up
    from sleep/hibernate, so the app can re-initialise the audio subsystem
    (Windows audio devices are often disrupted by sleep and the old PyAudio
    stream goes stale). QAbstractNativeEventFilter is not a QObject, so the
    resume notification is delivered via a plain callback rather than a Qt
    signal.
    """

    def __init__(self, callback, on_resume=None):
        super().__init__()
        self._callback = callback
        self._on_resume = on_resume
        self._registered = False
        self._id = 1

    def register(self, mods, vk):
        """Register the hotkey. Returns True on success."""
        if self._registered:
            self.unregister()
        # RegisterHotKey(None, id, mods, vk) posts WM_HOTKEY to the calling
        # thread's message queue (the Qt main thread here).
        result = ctypes.windll.user32.RegisterHotKey(None, self._id, mods, vk)
        self._registered = bool(result)
        return self._registered

    def unregister(self):
        """Unregister the hotkey if registered."""
        if self._registered:
            ctypes.windll.user32.UnregisterHotKey(None, self._id)
            self._registered = False

    def stop(self):
        """Alias for unregister(), used as an aboutToQuit cleanup hook."""
        self.unregister()

    def nativeEventFilter(self, eventType, message):
        if not self._registered:
            return False, 0
        try:
            msg = ctypes.wintypes.MSG.from_address(int(message))
        except Exception:
            return False, 0
        if msg.message == WM_HOTKEY and msg.wParam == self._id:
            try:
                self._callback()
            except Exception:
                pass
            return True, 0
        if msg.message == WM_POWERBROADCAST:
            wparam = msg.wParam & 0xFFFF
            if wparam == PBT_APMRESUMEAUTOMATIC or wparam == PBT_APMRESUMESUSPEND:
                try:
                    if self._on_resume is not None:
                        self._on_resume()
                except Exception:
                    pass
            return False, 0
        return False, 0
