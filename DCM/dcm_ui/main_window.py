from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QMessageBox, QGroupBox, QStackedWidget, QVBoxLayout, QHBoxLayout,
    QComboBox,
)
from dcm_core.user_manager import UserManager
from dcm_ui.mode_parameters_page import ModeParametersPage
from dcm_core.telemetry import TelemetryService, TelemetryState
from dcm_ui.egram_page import EgramPage

import json, os

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Device Controller Monitor")
        self.resize(800, 600)
        self.setMinimumSize(600, 400)

        self.user_manager = UserManager()
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        # --- Login Widgets ---
        self.login_group = QGroupBox()
        login_layout = QVBoxLayout()

        self.login_user = QLineEdit()
        self.login_user.setPlaceholderText("Username")
        login_layout.addWidget(self.login_user)

        self.login_pass = QLineEdit()
        self.login_pass.setPlaceholderText("Password")
        self.login_pass.setEchoMode(QLineEdit.Password)
        login_layout.addWidget(self.login_pass)
        
        quick_admin = QPushButton("Debug Admin Login")
        quick_admin.clicked.connect(self._login_admin)
        login_layout.addWidget(quick_admin)

        login_button = QPushButton("Login")
        login_button.clicked.connect(self.handle_login)
        login_layout.addWidget(login_button)
        
        self.btn_register = QPushButton("Register")
        self.btn_register.clicked.connect(self.open_register)
        login_layout.addWidget(self.btn_register)

        self.login_group.setLayout(login_layout)
        self.main_layout.addWidget(self.login_group)

        # --- Stacked Pages (Dashboard + Parameters + Pacing Modes) ---
        self.stack = QStackedWidget()
        self.main_layout.addWidget(self.stack)
        self.stack.setVisible(False)

        # Dashboard
        self.dashboard_group = QGroupBox("Dashboard")
        dashboard_layout = QVBoxLayout()
        self.welcome_label = QLabel("")
        dashboard_layout.addWidget(self.welcome_label)

        self.btn_modes_parameters = QPushButton("Modes and Parameters")
        dashboard_layout.addWidget(self.btn_modes_parameters)

        self.btn_egram = QPushButton("Egram Viewer")
        dashboard_layout.addWidget(self.btn_egram)



        # Status/Telemetry panel
        status_box = QGroupBox("Status")
        status_layout = QVBoxLayout()
        self.lbl_comm = QLabel("Telemetry: Disconnected")
        self.lbl_device = QLabel("Device: —")
        self.lbl_note = QLabel("")
        self.lbl_note.setStyleSheet("color:#a66;")
        status_layout.addWidget(self.lbl_comm)
        status_layout.addWidget(self.lbl_device)
        status_layout.addWidget(self.lbl_note)
        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("Communication Port:"))
        self.port_combo = QComboBox()
        self._refresh_ports()
        port_row.addWidget(self.port_combo)
        self.btn_toggle_comm = QPushButton("Connect Telemetry")
        self.btn_refresh_ports = QPushButton("Refresh")
        port_row.addWidget(self.btn_toggle_comm)
        port_row.addWidget(self.btn_refresh_ports)
        status_layout.addLayout(port_row)
        status_box.setLayout(status_layout)
        dashboard_layout.addWidget(status_box)

        # Utility buttons row
        util_row = QHBoxLayout()
        self.btn_about = QPushButton("About")
        self.btn_set_clock = QPushButton("Set Clock")
        self.btn_new_patient = QPushButton("New Patient")
        self.btn_accessibility = QPushButton("Accessibility")
        util_row.addWidget(self.btn_about)
        util_row.addWidget(self.btn_set_clock)
        util_row.addWidget(self.btn_new_patient)
        util_row.addWidget(self.btn_accessibility)
        util_row.addStretch(1)
        dashboard_layout.addLayout(util_row)

        self.dashboard_group.setLayout(dashboard_layout)

        # Combined page
        self.mode_params_page = ModeParametersPage(self)
        self.mode_params_page.fontPreferencesChanged.connect(self._apply_global_font)

        # Egram page
        self.egram_page = EgramPage(self)

        self.stack.addWidget(self.dashboard_group)   # index 0
        self.stack.addWidget(self.mode_params_page)  # index 1
        self.stack.addWidget(self.egram_page)  # index 1

        # --- Telemetry service (stub) ---
        self.telemetry = TelemetryService()
        self.telemetry.stateChanged.connect(self._on_tel_state)
        self.telemetry.serialConnected.connect(self._on_serial_connected)
        self.telemetry.serialDisconnected.connect(self._on_serial_disconnected)
        self.telemetry.serialError.connect(self._on_serial_error)
        self.telemetry.rawDataReceived.connect(self._on_raw_data)
        self.mode_params_page.setTelemetry(self.telemetry)

        self.egram_page.setTelemetry(self.telemetry)


        # --- Connect signals ---
        # Both buttons route to the combined page
        self.btn_modes_parameters.clicked.connect(
            lambda: self.stack.setCurrentWidget(self.mode_params_page)
        )

        self.btn_egram.clicked.connect(
        lambda: self.stack.setCurrentWidget(self.egram_page)
)



        # Utility actions
        self.btn_about.clicked.connect(self._show_about)
        self.btn_set_clock.clicked.connect(self._set_clock)
        self.btn_new_patient.clicked.connect(self._new_patient)
        self.btn_accessibility.clicked.connect(self.mode_params_page.open_accessibility_dialog)
        self.btn_toggle_comm.clicked.connect(self._toggle_connection)
        self.btn_refresh_ports.clicked.connect(self._refresh_ports)

        # Back signals from subpages
        if hasattr(self.mode_params_page, "goHome"):
            self.mode_params_page.goHome.connect(
                lambda: self.stack.setCurrentWidget(self.dashboard_group)
            )
        self._apply_global_font(self.mode_params_page._font_family, self.mode_params_page._font_size)

        if hasattr(self.mode_params_page, "goHome"):
            self.mode_params_page.goHome.connect(
            lambda: self.stack.setCurrentWidget(self.dashboard_group)
        )
            
        if hasattr(self.egram_page, "goHome"):
            self.egram_page.goHome.connect(
            lambda: self.stack.setCurrentWidget(self.dashboard_group)
        )


    # --- Event Handlers ---
    def open_register(self):
        from dcm_ui.register_dialog import RegisterDialog
        dlg = RegisterDialog(self)
        if dlg.exec_():
            u, p = dlg.values()
            ok, msg = self.user_manager.register(u, p)
            if ok:
                QMessageBox.information(self, "Registration", msg)
            else:
                QMessageBox.warning(self, "Registration", msg)

    def handle_login(self):
        user = self.login_user.text()
        password = self.login_pass.text()
        if self.user_manager.login(user, password):
            self.login_group.hide()
            self.stack.setVisible(True)
            self.stack.setCurrentWidget(self.dashboard_group)
            self.welcome_label.setText(f"Welcome, {user}!")
            # Start a simulated telemetry session with a placeholder device id
            self.telemetry.start_session(device_id="PG-TEST-001")
        else:
            QMessageBox.warning(self, "Login Failed", "Invalid username or password.")

    def _login_admin(self):
        """Convenience helper for testing: logs in as admin/password if available."""
        self.login_user.setText("admin")
        self.login_pass.setText("password")
        self.handle_login()

    # --- Telemetry/UI helpers ---
    def _on_tel_state(self, state: str, device_id, note):
        self.lbl_comm.setText(f"Telemetry: {state}")
        self.lbl_device.setText(f"Device: {device_id or '—'}")
        self.lbl_note.setText(note or "")

    def _show_about(self):
        info = {
            "app_model": "PACEMAKER-DCM",
            "app_version": "0.1.0",
            "dcm_serial": "DCM-0001",
            "institution": "McMaster University",
        }
        cfg_path = os.path.join(os.path.dirname(__file__), "..", "dcm_info.json")
        try:
            cfg_path = os.path.normpath(cfg_path)
            if os.path.exists(cfg_path):
                with open(cfg_path, "r") as f:
                    data = json.load(f)
                    info.update({k: v for k, v in data.items() if v})
        except Exception:
            pass
        text = (
            f"Application model: {info['app_model']}\n"
            f"Software version: {info['app_version']}\n"
            f"DCM serial: {info['dcm_serial']}\n"
            f"Institution: {info['institution']}"
        )
        QMessageBox.information(self, "About", text)
        
    def _set_clock(self):
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        QMessageBox.information(self, "Set Clock", f"Time set as: {now}")

    def _new_patient(self):
        # Clear contextual notes so the clinician can start fresh
        self.lbl_note.setText("Ready to interrogate a new device.")
        QMessageBox.information(self, "New Patient", "Patient context reset. Connect telemetry when ready.")

    def _toggle_connection(self):
        if self.telemetry.status().state == TelemetryState.DISCONNECTED:
            port = self.port_combo.currentData()
            if not port:
                QMessageBox.warning(self, "Telemetry", "Select a serial port first.")
                return
            self.telemetry.configure_serial(port)
            if self.telemetry.connect_serial():
                self.btn_toggle_comm.setText("Disconnect Telemetry")
            else:
                self.lbl_note.setText("UART connection failed.")
        else:
            self.telemetry.end_session()
            self.lbl_note.setText("Telemetry session ended.")
            self.btn_toggle_comm.setText("Connect Telemetry")

    def _on_serial_connected(self, port: str):
        self.lbl_note.setText(f"UART connected on {port}.")

    def _on_serial_disconnected(self):
        self.lbl_note.setText("UART disconnected.")

    def _on_serial_error(self, message: str):
        self.lbl_note.setText(message)
        QMessageBox.warning(self, "UART Error", message)

    def _on_raw_data(self, data: bytes):
        # Placeholder hook; could be extended to parse egrams/echo packets.
        self.lbl_note.setText(f"RX {len(data)} bytes")

    def _apply_global_font(self, family: str, size: int):
        from PyQt5.QtGui import QFont
        from PyQt5.QtWidgets import QApplication

        font = QFont(family, size)
        app = QApplication.instance()
        if app:
            app.setFont(font)
        self.setFont(font)

    def _refresh_ports(self):
        self.port_combo.clear()
        try:
            from serial.tools import list_ports
            ports = list_ports.comports()
        except Exception:
            ports = []
        if not ports:
            self.port_combo.addItem("No ports detected", None)
            return
        for info in ports:
            label = f"{info.device} ({info.description})"
            self.port_combo.addItem(label, info.device)
