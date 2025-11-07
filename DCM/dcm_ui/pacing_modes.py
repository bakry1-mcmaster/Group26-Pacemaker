# DEFUNCT - moved to mode_parameters_page.py
import json
import os
from dataclasses import dataclass, asdict

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QRadioButton,
    QLabel,
    QPushButton,
    QMessageBox,
)

MODE_FILE = "dcm_mode.json"


@dataclass
class ModeSelection:
    mode: str = "VVI"  # default; valid: AOO, VOO, AAI, VVI


class PacingModesPage(QWidget):
    goHome = pyqtSignal()  # used by MainWindow to navigate back

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PacingModesPage")

        # Load previously saved selection
        self.selection = self._load()

        # Layout root
        root = QVBoxLayout(self)

        title = QLabel("Pacing Modes")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        root.addWidget(title)

        # Modes group
        box = QGroupBox("Select Mode")
        box_layout = QVBoxLayout()
        box.setLayout(box_layout)

        self.rb_aoo = QRadioButton("AOO")
        # LRL, URL, AA, APW
        self.rb_voo = QRadioButton("VOO")
        # LRL, URL, VA, VPW
        self.rb_aai = QRadioButton("AAI")
        # LRL, URL, AA, APW, AS, ARP, PVARP, Hys, RS 
        self.rb_vvi = QRadioButton("VVI")
        # LRL, URL, VA, VPW, VS, VRP, Hys, RS

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
        self.btn_back = QPushButton("Back to Dashboard")
        self.btn_save = QPushButton("Save Mode")
        row.addWidget(self.btn_back)
        row.addStretch(1)
        row.addWidget(self.btn_save)
        root.addLayout(row)

        # Inline status label (green, like ParametersPage)
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color:#2a7; font-weight:500;")
        root.addWidget(self.lbl_status)

        root.addStretch(1)

        # Initialize selection + description
        self._init_selection(self.selection.mode)
        self._update_description()

        # Signals
        for rb in (self.rb_aoo, self.rb_voo, self.rb_aai, self.rb_vvi):
            rb.toggled.connect(self._on_mode_changed)

        self.btn_save.clicked.connect(self._save_mode)
        self.btn_back.clicked.connect(lambda: self.goHome.emit())

    # Helpers
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
            "AOO": "Asynchronous atrial pacing at the programmed lower rate; no sensing or inhibition.",
            "VOO": "Asynchronous ventricular pacing at the programmed lower rate; no sensing or inhibition.",
            "AAI": "Atrial demand pacing: senses atrium; inhibits on atrial sense; otherwise paces at LRL.",
            "VVI": "Ventricular demand pacing: senses ventricle; inhibits on ventricular sense; otherwise paces at LRL.",
        }
        mode = self._current_mode()
        self.lbl_desc.setText(descs.get(mode, ""))

    def _on_mode_changed(self):
        # Clear status when user changes selection and update description
        if hasattr(self, 'lbl_status') and self.lbl_status is not None:
            self.lbl_status.clear()
        self._update_description()

    def _save_mode(self):
        self.selection.mode = self._current_mode()
        try:
            with open(MODE_FILE, "w") as f:
                json.dump(asdict(self.selection), f, indent=2)
            # Inline confirmation instead of popup
            self.lbl_status.setText(f"Pacing mode set to {self.selection.mode}.")
        except Exception as e:
            QMessageBox.warning(self, "Save Failed", str(e))

    def _load(self) -> ModeSelection:
        if os.path.exists(MODE_FILE):
            try:
                with open(MODE_FILE, "r") as f:
                    data = json.load(f)
                return ModeSelection(**data)
            except Exception:
                pass
        return ModeSelection()

