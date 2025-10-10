# File: dcm_ui/pacing_modes.py
# - Part 1 pacing modes selection (AOO, VOO, AAI, VVI)
# - Minimal UI: radio buttons + Save + Back
# - Persists to working-directory JSON: dcm_mode.json

import json
import os
from dataclasses import dataclass, asdict

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QRadioButton,
    QLabel, QPushButton, QMessageBox
)

MODE_FILE = "dcm_mode.json"


@dataclass
class ModeSelection:
    mode: str = "VVI"  # default; valid: AOO, VOO, AAI, VVI


class PacingModesPage(QWidget):
    """Simple page to select a pacing mode (AOO, VOO, AAI, VVI) and persist locally."""
    goHome = pyqtSignal()  # used by MainWindow to navigate back

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PacingModesPage")

        # Load previously saved selection
        self.selection = self._load()

        # --- Layout root ---
        root = QVBoxLayout(self)

        title = QLabel("Pacing Modes")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        root.addWidget(title)

        # --- Modes group ---
        box = QGroupBox("Select Mode")
        box_layout = QVBoxLayout()
        box.setLayout(box_layout)

        self.rb_aoo = QRadioButton("AOO")
        self.rb_voo = QRadioButton("VOO")
        self.rb_aai = QRadioButton("AAI")
        self.rb_vvi = QRadioButton("VVI")

        box_layout.addWidget(self.rb_aoo)
        box_layout.addWidget(self.rb_voo)
        box_layout.addWidget(self.rb_aai)
        box_layout.addWidget(self.rb_vvi)

        root.addWidget(box)

        # Description label
        self.lbl_desc = QLabel("")
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setStyleSheet("color: #444;")
        root.addWidget(self.lbl_desc)

        # Buttons row
        row = QHBoxLayout()
        self.btn_back = QPushButton("← Back to Dashboard")
        self.btn_save = QPushButton("Save Mode")
        row.addWidget(self.btn_back)
        row.addStretch(1)
        row.addWidget(self.btn_save)
        root.addLayout(row)

        root.addStretch(1)

        # Initialize selection + description
        self._init_selection(self.selection.mode)
        self._update_description()

        # Signals
        for rb in (self.rb_aoo, self.rb_voo, self.rb_aai, self.rb_vvi):
            rb.toggled.connect(self._update_description)

        self.btn_save.clicked.connect(self._save_mode)
        self.btn_back.clicked.connect(lambda: self.goHome.emit())

    # --- helpers ---
    def _init_selection(self, mode: str):
        mode = (mode or "").upper()
        mapping = {
            "AOO": self.rb_aoo,
            "VOO": self.rb_voo,
            "AAI": self.rb_aai,
            "VVI": self.rb_vvi,
        }
        rb = mapping.get(mode, self.rb_vvi)
        rb.setChecked(True)

    def _current_mode(self) -> str:
        if self.rb_aoo.isChecked():
            return "AOO"
        if self.rb_voo.isChecked():
            return "VOO"
        if self.rb_aai.isChecked():
            return "AAI"
        return "VVI"

    def _update_description(self):
        descs = {
            "AOO": "AOO — Asynchronous atrial pacing at the programmed lower rate; no sensing or inhibition.",
            "VOO": "VOO — Asynchronous ventricular pacing at the programmed lower rate; no sensing or inhibition.",
            "AAI": "AAI — Atrial demand pacing: senses atrium; inhibits pacing on atrial sense; paces atrium at LRL otherwise.",
            "VVI": "VVI — Ventricular demand pacing: senses ventricle; inhibits pacing on ventricular sense; paces ventricle at LRL otherwise.",
        }
        mode = self._current_mode()
        self.lbl_desc.setText(descs.get(mode, ""))

    def _save_mode(self):
        self.selection.mode = self._current_mode()
        try:
            with open(MODE_FILE, "w") as f:
                json.dump(asdict(self.selection), f, indent=2)
            QMessageBox.information(self, "Saved", f"Pacing mode set to {self.selection.mode}.")
        except Exception as e:
            QMessageBox.warning(self, "Save Failed", str(e))

    def _load(self) -> ModeSelection:
        if os.path.exists(MODE_FILE):
            try:
                data = json.load(open(MODE_FILE, "r"))
                return ModeSelection(**data)
            except Exception:
                pass
        return ModeSelection()
