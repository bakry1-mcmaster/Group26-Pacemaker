"""Combined page: pacing mode selection + parameters with stable spacing.

This widget does not introspect ParametersPage's layout. Instead it
builds its own parameter rows (each in a dedicated QWidget container),
so hiding rows collapses space consistently across modes.
"""

import json
import os
from dataclasses import dataclass, asdict

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QIntValidator, QDoubleValidator
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QButtonGroup,
    QSizePolicy,
)


PARAMS_FILE = "dcm_params.json"


@dataclass
class PacingParams:
    # Rates in bpm
    lrl_bpm: int = 60  # Lower Rate Limit
    url_bpm: int = 120  # Upper Rate Limit

    # Atrial
    a_amp_mV: float = 3000.0
    a_pw_ms: float = 0.4

    # Ventricular
    v_amp_mV: float = 3500.0
    v_pw_ms: float = 0.4

    # Refractory
    arp_ms: int = 250
    vrp_ms: int = 320


class ModeParametersPage(QWidget):
    goHome = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ModeParametersPage")

        # Mode → parameter keys
        self.visible_by_mode = {
            "AOO": ["LRL", "URL", "AA", "APW"],
            "VOO": ["LRL", "URL", "VA", "VPW"],
            "AAI": ["LRL", "URL", "AA", "APW", "ARP"],  # subset supported in UI
            "VVI": ["LRL", "URL", "VA", "VPW", "VRP"],  # subset supported in UI
        }

        self.params = self._load()
        self._build_ui()
        self._wire()
        self._select_default_mode()

    # --- UI ---
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Mode radios row
        self.rb_aoo = QRadioButton("AOO")
        self.rb_voo = QRadioButton("VOO")
        self.rb_aai = QRadioButton("AAI")
        self.rb_vvi = QRadioButton("VVI")
        self.mode_group = QButtonGroup(self)
        for rb in (self.rb_aoo, self.rb_voo, self.rb_aai, self.rb_vvi):
            self.mode_group.addButton(rb)
            rb.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        mode_row = QHBoxLayout()
        mode_row.addWidget(self.rb_aoo)
        mode_row.addWidget(self.rb_voo)
        mode_row.addWidget(self.rb_aai)
        mode_row.addWidget(self.rb_vvi)
        mode_row.addStretch(1)
        root.addLayout(mode_row)

        # Parameter rows container
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(8)
        root.addLayout(self.rows_layout)

        # Build editor widgets
        self.ed_lrl = QLineEdit(str(self.params.lrl_bpm))
        self.ed_lrl.setValidator(QIntValidator(30, 175, self))

        self.ed_url = QLineEdit(str(self.params.url_bpm))
        self.ed_url.setValidator(QIntValidator(50, 175, self))

        self.ed_a_amp = QLineEdit(str(self.params.a_amp_mV))
        self.ed_a_amp.setValidator(QDoubleValidator(500.0, 7000.0, 1, self))

        self.ed_a_pw = QLineEdit(str(self.params.a_pw_ms))
        self.ed_a_pw.setValidator(QDoubleValidator(0.1, 1.9, 2, self))

        self.ed_v_amp = QLineEdit(str(self.params.v_amp_mV))
        self.ed_v_amp.setValidator(QDoubleValidator(500.0, 7000.0, 1, self))

        self.ed_v_pw = QLineEdit(str(self.params.v_pw_ms))
        self.ed_v_pw.setValidator(QDoubleValidator(0.1, 1.9, 2, self))

        self.ed_arp = QLineEdit(str(self.params.arp_ms))
        self.ed_arp.setValidator(QIntValidator(150, 500, self))

        self.ed_vrp = QLineEdit(str(self.params.vrp_ms))
        self.ed_vrp.setValidator(QIntValidator(150, 500, self))

        # Row containers: key -> QWidget row with label+editor
        def make_row(label_text, editor):
            row = QWidget(self)
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(8)
            lbl = QLabel(label_text, row)
            h.addWidget(lbl)
            h.addWidget(editor, 1)
            return row

        self.row_widgets = {
            "LRL": make_row("Lower Rate Limit (bpm)", self.ed_lrl),
            "URL": make_row("Upper Rate Limit (bpm)", self.ed_url),
            "AA": make_row("Atrial Amplitude (mV)", self.ed_a_amp),
            "APW": make_row("Atrial Pulse Width (ms)", self.ed_a_pw),
            "VA": make_row("Ventricular Amplitude (mV)", self.ed_v_amp),
            "VPW": make_row("Ventricular Pulse Width (ms)", self.ed_v_pw),
            "ARP": make_row("ARP (ms)", self.ed_arp),
            "VRP": make_row("VRP (ms)", self.ed_vrp),
        }

        # Fixed order we will always use when (re)building the list
        self._row_order = [
            "LRL", "URL", "AA", "APW", "VA", "VPW", "ARP", "VRP"
        ]

        # Add all rows initially (visibility handled by mode)
        for key in self._row_order:
            self.rows_layout.addWidget(self.row_widgets[key])

        # Buttons row
        btn_row = QHBoxLayout()
        self.btn_reset = QPushButton("Reset Defaults")
        self.btn_save = QPushButton("Save Parameters")
        btn_row.addWidget(self.btn_reset)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_save)
        root.addLayout(btn_row)

        # Back button centered style (non-expanding)
        back_row = QHBoxLayout()
        back_row.addStretch(1)
        self.btn_back = QPushButton("Back to Dashboard")
        self.btn_back.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        back_row.addWidget(self.btn_back)
        back_row.addStretch(1)
        root.addLayout(back_row)

        root.addStretch(1)

    def _wire(self):
        for rb in (self.rb_aoo, self.rb_voo, self.rb_aai, self.rb_vvi):
            rb.toggled.connect(lambda checked, m=rb.text(): checked and self.update_visible_params(m))

        for w in (
            self.ed_lrl,
            self.ed_url,
            self.ed_a_amp,
            self.ed_a_pw,
            self.ed_v_amp,
            self.ed_v_pw,
            self.ed_arp,
            self.ed_vrp,
        ):
            w.textChanged.connect(self._clear_status)

        self.btn_save.clicked.connect(self._save)
        self.btn_reset.clicked.connect(self._reset)
        self.btn_back.clicked.connect(self.goHome.emit)

    # --- Behavior ---
    def _select_default_mode(self):
        self.rb_aoo.setChecked(True)
        self.update_visible_params("AOO")

    def update_visible_params(self, mode: str):
        allowed = set(self.visible_by_mode.get(mode, []))
        for key, row in self.row_widgets.items():
            row.setVisible(key in allowed)
        self.adjustSize()
        self.updateGeometry()

    def _clear_status(self):
        # Placeholder: no visible status label in this compact page
        pass

    # --- Model IO ---
    def _load(self) -> PacingParams:
        if os.path.exists(PARAMS_FILE):
            try:
                with open(PARAMS_FILE, "r") as f:
                    data = json.load(f)
                return PacingParams(**data)
            except Exception:
                pass
        return PacingParams()

    def _apply_to_model(self):
        self.params.lrl_bpm = int(self.ed_lrl.text())
        self.params.url_bpm = int(self.ed_url.text())
        self.params.a_amp_mV = float(self.ed_a_amp.text())
        self.params.a_pw_ms = float(self.ed_a_pw.text())
        self.params.v_amp_mV = float(self.ed_v_amp.text())
        self.params.v_pw_ms = float(self.ed_v_pw.text())
        self.params.arp_ms = int(self.ed_arp.text())
        self.params.vrp_ms = int(self.ed_vrp.text())

    def _reset(self):
        self.params = PacingParams()
        self._refresh_fields()

    def _refresh_fields(self):
        self.ed_lrl.setText(str(self.params.lrl_bpm))
        self.ed_url.setText(str(self.params.url_bpm))
        self.ed_a_amp.setText(str(self.params.a_amp_mV))
        self.ed_a_pw.setText(str(self.params.a_pw_ms))
        self.ed_v_amp.setText(str(self.params.v_amp_mV))
        self.ed_v_pw.setText(str(self.params.v_pw_ms))
        self.ed_arp.setText(str(self.params.arp_ms))
        self.ed_vrp.setText(str(self.params.vrp_ms))

    def _validate_all(self) -> bool:
        def ok_line(w):
            v = w.validator()
            if v is None:
                return True
            s = w.text()
            pos = 0
            return v.validate(s, pos)[0] == v.Acceptable

        fields = [
            (self.ed_lrl, True),
            (self.ed_url, True),
            (self.ed_a_amp, True),
            (self.ed_a_pw, True),
            (self.ed_v_amp, True),
            (self.ed_v_pw, True),
            (self.ed_arp, True),
            (self.ed_vrp, True),
        ]
        for w, _ in fields:
            if not ok_line(w):
                return False
        try:
            lrl = int(self.ed_lrl.text())
            url = int(self.ed_url.text())
            if lrl > url:
                return False
        except ValueError:
            return False
        return True

    def _save(self):
        if not self._validate_all():
            # Silent fail; validation UI could be added later
            return
        self._apply_to_model()
        try:
            with open(PARAMS_FILE, "w") as f:
                json.dump(asdict(self.params), f, indent=2)
        except Exception:
            pass

