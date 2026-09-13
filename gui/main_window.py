"""Main window for Bangla VoiceTyper.

Provides the primary user interface with:
- Audio visualizer
- Live transcription display
- Recognized text history
- Recording controls
- Status display
"""

import logging
import time

logger = logging.getLogger(__name__)

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QFont, QIcon, QColor
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTextEdit,
    QListWidget,
    QListWidgetItem,
    QComboBox,
    QFrame,
    QTabWidget,
    QSplitter,
    QMessageBox,
    QApplication,
    QSystemTrayIcon,
    QMenu,
)

from .audio_visualizer import AudioVisualizer
from .settings_dialog import SettingsDialog
from core import AudioRecorder, SpeechEngine, BanglaProcessor, KeyboardTyper


class AudioWorker(QThread):
    """Persistent worker thread for recording and recognizing speech.

    A single instance is created once and lives for the whole app session.
    start/stop simply toggle a flag that the run-loop honours, so the
    underlying QThread is NEVER destroyed or recreated while the app runs.
    This completely avoids the native "QThread: Destroyed while thread is
    still running" crash that kills the whole process on stop.
    """

    status_changed = pyqtSignal(str)
    text_received = pyqtSignal(str)
    level_changed = pyqtSignal(float)
    started = pyqtSignal()
    finished_recognition = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.recorder = None
        self.speech_engine = None
        self.bangla_processor = None
        self._stop = False       # app is quitting
        self._active = False     # user wants dictation on
        self._recognizing = False
        self._reinit_audio = False  # set after system sleep/resume

    def set_active(self, active: bool) -> None:
        """Enable/disable continuous dictation without touching the thread."""
        self._active = bool(active)
        if not active and self.recorder is not None:
            # Immediately stop the ongoing recording so the run-loop can
            # exit _monitor_levels fast and respond to the next toggle
            # quickly instead of waiting for silence/30s max duration.
            try:
                self.recorder.stop_recording()
            except Exception:
                pass

    def power_resumed(self) -> None:
        """Re-initialise the audio subsystem after the PC wakes from sleep.

        Windows often leaves the old PyAudio stream in a stale/broken state
        after resume. We hard-reset the recorder and force a fresh PyAudio
        instance on the next active cycle, after letting the audio service
        settle for a moment.
        """
        self._reinit_audio = True
        if self.recorder is not None:
            try:
                self.recorder.reset()
            except Exception:
                pass

    def run(self) -> None:
        """Main worker loop - runs for the entire app lifetime."""
        self._stop = False
        self.started.emit()
        try:
            while not self._stop:
                # Wait until the user wants recording on.
                if not self._active:
                    QThread.msleep(50)
                    continue

                if not self._do_cycle():
                    # Something went wrong; back off briefly before retrying.
                    QThread.msleep(500)
        except Exception:
            import traceback
            traceback.print_exc()

    def _do_cycle(self) -> bool:
        """Run one record->recognize->emit cycle. Returns False on error."""
        try:
            if self._reinit_audio:
                # After wake the Windows audio service needs a moment to
                # re-enumerate devices; then create a brand-new recorder.
                logger.info("Power resume: re-initialising audio.")
                self.msleep(2500)
                self.recorder = None
                self._reinit_audio = False

            if self.recorder is None:
                self.recorder = AudioRecorder(
                    sample_rate=self.settings.get("speech", "sample_rate", 16000),
                    channels=1,
                    silence_threshold=self.settings.get("speech", "silence_threshold", 500),
                    max_duration=self.settings.get("speech", "max_duration", 30),
                )
            if self.speech_engine is None:
                self.speech_engine = SpeechEngine(
                    self.settings,
                    on_status=lambda s: self.status_changed.emit(s),
                )
            if self.bangla_processor is None:
                self.bangla_processor = BanglaProcessor(
                    auto_punctuation=self.settings.get(
                        "typing", "auto_punctuation", True
                    ),
                    fix_spacing=self.settings.get("typing", "fix_spacing", True),
                )

            self.status_changed.emit("শুনছি... (বলুন)")
            self.recorder.start_recording()
            self._monitor_levels()

            audio_data = self.recorder.stop_recording()
            if audio_data and self._active and not self._stop:
                self._recognizing = True
                self.status_changed.emit("প্রসেস হচ্ছে...")
                text = self.speech_engine.recognize(
                    audio_data=audio_data,
                    engine=self.settings.get("speech", "engine", "whisper"),
                )
                self._recognizing = False
                if not self._active or self._stop:
                    return True
                if text:
                    polished = self.bangla_processor.process(text)
                    self.text_received.emit(polished)
                else:
                    self.status_changed.emit("কথা শনাক্ত করা যায়নি। আবার চেষ্টা করুন।")
            return True
        except Exception as exc:
            try:
                self.error.emit(str(exc))
                self.status_changed.emit(f"ত্রুটি: {exc}")
            except Exception:
                pass
            return False

    def _monitor_levels(self) -> None:
        """Monitor recording progress and emit audio levels."""
        import numpy as np
        idle_ticks = 0
        while self.recorder._recording:
            data = b"".join(self.recorder._frames) if self.recorder._frames else b""
            if not data:
                idle_ticks += 1
                if idle_ticks > 50:
                    QThread.msleep(5)
                    continue
            else:
                idle_ticks = 0
            try:
                audio = np.frombuffer(data[-4096:], dtype=np.int16)
                if audio.size == 0:
                    continue
                level = float(np.abs(audio).mean() / 32768.0)
                self.level_changed.emit(min(1.0, level))
            except Exception:
                pass
            QThread.msleep(50)

    def stop(self) -> None:
        """Tell the worker to exit for good (app shutdown only)."""
        self._stop = True
        self._active = False
        if self.recorder:
            try:
                self.recorder.stop_recording()
            except Exception:
                pass


class MainWindow(QMainWindow):
    """Main window of the Bangla VoiceTyper application."""

    # Emitted whenever recording state changes (True=recording, False=idle);
    # the thin floating bar listens to this to update its visuals.
    recording_state_changed = pyqtSignal(bool)

    def __init__(self, settings_manager, settings):
        super().__init__()
        self.settings_manager = settings_manager
        self.settings = settings
        self.worker = None
        self.is_recording = False
        self.global_voice_mode = False
        self._last_toggle = 0.0
        # Keeps references to old QThread objects alive until their thread
        # has fully finished. Releasing a still-running QThread (via GC) is a
        # native crash ("QThread: Destroyed while thread is still running")
        # that kills the whole app, so we must keep them referenced.
        self._stale_workers = []
        self.typer = KeyboardTyper(
            typing_speed=self.settings.get("typing", "speed", "fast")
        )
        self.history_items = []
        self._build_ui()
        self._build_tray()
        self._load_styles()

    # ------------------------------------------------------------------
    # UI Build
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Build the main window UI."""
        self.setWindowTitle("Bangla VoiceTyper")
        self.setWindowIcon(self._create_icon())
        self.setMinimumSize(280, 320)
        self.resize(300, 340)

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        # ===== Top bar: title + status ======
        top_layout = QHBoxLayout()
        title = QLabel("🎙️ Bangla VoiceTyper")
        title.setObjectName("titleLabel")
        title.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: {accent};".format(
                accent=self.settings.get("appearance", "accent_color", "#00bcd4")
            )
        )
        top_layout.addWidget(title)
        top_layout.addStretch()

        self.status_label = QLabel("প্রস্তুত")
        self.status_label.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        top_layout.addWidget(self.status_label)
        root_layout.addLayout(top_layout)

        # ===== Audio visualizer =====
        self.visualizer = AudioVisualizer(
            accent_color=self.settings.get("appearance", "accent_color", "#00bcd4")
        )
        root_layout.addWidget(self.visualizer)

        # ===== Control buttons =====
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.record_btn = QPushButton("🎤 রেকর্ড শুরু")
        self.record_btn.setObjectName("recordBtn")
        self.record_btn.clicked.connect(self.toggle_recording)
        self.record_btn.setMinimumHeight(44)
        btn_layout.addWidget(self.record_btn, 3)

        self.clear_btn = QPushButton("🗑️ মুছুন")
        self.clear_btn.clicked.connect(self.clear_text)
        self.clear_btn.setMinimumHeight(44)
        btn_layout.addWidget(self.clear_btn, 1)

        self.settings_btn = QPushButton("⚙️ সেটিংস")
        self.settings_btn.clicked.connect(self.open_settings)
        self.settings_btn.setMinimumHeight(44)
        btn_layout.addWidget(self.settings_btn, 1)

        root_layout.addLayout(btn_layout)

        # ===== Tabs =====
        self.tabs = QTabWidget()
        root_layout.addWidget(self.tabs, 1)

        # --- Live Text tab ---
        live_tab = QWidget()
        live_layout = QVBoxLayout(live_tab)
        self.live_text = QTextEdit()
        self.live_text.setPlaceholderText("শনাক্তকৃত টেক্সট এখানে দেখা যাবে...")
        self.live_text.setFont(QFont("Nirmala UI", 14))
        live_layout.addWidget(self.live_text)

        live_actions = QHBoxLayout()
        self.type_btn = QPushButton("🖊️ এপ্লিকেশনে টাইপ করুন")
        self.type_btn.clicked.connect(self.type_into_app)
        self.type_btn.setMinimumHeight(40)
        live_actions.addWidget(self.type_btn, 2)

        self.copy_btn = QPushButton("📋 কপি")
        self.copy_btn.clicked.connect(self.copy_live)
        live_actions.addWidget(self.copy_btn, 1)

        live_layout.addLayout(live_actions)
        self.tabs.addTab(live_tab, "লাইভ টেক্সট")

        # --- History tab ---
        history_tab = QWidget()
        hist_layout = QVBoxLayout(history_tab)
        self.history_list = QListWidget()
        self.history_list.setFont(QFont("Nirmala UI", 12))
        self.history_list.itemDoubleClicked.connect(self._history_clicked)
        hist_layout.addWidget(self.history_list)

        hist_actions = QHBoxLayout()
        self.copy_hist_btn = QPushButton("📋 কপি")
        self.copy_hist_btn.clicked.connect(self.copy_history)
        hist_actions.addWidget(self.copy_hist_btn)

        self.clear_hist_btn = QPushButton("🗑️ ইতিহাস মুছুন")
        self.clear_hist_btn.clicked.connect(self.clear_history)
        hist_actions.addWidget(self.clear_hist_btn)

        hist_layout.addLayout(hist_actions)
        self.tabs.addTab(history_tab, "ইতিহাস")

        # ===== Footer hint =====
        hint = QLabel(
            f"হটকি: {self.settings.get('hotkey', 'toggle', 'Ctrl+Shift+B')} "
            "— স্টার্ট/স্টপ | Push-to-Talk: "
            f"{self.settings.get('hotkey', 'push_to_talk', 'Ctrl+B')}"
        )
        hint.setObjectName("hintLabel")
        hint.setStyleSheet("color: #888888; font-size: 11px;")
        root_layout.addWidget(hint)

    def _build_tray(self) -> None:
        """Build the system tray icon and menu."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self.tray = QSystemTrayIcon(self._create_icon(), self)
        self.tray.setToolTip("Bangla VoiceTyper")

        tray_menu = QMenu()
        toggle_action = tray_menu.addAction("রেকর্ড স্টার্ট/স্টপ")
        toggle_action.triggered.connect(self.toggle_recording)
        tray_menu.addSeparator()
        show_action = tray_menu.addAction("প্রদর্শন করুন")
        show_action.triggered.connect(self.show_window)
        tray_menu.addSeparator()
        quit_action = tray_menu.addAction("প্রস্থান")
        quit_action.triggered.connect(self.quit_app)

        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _create_icon(self):
        """Create a simple microphone icon."""
        from PyQt6.QtGui import QPixmap, QPainter, QColor, QBrush
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        accent = QColor(self.settings.get("appearance", "accent_color", "#00bcd4"))
        painter.setBrush(QBrush(accent))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(8, 4, 48, 56, 10, 10)
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawRoundedRect(24, 12, 16, 30, 6, 6)
        painter.drawEllipse(24, 44, 16, 6)
        painter.end()
        return QIcon(pixmap)

    def _load_styles(self) -> None:
        """Load application-wide QSS styles."""
        accent = self.settings.get("appearance", "accent_color", "#00bcd4")
        dark_accent = QColor(accent).darker(150).name()
        self.setStyleSheet(
            f"""
            QMainWindow {{
                background-color: #1e1e1e;
                color: #e0e0e0;
            }}
            QWidget {{
                background-color: #1e1e1e;
                color: #e0e0e0;
                font-family: "Segoe UI", "Nirmala UI";
                font-size: 13px;
            }}
            QPushButton {{
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                padding: 8px 14px;
                color: #e0e0e0;
            }}
            QPushButton:hover {{
                background-color: #3d3d3d;
                border-color: #4d4d4d;
            }}
            QPushButton#recordBtn {{
                background-color: {dark_accent};
                border: 1px solid {accent};
                color: #ffffff;
                font-weight: bold;
            }}
            QPushButton#recordBtn:hover {{
                background-color: {accent};
            }}
            QPushButton#recordBtn[recording="true"] {{
                background-color: #d32f2f;
                border-color: #c62828;
            }}
            QTextEdit {{
                background-color: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 10px;
                color: #e8e8e8;
                selection-background-color: {dark_accent};
            }}
            QListWidget {{
                background-color: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 6px;
            }}
            QListWidget::item {{
                padding: 10px;
                border-bottom: 1px solid #2a2a2a;
            }}
            QListWidget::item:selected {{
                background-color: {dark_accent};
                color: #ffffff;
            }}
            QTabWidget::pane {{
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                background-color: #1e1e1e;
            }}
            QTabBar::tab {{
                background-color: #252525;
                padding: 8px 18px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }}
            QTabBar::tab:selected {{
                background-color: {dark_accent};
                color: #ffffff;
            }}
            QGroupBox {{
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 8px;
                background-color: #222;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
                color: {accent};
                font-weight: bold;
            }}
            QComboBox {{
                background-color: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 6px 10px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QLineEdit {{
                background-color: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 6px;
            }}
            QSpinBox {{
                background-color: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 6px;
            }}
            QCheckBox {{
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
            }}
            QScrollBar:vertical {{
                background: #252525;
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: #444;
                border-radius: 5px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #555;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QStatusBar {{
                background-color: #1a1a1a;
                color: #aaaaaa;
            }}
            """
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def toggle_recording(self) -> None:
        """Toggle system-wide voice typing on/off.

        Both the Ctrl+Shift+B hotkey and the tray "রেকর্ড শুরু" button call
        this. When active, recognized text is typed directly into the app
        that currently has keyboard focus (Word, browser, etc.), and the
        main window stays hidden so it never steals focus. The app itself
        is never closed.

        Debounced (500 ms) so a single hotkey press that arrives more than
        once (native event duplicates) still only toggles once.
        """
        now = time.monotonic()
        if self._last_toggle and (now - self._last_toggle) < 0.5:
            return
        self._last_toggle = now
        try:
            if self.is_recording:
                self.stop_voice()
            else:
                self.start_voice()
        except Exception as exc:
            # Never let an error close the app or remove the tray icon.
            import traceback
            traceback.print_exc()
            self.status_label.setText(f"ত্রুটি: {exc}")
            self.is_recording = False
            if hasattr(self, "tray"):
                try:
                    self.tray.showMessage(
                        "Bangla VoiceTyper",
                        "একটি সমস্যা হয়েছে, অ্যাপ চলতে থাকবে।",
                        QSystemTrayIcon.MessageIcon.Warning,
                        2000,
                    )
                except Exception:
                    pass

    def _refresh_tray_status(
        self, message: str, icon: QSystemTrayIcon.MessageIcon = None
    ) -> None:
        """Show a non-blocking tray notification without resetting the icon."""
        if hasattr(self, "tray") and self.tray is not None:
            try:
                self.tray.showMessage(
                    "Bangla VoiceTyper",
                    message,
                    icon or QSystemTrayIcon.MessageIcon.Information,
                    2000,
                )
            except Exception:
                pass

    def toggle_global_voice(self) -> None:
        """Hotkey entry point - identical to toggle_recording."""
        self.toggle_recording()

    def start_voice(self) -> None:
        """Start system-wide voice typing.

        The window is hidden so keyboard focus stays on the target app,
        and every recognized phrase is typed straight into that app.
        """
        if self.is_recording:
            return

        self.is_recording = True
        self.status_label.setText("শুনছি... (বলুন)")
        self.visualizer.set_state("listening")
        self.recording_state_changed.emit(True)
        self._refresh_tray_status("🎙️ ভয়েস টাইপিং চালু — বাংলায় বলুন...")

        # Hide so focus stays in the app we are typing into.
        self.hide()

        # Create the worker once; never recreate/destroy it while running.
        if self.worker is None:
            self.worker = AudioWorker(self.settings, self)
            self.worker.status_changed.connect(self.on_status)
            self.worker.text_received.connect(self.on_text_received)
            self.worker.level_changed.connect(self.visualizer.set_level)
            self.worker.error.connect(self.on_worker_error)
            self.worker.finished.connect(self.worker.deleteLater)
            self.worker.start()

        # Flip the flag - the persistent thread starts dictating.
        self.worker.set_active(True)

    def stop_voice(self) -> None:
        """Stop system-wide voice typing.

        This is deliberately non-blocking and never closes the app or the
        tray icon. The persistent worker thread is kept alive - we simply
        turn its dictation flag off, so the QThread is never destroyed
        (which is what previously crashed the whole app on stop).
        """
        if not self.is_recording:
            return
        self.is_recording = False

        if self.worker is not None:
            self.worker.set_active(False)  # thread stays alive, just pauses

        self.visualizer.set_state("idle")
        self.status_label.setText("প্রস্তুত (Ctrl+Shift+B চাপুন)")
        self.recording_state_changed.emit(False)
        self._refresh_tray_status("⏹️ ভয়েস টাইপিং বন্ধ — অ্যাপ চলতে থাকবে")

        # Keep the window hidden so the app always runs in the background
        # (tray icon). The user can open it by double-clicking the tray
        # icon if they ever want to see the window. Do NOT self.show() here.
        self.hide()

    def start_recording(self) -> None:
        """Backward-compatible alias for start_voice."""
        self.start_voice()

    def stop_recording(self) -> None:
        """Backward-compatible alias for stop_voice."""
        self.stop_voice()

    @pyqtSlot(str)
    def on_status(self, msg: str) -> None:
        """Update the status label and tray status on worker state changes."""
        self.status_label.setText(msg)
        if "প্রসেস" in msg:
            self.visualizer.set_state("processing")
            self._refresh_tray_status("⚙️ প্রসেসিং হচ্ছে...")
        elif "শুনছি" in msg:
            self.visualizer.set_state("listening")
            self._refresh_tray_status("🎙️ রেকর্ডিং... বলুন")

    @pyqtSlot(str)
    def on_text_received(self, text: str) -> None:
        """Handle newly recognized Bengali text.

        The text is typed directly into the focused application (Word,
        browser, notebook, etc.). It is never echoed into this app only -
        it goes where the cursor is.
        """
        if not self.is_recording:
            return

        self.status_label.setText("✅ শনাক্ত হয়েছে — টাইপ হচ্ছে")
        self.visualizer.set_state("success")

        if text:
            self._add_to_history(text)
            # Type straight into the app that has focus.
            self._type_text_into_focus(text)

        # Return the visualizer to "listening" shortly after.
        QTimer.singleShot(800, lambda: self.visualizer.set_state("listening"))

    @pyqtSlot(str)
    def on_worker_error(self, msg: str) -> None:
        """Handle worker errors - show them visibly via tray + status."""
        self.status_label.setText(f"ত্রুটি: {msg}")
        self.visualizer.set_state("error")
        QTimer.singleShot(2000, lambda: self.visualizer.set_state("idle"))
        self._refresh_tray_status(
            f"ত্রুটি: {msg}",
            icon=QSystemTrayIcon.MessageIcon.Warning,
        )

    def clear_text(self) -> None:
        """Clear the live text editor."""
        self.live_text.clear()

    def type_into_app(self) -> None:
        """Type the live text into the focused application."""
        text = self.live_text.toPlainText()
        if not text:
            return
        self.hide()
        QTimer.singleShot(350, lambda: self._do_type(text))

    def _do_type(self, text: str) -> None:
        """Actually perform typing after window is hidden."""
        use_clipboard = self.settings.get("typing", "clipboard_mode", False)
        if use_clipboard and len(text) > 50:
            self.typer.type_paste(text)
        else:
            speed = self.settings.get("typing", "speed", "fast")
            self.typer.set_speed(speed)
            self.typer.type_text(text)
        self.show()

    def _type_text_into_focus(self, text: str) -> None:
        """Type recognized text into the currently focused application.

        Used by system-wide voice typing mode. The window stays hidden so
        keyboard focus remains on the target app (Word, browser, etc.).
        """
        if not text:
            return
        use_clipboard = self.settings.get("typing", "clipboard_mode", False)
        if use_clipboard and len(text) > 50:
            self.typer.type_paste(text)
        else:
            speed = self.settings.get("typing", "speed", "fast")
            self.typer.set_speed(speed)
            self.typer.type_text(text)

    def copy_live(self) -> None:
        """Copy live text to clipboard."""
        import pyperclip
        text = self.live_text.toPlainText()
        if text:
            pyperclip.copy(text)
            self.status_label.setText("📋 কপি করা হয়েছে")

    def _add_to_history(self, text: str) -> None:
        """Add text to history list."""
        self.history_items.append(text)
        item = QListWidgetItem(text)
        self.history_list.insertItem(0, item)
        if self.history_list.count() > 100:
            self.history_list.takeItem(self.history_list.count() - 1)
            self.history_items.pop(0)

    def _history_clicked(self, item: QListWidgetItem) -> None:
        """Handle double-click on history item."""
        self.live_text.setText(item.text())

    def copy_history(self) -> None:
        """Copy selected history item to clipboard."""
        import pyperclip
        selected = self.history_list.currentItem()
        if selected:
            pyperclip.copy(selected.text())
            self.status_label.setText("📋 কপি করা হয়েছে")

    def clear_history(self) -> None:
        """Clear the history list."""
        self.history_list.clear()
        self.history_items.clear()

    def open_settings(self) -> None:
        """Open the settings dialog."""
        dialog = SettingsDialog(self.settings, self)
        dialog.settings_changed.connect(self.on_settings_changed)
        dialog.exec()

    def on_settings_changed(self, new_settings: dict) -> None:
        """Apply settings changes."""
        for section, values in new_settings.items():
            for key, value in values.items():
                self.settings.set(section, key, value)
        self.settings_manager.save(self.settings)
        self.status_label.setText("✅ সেটিংস সেভ হয়েছে")
        self._reload_styles()
        # Update typer speed
        self.typer.set_speed(self.settings.get("typing", "speed", "fast"))

    def _reload_styles(self) -> None:
        """Reload styles with new accent color."""
        self._load_styles()
        accent = self.settings.get("appearance", "accent_color", "#00bcd4")
        self.visualizer.accent_color = accent

    # ------------------------------------------------------------------
    # Tray / Window management
    # ------------------------------------------------------------------
    def show_window(self) -> None:
        """Show and restore the main window."""
        self.show()
        self.setWindowState(Qt.WindowState.WindowActive)
        self.raise_()
        self.activateWindow()

    def _tray_activated(self, reason) -> None:
        """Handle tray icon double-click."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show_window()

    def closeEvent(self, event) -> None:
        """Handle window close - minimize to tray if configured."""
        if self.settings.get("behavior", "close_to_tray", True):
            event.ignore()
            self.hide()
            self.tray.showMessage(
                "Bangla VoiceTyper",
                "অ্যাপ ট্রেতে চলছে। সিস্টেম ট্রে আইকন থেকে পুনরায় খুলুন।",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )
        else:
            self.quit_app()
            event.accept()

    def quit_app(self) -> None:
        """Fully quit the application."""
        if self.worker is not None:
            self.worker.stop()
            self.worker.wait(2000)
        QApplication.quit()
