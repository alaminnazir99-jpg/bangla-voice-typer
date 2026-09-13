"""Settings dialog for Bangla VoiceTyper."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QComboBox,
    QSpinBox,
    QCheckBox,
    QPushButton,
    QLabel,
    QGroupBox,
    QLineEdit,
    QColorDialog,
    QDialogButtonBox,
)


class SettingsDialog(QDialog):
    """Settings dialog for configuring the application."""

    settings_changed = pyqtSignal(dict)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("সেটিংস - Bangla VoiceTyper")
        self.setMinimumWidth(480)
        self._build_ui()
        self._load_current_settings()

    def _build_ui(self) -> None:
        """Build the settings UI."""
        layout = QVBoxLayout(self)

        # ============ Speech Engine ============
        engine_group = QGroupBox("স্পিচ ইঞ্জিন")
        engine_form = QFormLayout(engine_group)

        self.engine_combo = QComboBox()
        self.engine_combo.addItem("OpenAI Whisper (অফলাইন)", "whisper")
        self.engine_combo.addItem("Google Speech (অনলাইন)", "google")
        self.engine_combo.addItem("Vosk (অফলাইন)", "vosk")
        engine_form.addRow("ইঞ্জিন:", self.engine_combo)

        self.model_combo = QComboBox()
        self.model_combo.addItem("tiny (দ্রুত, কম ভুল)", "tiny")
        self.model_combo.addItem("base (মাঝারি)", "base")
        self.model_combo.addItem("small (ভালো - Recommended)", "small")
        self.model_combo.addItem("medium (সেরা, ধীর)", "medium")
        engine_form.addRow("Whisper মডেল:", self.model_combo)

        self.language_combo = QComboBox()
        self.language_combo.addItem("বাংলা (বাংলাদেশ)", "bn-BD")
        self.language_combo.addItem("বাংলা (ভারত)", "bn-IN")
        engine_form.addRow("ভাষা:", self.language_combo)

        layout.addWidget(engine_group)

        # Hook engine combo to toggle Whisper model visibility
        self.engine_combo.currentIndexChanged.connect(self._on_engine_changed)

        # ============ Typing ============
        typing_group = QGroupBox("টাইপিং")
        typing_form = QFormLayout(typing_group)

        self.speed_combo = QComboBox()
        self.speed_combo.addItem("দ্রুত", "fast")
        self.speed_combo.addItem("স্বাভাবিক", "normal")
        self.speed_combo.addItem("ধীর", "slow")
        typing_form.addRow("টাইপিং গতি:", self.speed_combo)

        self.auto_punct = QCheckBox("সঠিক বাংলা বিরাম চিহ্ন যোগ করুন")
        self.auto_punct.setChecked(True)
        typing_form.addRow("বিরাম চিহ্ন:", self.auto_punct)

        self.fix_spacing = QCheckBox("স্পেসিং ঠিক করুন")
        self.fix_spacing.setChecked(True)
        typing_form.addRow("স্পেসিং:", self.fix_spacing)

        self.clipboard_mode = QCheckBox("ক্লিপবোর্ড পদ্ধতি ব্যবহার করুন (দ্রুত)")
        self.clipboard_mode.toolTip = (
            "বড় টেক্সটের জন্য কপি-পেস্ট পদ্ধতি ব্যবহার করবে\n"
            "যা বেশি নির্ভরযোগ্য ও দ্রুত"
        )
        typing_form.addRow("দ্রুত মোড:", self.clipboard_mode)

        layout.addWidget(typing_group)

        # ============ Hotkeys ============
        hotkey_group = QGroupBox("হটকি")
        hotkey_form = QFormLayout(hotkey_group)

        self.toggle_hotkey = QLineEdit()
        self.toggle_hotkey.setPlaceholderText("ctrl+shift+b")
        hotkey_form.addRow("চালু/বন্ধ:", self.toggle_hotkey)

        self.push_hotkey = QLineEdit()
        self.push_hotkey.setPlaceholderText("ctrl+b")
        hotkey_form.addRow("পুশ-টু-টক:", self.push_hotkey)

        layout.addWidget(hotkey_group)

        # ============ Behavior ============
        behavior_group = QGroupBox("আচরণ")
        behavior_form = QFormLayout(behavior_group)

        self.start_minimized = QCheckBox("ট্রেতে মিনিমাইজ করে শুরু করুন")
        self.start_minimized.setChecked(True)
        behavior_form.addRow("", self.start_minimized)

        self.close_to_tray = QCheckBox("বন্ধ বাটনে ট্রেতে যাবে")
        self.close_to_tray.setChecked(True)
        behavior_form.addRow("", self.close_to_tray)

        self.auto_start = QCheckBox("Windows চালু হলে অ্যাপ স্বয়ংক্রিয়ভাবে শুরু হবে")
        behavior_form.addRow("", self.auto_start)

        layout.addWidget(behavior_group)

        # ============ Accent Color ============
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("অ্যাকসেন্ট রঙ:"))
        self.color_display = QLabel()
        self.color_display.setFixedSize(30, 25)
        self.color_display.setStyleSheet(
            f"background-color: {self._get_accent_color()}; border: 1px solid #555;"
        )
        self.color_btn = QPushButton("বদলান...")
        self.color_btn.clicked.connect(self._choose_color)
        color_layout.addWidget(self.color_display)
        color_layout.addWidget(self.color_btn)
        color_layout.addStretch()
        layout.addLayout(color_layout)

        # ============ Buttons ============
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _get_accent_color(self) -> str:
        return self.settings.get("appearance", "accent_color", "#00bcd4")

    def _load_current_settings(self) -> None:
        """Load current settings into the form."""
        engine = self.settings.get("speech", "engine", "whisper")
        idx = self.engine_combo.findData(engine)
        if idx >= 0:
            self.engine_combo.setCurrentIndex(idx)
        self._on_engine_changed()

        model = self.settings.get("speech", "whisper_model", "small")
        idx = self.model_combo.findData(model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)

        speed = self.settings.get("typing", "speed", "fast")
        idx = self.speed_combo.findData(speed)
        if idx >= 0:
            self.speed_combo.setCurrentIndex(idx)

        self.auto_punct.setChecked(
            self.settings.get("typing", "auto_punctuation", True)
        )
        self.fix_spacing.setChecked(
            self.settings.get("typing", "fix_spacing", True)
        )
        self.clipboard_mode.setChecked(
            self.settings.get("typing", "clipboard_mode", False)
        )

        self.toggle_hotkey.setText(
            self.settings.get("hotkey", "toggle", "ctrl+shift+b")
        )
        self.push_hotkey.setText(
            self.settings.get("hotkey", "push_to_talk", "ctrl+b")
        )

        self.start_minimized.setChecked(
            self.settings.get("behavior", "start_minimized", True)
        )
        self.close_to_tray.setChecked(
            self.settings.get("behavior", "close_to_tray", True)
        )
        self.auto_start.setChecked(
            self.settings.get("behavior", "auto_start", False)
        )

        self.color_display.setStyleSheet(
            f"background-color: {self._get_accent_color()}; border: 1px solid #555;"
        )

    def _on_engine_changed(self) -> None:
        """Show/hide Whisper model options based on engine selection."""
        engine = self.engine_combo.currentData()
        is_whisper = engine == "whisper"
        self.model_combo.setVisible(is_whisper)
        # The form label needs to be hidden too; we keep it but disabled
        self.model_combo.setEnabled(is_whisper)

    def _choose_color(self) -> None:
        color = QColorDialog.getColor()
        if color.isValid():
            c = color.name()
            self.color_display.setStyleSheet(
                f"background-color: {c}; border: 1px solid #555;"
            )

    def _on_save(self) -> None:
        """Save settings and emit signal."""
        new_settings = {}

        # Speech
        new_settings["speech"] = {
            "engine": self.engine_combo.currentData(),
            "whisper_model": self.model_combo.currentData(),
        }

        # Typing
        new_settings["typing"] = {
            "speed": self.speed_combo.currentData(),
            "auto_punctuation": self.auto_punct.isChecked(),
            "fix_spacing": self.fix_spacing.isChecked(),
            "clipboard_mode": self.clipboard_mode.isChecked(),
        }

        # Hotkeys
        new_settings["hotkey"] = {
            "toggle": self.toggle_hotkey.text().strip() or "ctrl+shift+b",
            "push_to_talk": self.push_hotkey.text().strip() or "ctrl+b",
        }

        # Behavior
        new_settings["behavior"] = {
            "start_minimized": self.start_minimized.isChecked(),
            "close_to_tray": self.close_to_tray.isChecked(),
            "auto_start": self.auto_start.isChecked(),
        }

        # Color
        color = self.color_display.styleSheet().split(":")[1].split(";")[0].strip()
        new_settings["appearance"] = {
            "accent_color": color if color else "#00bcd4",
        }

        self.settings_changed.emit(new_settings)
        self.accept()
