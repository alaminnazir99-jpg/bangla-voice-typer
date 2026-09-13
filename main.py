"""Bangla VoiceTyper - Main entry point.

A professional system-wide Bengali voice typing application
for Windows.

Usage:
    python main.py

Features:
- Voice typing in Bengali Unicode in any application
- Multiple speech engines (Whisper offline, Google online, Vosk offline)
- Smart punctuation (কমা, দাঁড়ি, জিজ্ঞাসাচিহ্ন, যুক্তবর্ণ)
- System-wide keyboard simulation
- Global hotkeys
- System tray
- Professional GUI
"""

import os
import sys
import logging
import threading

# Ensure the project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Ensure the log/config directory exists BEFORE configuring logging.
# On a fresh computer %APPDATA%\\BanglaVoiceTyper does not exist yet; if
# we create the FileHandler before the folder, the app crashes instantly
# on import - the most common "unhandled exception" on other PCs.
APPDATA_DIR = os.path.join(os.environ.get("APPDATA", "."), "BanglaVoiceTyper")
os.makedirs(APPDATA_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(APPDATA_DIR, "app.log"),
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger(__name__)


def _write_crash_report(text: str) -> str:
    """Write a crash report to the real Desktop so it is easy to find/send.

    Uses the Windows known-folder API so it works even when the Desktop is
    redirected to OneDrive (common on Windows 10/11). Returns the path
    written, or '' if it could not be written.
    """
    try:
        desktop = _desktop_folder()
        path = os.path.join(desktop, "BanglaVoiceTyper_crash.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("Bangla VoiceTyper - crash report\n")
            f.write("=" * 48 + "\n")
            f.write(text)
        return path
    except Exception:
        return ""


def _desktop_folder() -> str:
    """Return the user's real Desktop path via SHGetKnownFolderPath."""
    try:
        import ctypes
        from ctypes import wintypes

        FOLDERID_Desktop = ctypes.c_char_p(
            b"{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}"
        )
        p_path = ctypes.c_void_p()
        if (
            ctypes.windll.shell32.SHGetKnownFolderPath(
                FOLDERID_Desktop, 0, None, ctypes.byref(p_path)
            )
            == 0
            and p_path.value
        ):
            path = ctypes.wstring_at(p_path.value)
            ctypes.windll.ole32.CoTaskMemFree(p_path.value)
            if path:
                return path
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Desktop")


def _show_crash_dialog(text: str) -> None:
    """Show a readable message box for an uncaught exception."""
    try:
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication, QMessageBox

        app = QApplication.instance()
        if app is None:
            return
        lines = text.strip().splitlines()
        brief = "\n".join(lines[-6:]) if lines else text
        QTimer.singleShot(
            0,
            lambda: QMessageBox.critical(
                None,
                "Bangla VoiceTyper - ত্রুটি",
                "প্রোগ্রামে একটি সমস্যা হয়েছে।\n\n"
                f"{brief[:1500]}\n\n"
                "পূর্ণ বিবরণ সেভ হয়েছে: "
                "ডেস্কটপের BanglaVoiceTyper_crash.txt ফাইলে।",
            ),
        )
    except Exception:
        pass


def _install_exception_guard():
    """Log any uncaught exception and surface it visibly.

    In a --windowed build there is no console, so an unhandled exception in a
    slot would otherwise just terminate the app without a trace. We log it,
    write a desktop crash report and show a readable dialog so the real cause
    is never lost ('unhandled exception' dialogs on other PCs become a file
    the user can find and send).
    """
    def _report(exc_type, exc, tb):
        import traceback
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        logger.error("UNCAUGHT EXCEPTION:\n%s", text)
        _write_crash_report(text)
        _show_crash_dialog(text)

    sys.excepthook = _report
    if hasattr(threading, "excepthook"):
        def _thread_hook(args):
            import traceback
            text = "".join(traceback.format_exception(*args.exc_info))
            logger.error("UNCAUGHT THREAD EXCEPTION:\n%s", text)
        threading.excepthook = _thread_hook


_install_exception_guard()


def setup_appdata():
    """Ensure the AppData directory exists."""
    appdata = os.environ.get("APPDATA", str(os.path.expanduser("~")))
    path = os.path.join(appdata, "BanglaVoiceTyper")
    os.makedirs(path, exist_ok=True)
    return path


class GlobalHotkeyManager:
    """Manages global hotkeys using the keyboard library.

    Runs in a background thread to listen for hotkey presses.
    """

    def __init__(self, on_toggle: callable, on_push_to_talk: callable):
        self.on_toggle = on_toggle
        self.on_push_to_talk = on_push_to_talk
        self._running = False
        self._thread = None
        self._hotkeys = {}

    def start(self, toggle_key: str = "ctrl+shift+b", push_key: str = "ctrl+b") -> None:
        """Start listening for hotkeys."""
        if self._running:
            return
        self._running = True
        self._hotkeys[toggle_key] = self.on_toggle
        if push_key and self.on_push_to_talk:
            self._hotkeys[push_key] = self.on_push_to_talk
        self._thread = threading.Thread(target=self._listener_loop, daemon=True)
        self._thread.start()

    def _dispatch_to_main_thread(self, callback) -> None:
        """Safely run a callback on the PyQt main thread.

        The 'keyboard' library invokes hotkey callbacks from a worker
        thread. Touching PyQt widgets from that thread can crash / quit the
        app (which is why the tray icon was disappearing). We marshal the
        call back onto the GUI thread using QTimer.singleShot, which is
        thread-safe and schedules on the main thread.
        """
        try:
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtCore import QTimer

            app = QApplication.instance()
            if app is None:
                callback()
                return

            def _run():
                try:
                    callback()
                except Exception:
                    logger.exception("Hotkey callback error")

            QTimer.singleShot(0, _run)
        except Exception:
            try:
                callback()
            except Exception:
                logger.exception("Hotkey callback error")

    def _listener_loop(self) -> None:
        """Background loop using keyboard library."""
        try:
            import keyboard
            for key, callback in self._hotkeys.items():
                def make_handler(cb):
                    def handler():
                        self._dispatch_to_main_thread(cb)
                    return handler
                keyboard.add_hotkey(key, make_handler(callback))
            keyboard.wait()  # Blocks forever
        except Exception as exc:
            logger.error("Hotkey listener error: %s", exc)

    def stop(self) -> None:
        """Stop listening for hotkeys."""
        self._running = False
        try:
            import keyboard
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass


def _single_instance_lock():
    """Acquire a Windows named mutex so only one instance runs.

    Uses ctypes/CreateMutexW which works reliably with PyInstaller onefile
    builds. Returns True if THIS instance owns the mutex (should keep
    running), False if another instance already holds it, and True if the
    mutex could not be created at all (better to keep going than to block
    the user because of a rare system error).
    """
    import ctypes
    from ctypes import wintypes

    ERROR_ALREADY_EXISTS = 183
    name = "BanglaVoiceTyper_SingleInstanceMutex"

    handle = ctypes.windll.kernel32.CreateMutexW(None, False, name)
    if not handle:
        # Rare system error - don't block the user, let the app continue.
        return True
    if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        return False
    return True


def main():
    """Application entry point."""
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QTimer

    from config.settings import SettingsManager
    from gui.splash import SplashScreen

    # Ensure PyQt6 is available
    try:
        app = QApplication(sys.argv)
    except ImportError:
        logger.error(
            "PyQt6 is not installed. Install with: pip install PyQt6"
        )
        sys.exit(1)

    app.setApplicationName("Bangla VoiceTyper")
    app.setOrganizationName("BanglaVoiceTyper")

    # Load settings
    settings_manager = SettingsManager()
    settings = settings_manager.load()

    def _boot():
        """Run after the splash has been visible.

        Single-instance guard is checked here so that double-clicking the
        exe while the app already runs still shows the splash first, then
        quietly exits (the running instance keeps working).
        """
        # Single-instance guard (Windows named mutex).
        if not _single_instance_lock():
            logger.info("Another instance is already running - exiting.")
            sys.exit(0)

        # --- License gate: the app won't run without a valid key. ---
        from core.license import validate
        stored_key = settings.get("license", "key", "") or ""
        if not validate(stored_key):
            from gui.activation_dialog import request_activation
            key = request_activation()
            if not key:
                logger.warning("License activation cancelled - exiting.")
                sys.exit(0)
            settings.set("license", "key", key)
            settings_manager.save(settings)
            logger.info("License activated.")

        from gui.main_window import MainWindow

        # Create the main window
        window = MainWindow(settings_manager, settings)

        # Setup the system-wide toggle hotkey (Ctrl+Shift+B) using the
        # Windows-native RegisterHotKey + native event filter. This is
        # reliable in a background app and needs no admin rights.
        from native_hotkey import NativeHotkey, MOD_CONTROL, MOD_SHIFT

        hotkey_mgr = NativeHotkey(window.toggle_global_voice)
        toggle_key = settings.get("hotkey", "toggle", "ctrl+shift+b")
        KEY_MAP = {
            "ctrl+shift+b": 0x42,
            "ctrl+shift+x": 0x58,
            "ctrl+shift+y": 0x59,
            "ctrl+shift+z": 0x5A,
        }
        vk = KEY_MAP.get(toggle_key.lower(), 0x42)
        ok = hotkey_mgr.register(MOD_CONTROL | MOD_SHIFT, vk)
        if ok:
            app.installNativeEventFilter(hotkey_mgr)
            logger.info("Ctrl+Shift+B global hotkey registered (native).")
        else:
            logger.warning("Failed to register global hotkey.")
            # Tell the user visibly - otherwise they'd have an app running
            # yet the hotkey silently does nothing.
            try:
                window._refresh_tray_status(
                    "হটকি (Ctrl+Shift+B) রেজিস্টার করা যায়নি। "
                    "আরেকটি প্রোগ্রাম একই হটকি ব্যবহার করতে পারে।"
                )
                window.status_label.setText(
                    "হটকি ব্যর্থ — Ctrl+Shift+B অন্য প্রোগ্রাম ব্যবহার করছে।"
                )
            except Exception:
                pass
        window.hotkey_manager = hotkey_mgr

        # Recover from system sleep/resume: Windows disrupts the audio
        # devices on resume, which made the app silently stop working.
        # Wait a moment for the audio service to settle, then reset the
        # worker's audio subsystem and re-register the hotkey for safety.
        def _on_power_resume():
            # Worker may not exist yet (before first use) - guard it.
            if window.worker is not None:
                QTimer.singleShot(2000, window.worker.power_resumed)
            try:
                if not hotkey_mgr.register(MOD_CONTROL | MOD_SHIFT, vk):
                    logger.warning("Hotkey re-register failed after resume.")
            except Exception:
                pass

        hotkey_mgr._on_resume = _on_power_resume

        # Minimize to tray if configured
        start_minimized = settings.get("behavior", "start_minimized", True)
        if start_minimized and hasattr(window, "tray"):
            QTimer.singleShot(500, window.hide)
        else:
            window.show()

        # Thin floating bar (the small single-line window the user sees).
        from gui.thin_bar import ThinBar

        thin_bar = ThinBar()
        thin_bar.toggle_requested.connect(window.toggle_global_voice)
        thin_bar.settings_requested.connect(window.open_settings)
        window.recording_state_changed.connect(thin_bar.set_recording_state)
        thin_bar.show()
        window.hide()

        logger.info("Bangla VoiceTyper started")

        # Ensure cleanup on exit
        app.aboutToQuit.connect(hotkey_mgr.stop)
        app.aboutToQuit.connect(
            lambda: window.worker.stop() if window.worker else None
        )

        splash.hide()
        splash.deleteLater()

    # Splash screen first, then boot the app after a short moment.
    splash = SplashScreen(settings)
    splash.show_for(5000, _boot)

    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        import traceback
        text = "".join(traceback.format_exc())
        try:
            logger.error("FATAL STARTUP ERROR:\n%s", text)
        except Exception:
            pass
        _write_crash_report(text)
        _show_crash_dialog(text)
        sys.exit(1)
