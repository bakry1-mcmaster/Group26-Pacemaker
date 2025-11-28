# dcm_ui/egram_page.py

from __future__ import annotations

from collections import deque
from typing import Optional

import json
import os
from datetime import datetime

from dcm_core.egram_data import ParamsRecorded, EgramRecord, EgramBlock, new_template


from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QRadioButton,
    QButtonGroup,
    QSizePolicy,
)

from dcm_core.telemetry import TelemetryService
import pyqtgraph as pg  # for plotting


class EgramPage(QWidget):
    goHome = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("EgramPage")

        self._telemetry: Optional[TelemetryService] = None

        self._max_samples = 1000
        self._atr_buf = deque(maxlen=self._max_samples)
        self._ven_buf = deque(maxlen=self._max_samples)

        self._build_ui()

        self._timer = QTimer(self)
        self._timer.setInterval(40)  
        self._timer.timeout.connect(self._refresh_plot)
        self._timer.start()

        # recording model
        self._record: Optional[EgramRecord] = None
        self._block: Optional[EgramBlock] = None

        #user
        self._username: Optional[str] = None


    def setTelemetry(self, telemetry: TelemetryService):
        self._telemetry = telemetry
        telemetry.egramSampleReceived.connect(self._on_egram_sample)

    # --- UI ---
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Title
        title = QLabel("Egram Viewer")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        root.addWidget(title)

        # Channel selection
        chan_box = QGroupBox("Channels")
        chan_layout = QHBoxLayout(chan_box)

        self.rb_atrial = QRadioButton("Atrial")
        self.rb_ventricular = QRadioButton("Ventricular")
        self.rb_both = QRadioButton("Both")

        # default: ventricular
        self.rb_ventricular.setChecked(True)

        self.channel_group = QButtonGroup(self)
        for rb in (self.rb_atrial, self.rb_ventricular, self.rb_both):
            self.channel_group.addButton(rb)

        chan_layout.addWidget(self.rb_atrial)
        chan_layout.addWidget(self.rb_ventricular)
        chan_layout.addWidget(self.rb_both)
        chan_layout.addStretch(1)

        root.addWidget(chan_box)

        # Plot area
        plot_box = QGroupBox("Real-time Egram")
        plot_layout = QVBoxLayout(plot_box)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground("w")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel("left", "Amplitude", units="mV")
        self.plot_widget.setLabel("bottom", "Sample")
        self.plot_widget.setYRange(0, 15)

        self._atr_curve = self.plot_widget.plot(pen=pg.mkPen("r", width=1))
        self._ven_curve = self.plot_widget.plot(pen=pg.mkPen("b", width=1))

        plot_layout.addWidget(self.plot_widget)
        root.addWidget(plot_box, stretch=1)

        # Control row
        ctrl_row = QHBoxLayout()
        self.btn_start = QPushButton("Start Egram")
        self.btn_stop = QPushButton("Stop Egram")
        self.btn_stop.setEnabled(False)

        ctrl_row.addWidget(self.btn_start)
        ctrl_row.addWidget(self.btn_stop)
        ctrl_row.addStretch(1)
        root.addLayout(ctrl_row)

        # Back button (same style as other pages)
        back_row = QHBoxLayout()
        back_row.addStretch(1)
        self.btn_back = QPushButton("Back to Dashboard")
        self.btn_back.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        back_row.addWidget(self.btn_back)
        back_row.addStretch(1)
        root.addLayout(back_row)

        # signals
        self.btn_back.clicked.connect(self.goHome.emit)
        self.btn_start.clicked.connect(self._start_egram)
        self.btn_stop.clicked.connect(self._stop_egram)


    # --- telemetry interaction ---
    def _start_egram(self):
        if not self._telemetry:
            return

        self._atr_buf.clear()
        self._ven_buf.clear()

        #build EgramRecord + initial block

        # load current params (if file missing, use defaults)
        try:
            with open("dcm_params.json", "r") as f:
                params_data = json.load(f)
            params = ParamsRecorded(**params_data)
        except Exception:
            params = ParamsRecorded()

        # load current mode string (if missing, leave as None)
        mode = None
        try:
            with open("dcm_mode.json", "r") as f:
                mode_data = json.load(f)
                mode = (mode_data or {}).get("mode")
        except Exception:
            pass

        # simple session id based on timestamp
        session_id = datetime.utcnow().strftime("EGRAM-%Y%m%dT%H%M%S")

        # create record
        self._record = new_template(
            session_id=session_id,
            mode=mode,
            params=params,
            user=self._username,          
            source="simulated",  # !!!hardware!!!
        )

        if self.rb_both.isChecked():
            channel = "AV"
        elif self.rb_atrial.isChecked():
            channel = "A"
        else:
            channel = "V"

        self._block = EgramBlock(
            channel=channel,
            sample_rate_Hz=10, #!!!double check what the sample rate is!!!
        )
        self._record.blocks.append(self._block)

        self._telemetry.request_egram()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)


    def _stop_egram(self):
        if self._telemetry:
            self._telemetry.stop_egram()

        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

        # if we have a recording, save it
        if self._record is not None:
            from datetime import datetime

            year_month = datetime.now().strftime("%Y-%m")
            user = self._username or "User"  

            fname = f"EGRAM_{user}_{year_month}.json"
            try:
                with open(fname, "w") as f:
                    f.write(self._record.to_json(indent=2))
            except Exception:
                pass

            # reset record/block
            self._record = None
            self._block = None


    def _on_egram_sample(self, atr, atr_marker, ven, ven_marker):
        self._atr_buf.append(atr)
        self._ven_buf.append(ven)

        if self._block is not None:
            # normalize Nones to 0 / "--" so JSON stays clean
            self._block.atr_samples.append(int(atr) if isinstance(atr, (int, float)) else 0)
            self._block.ven_samples.append(int(ven) if isinstance(ven, (int, float)) else 0)
            self._block.atr_markers.append(atr_marker or "--")
            self._block.ven_markers.append(ven_marker or "--")
            
            print("v samples:", ven)

    # --- plotting ---
    def _refresh_plot(self):
        if not self._ven_buf:
            return

        n = len(self._ven_buf)
        x = list(range(n))

        show_atrial = self.rb_atrial.isChecked() or self.rb_both.isChecked()
        show_vent = self.rb_ventricular.isChecked() or self.rb_both.isChecked()

        atr_vals = [a if isinstance(a, (int, float)) else 0 for a in self._atr_buf]
        ven_vals = [v if isinstance(v, (int, float)) else 0 for v in self._ven_buf]

        if show_atrial:
            self._atr_curve.setData(x, atr_vals)
        else:
            self._atr_curve.setData([], [])

        if show_vent:
            self._ven_curve.setData(x, ven_vals)
        else:
            self._ven_curve.setData([], [])

    
    def set_username(self, username: Optional[str]):
        self._username = username
