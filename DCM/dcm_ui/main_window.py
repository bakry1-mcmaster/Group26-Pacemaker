# dcm_ui/main_window.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QMessageBox, QGroupBox, QStackedWidget
)
from dcm_core.user_manager import UserManager
from dcm_ui.parameters_page import ParametersPage  # make sure this file exists
from dcm_ui.pacing_modes import PacingModesPage
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Device Controller Monitor")

        # --- Set default window size and minimum size ---
        self.resize(800, 600)           # default size
        self.setMinimumSize(600, 400)   # cannot shrink below this

        self.user_manager = UserManager()
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        # =========================
        # Login Group
        # =========================
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

        # Register button (added AFTER login_layout exists)
        self.btn_register = QPushButton("Register")
        self.btn_register.clicked.connect(self.open_register)
        login_layout.addWidget(self.btn_register)

        self.login_group.setLayout(login_layout)
        self.main_layout.addWidget(self.login_group)

        # =========================
        # Stacked pages (Dashboard + Parameters)
        # =========================
        self.stack = QStackedWidget()
        self.main_layout.addWidget(self.stack)
        self.stack.setVisible(False)  # hidden until login succeeds

        # --- Dashboard page ---
        self.dashboard_group = QGroupBox("Dashboard")
        dashboard_layout = QVBoxLayout()

        self.welcome_label = QLabel("")
        dashboard_layout.addWidget(self.welcome_label)

        self.btn_pacing = QPushButton("Pacing Modes")
        dashboard_layout.addWidget(self.btn_pacing)

        self.btn_parameters = QPushButton("Parameters")
        dashboard_layout.addWidget(self.btn_parameters)

        self.dashboard_group.setLayout(dashboard_layout)

        # --- Parameters page ---
        self.params_page = ParametersPage(self)
        self.pacing_page = PacingModesPage(self)

        # Add pages to stack
        self.stack.addWidget(self.dashboard_group)  # index 0
        self.stack.addWidget(self.params_page)      # index 1
        self.stack.addWidget(self.pacing_page)

        # Navigation
        self.btn_parameters.clicked.connect(
            lambda: self.stack.setCurrentWidget(self.params_page)
        )
        self.btn_pacing.clicked.connect(
            lambda: self.stack.setCurrentWidget(self.pacing_page)
        )

        # (Optional) Wire a simple way back to dashboard from the params page
        # e.g., add a top-level button in ParametersPage and connect it here if desired.

    # =========================
    # Slots
    # =========================
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
            # Switch to stacked pages (dashboard shown by default)
            self.login_group.hide()
            self.stack.setVisible(True)
            self.stack.setCurrentWidget(self.dashboard_group)
            self.welcome_label.setText(f"Welcome, {user}!")
        else:
            QMessageBox.warning(self, "Login Failed", "Invalid username or password.")