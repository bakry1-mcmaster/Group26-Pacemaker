# pacing_modes.py
# - Lists all pacing modes from Part 1.
# - Simple dropdowns, buttons, or tabbed interface.
import json, os
from dataclasses import dataclass, asdict
from PyQt5.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox
)
from PyQt5.QtGui import QIntValidator, QDoubleValidator
from PyQt5.QtCore import Qt

PARAMS_FILE = "dcm_modes.json"

@dataclass
class PacingModes:
    # Rates in bpm
    lrl_bpm: int = 60        # Lower Rate Limit
    url_bpm: int = 120       # Upper Rate Limit

    # Atrial
    a_amp_mV: float = 3000.0   # 500–7000 mV suggested
    a_pw_ms: float = 0.4        # 0.1–1.9 ms

    # Ventricular
    v_amp_mV: float = 3500.0    # 500–7000 mV
    v_pw_ms: float = 0.4        # 0.1–1.9 ms

    # Refractory periods
    arp_ms: int = 250           # 150–500 ms
    vrp_ms: int = 320           # 150–500 ms

class PacingModesPage(QWidget):
    """Collects + validates core D1 parameters and persists locally.
    Ranges used (Deliverable 1 friendly):
      - LRL: 30–175 bpm (maps to 343–2000 ms)
      - URL: 50–175 bpm (UI only in D1)
      - A/V Amplitudes: 500–7000 mV
      - A/V Pulse Width: 0.1–1.9 ms
      - ARP/VRP: 150–500 ms
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('ParametersPage')

        self.params = self._load()

        self.form = QFormLayout()
        self.setLayout(QVBoxLayout())
        self.layout().addLayout(self.form)

        # --- Widgets ---
        
        # Save / Reset buttons
        row = QHBoxLayout()
        self.aoo = QPushButton("AOO")
        self.voo = QPushButton("VOO")
        self.aai = QPushButton("AAI")
        self.vvi = QPushButton("VVI")
        self.btn_reset = QPushButton("Reset Defaults")

        self.btn_save = QPushButton("Save Parameters")
        self.btn_reset = QPushButton("Reset Defaults")
        row.addWidget(self.btn_reset)
        row.addStretch(1)
        row.addWidget(self.btn_save)
        row.addStretch(1)
        row.addWidget(self.aoo)
        row.addStretch(1)
        row.addWidget(self.voo)
        row.addStretch(1)
        row.addWidget(self.aai)
        row.addStretch(1)
        row.addWidget(self.vvi)
        self.layout().addLayout(row)

        # Status label
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color:#2a7; font-weight:500;")
        self.layout().addWidget(self.lbl_status)

        # NEW: Back to Dashboard button
        self.btn_back = QPushButton("← Back to Dashboard")
        self.layout().addWidget(self.btn_back)

        self.layout().addStretch(1)

        # Signals


        self.btn_save.clicked.connect(self._save)
        self.btn_reset.clicked.connect(self._reset)
        self.btn_back.clicked.connect(self._go_home)

    # --- helpers ---
    def _load(self) -> PacingParams:
        if os.path.exists(PARAMS_FILE):
            try:
                data = json.load(open(PARAMS_FILE, 'r'))
                return PacingParams(**data)
            except Exception:
                pass
        return PacingModes()

    def _save(self):
        if not self._validate_all(show_msg=True):
            return
        self._apply_to_model()
        try:
            with open(PARAMS_FILE, 'w') as f:
                json.dump(asdict(self.params), f, indent=2)
            self.lbl_status.setText("Parameters saved ✔")
        except Exception as e:
            QMessageBox.warning(self, "Save Failed", str(e))

    def _reset(self):
        self.params = PacingModes()
        self._refresh_fields()
        self.lbl_status.setText("Defaults restored.")

    def _apply_to_model(self):
        self.params.lrl_bpm = int(self.ed_lrl.text())
        self.params.url_bpm = int(self.ed_url.text())
        self.params.a_amp_mV = float(self.ed_a_amp.text())
        self.params.a_pw_ms = float(self.ed_a_pw.text())
        self.params.v_amp_mV = float(self.ed_v_amp.text())
        self.params.v_pw_ms = float(self.ed_v_pw.text())
        self.params.arp_ms = int(self.ed_arp.text())
        self.params.vrp_ms = int(self.ed_vrp.text())

    def _refresh_fields(self):
        self.ed_lrl.setText(str(self.params.lrl_bpm))
        self.ed_url.setText(str(self.params.url_bpm))
        self.ed_a_amp.setText(str(self.params.a_amp_mV))
        self.ed_a_pw.setText(str(self.params.a_pw_ms))
        self.ed_v_amp.setText(str(self.params.v_amp_mV))
        self.ed_v_pw.setText(str(self.params.v_pw_ms))
        self.ed_arp.setText(str(self.params.arp_ms))
        self.ed_vrp.setText(str(self.params.vrp_ms))
        self._update_intervals()

    def _on_changed(self):
        self.lbl_status.clear()
        self._update_intervals()

    def _update_intervals(self):
        # Convert bpm -> ms safely
        def to_ms(bpm_text: str):
            try:
                bpm = int(bpm_text)
                return int(round(60000.0 / bpm)) if bpm > 0 else 0
            except ValueError:
                return 0
        lri = to_ms(self.ed_lrl.text())
        uri = to_ms(self.ed_url.text())
        self.lbl_lri.setText(f"{lri} ms" if lri else "–")
        self.lbl_uri.setText(f"{uri} ms" if uri else "–")

    def _validate_all(self, show_msg=False) -> bool:
        # Ensure all fields pass their validators and bounds (including logical checks)
        fields = [
            (self.ed_lrl, "LRL (30–175 bpm)"),
            (self.ed_url, "URL (50–175 bpm)"),
            (self.ed_a_amp, "Atrial Amplitude (500–7000 mV)"),
            (self.ed_a_pw, "Atrial PW (0.1–1.9 ms)"),
            (self.ed_v_amp, "Ventricular Amplitude (500–7000 mV)"),
            (self.ed_v_pw, "Ventricular PW (0.1–1.9 ms)"),
            (self.ed_arp, "ARP (150–500 ms)"),
            (self.ed_vrp, "VRP (150–500 ms)")
        ]
        for w, name in fields:
            if not w.hasAcceptableInput():
                if show_msg:
                    QMessageBox.warning(self, "Invalid Input", f"Please correct: {name}")
                return False
        # Logical: LRL <= URL
        try:
            lrl = int(self.ed_lrl.text()); url = int(self.ed_url.text())
            if lrl > url:
                if show_msg:
                    QMessageBox.warning(self, "Invalid Rates", "LRL must be ≤ URL.")
                return False
        except ValueError:
            if show_msg:
                QMessageBox.warning(self, "Invalid Rates", "Rates must be integers.")
            return False
        return True

    def _go_home(self):
        """Return to the dashboard page inside MainWindow's stacked widget."""
        parent = self.parent()
        if parent and hasattr(parent, "stack") and hasattr(parent, "dashboard_group"):
            parent.stack.setCurrentWidget(parent.dashboard_group)