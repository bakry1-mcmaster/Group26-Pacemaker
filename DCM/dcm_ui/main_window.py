from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QMessageBox, QGroupBox, QStackedWidget, QVBoxLayout, QHBoxLayout
)
from dcm_core.user_manager import UserManager
from dcm_ui.mode_parameters_page import ModeParametersPage
from dcm_core.telemetry import TelemetryService, TelemetryState
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
        status_box.setLayout(status_layout)
        dashboard_layout.addWidget(status_box)

        # Utility buttons row
        util_row = QHBoxLayout()
        self.btn_about = QPushButton("About")
        self.btn_set_clock = QPushButton("Set Clock")
        self.btn_new_patient = QPushButton("New Patient")
        self.btn_quit_tel = QPushButton("Quit Telemetry")
        util_row.addWidget(self.btn_about)
        util_row.addWidget(self.btn_set_clock)
        util_row.addWidget(self.btn_new_patient)
        util_row.addStretch(1)
        util_row.addWidget(self.btn_quit_tel)
        dashboard_layout.addLayout(util_row)

        self.dashboard_group.setLayout(dashboard_layout)

        # Combined page
        self.mode_params_page = ModeParametersPage(self)

        self.stack.addWidget(self.dashboard_group)   # index 0
        self.stack.addWidget(self.mode_params_page)  # index 1

        # --- Telemetry service (stub) ---
        self.telemetry = TelemetryService()
        self.telemetry.stateChanged.connect(self._on_tel_state)

        # --- Connect signals ---
        # Both buttons route to the combined page
        self.btn_modes_parameters.clicked.connect(
            lambda: self.stack.setCurrentWidget(self.mode_params_page)
        )


        # Utility actions
        self.btn_about.clicked.connect(self._show_about)
        self.btn_set_clock.clicked.connect(self._set_clock)
        self.btn_new_patient.clicked.connect(self._new_patient)
        self.btn_quit_tel.clicked.connect(self._quit_telemetry)

        # Back signals from subpages
        if hasattr(self.mode_params_page, "goHome"):
            self.mode_params_page.goHome.connect(
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
        QMessageBox.information(self, "Set Clock", "TODO: set clock")

    def _new_patient(self):
        # End current session but keep app running; next session may be a new device
        self.telemetry.end_session()
        # Clear UI extras as part of new workflow
        self.lbl_note.clear()
        QMessageBox.information(self, "New Patient", "Ready to interrogate a new device.")

    def _quit_telemetry(self):
        self.telemetry.end_session()
        QMessageBox.information(self, "Telemetry", "Telemetry session ended.")
