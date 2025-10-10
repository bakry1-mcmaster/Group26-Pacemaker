from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QMessageBox, QGroupBox, QStackedWidget, QVBoxLayout
)
from dcm_core.user_manager import UserManager
from dcm_ui.parameters_page import ParametersPage
from dcm_ui.pacing_modes import PacingModesPage

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

        self.btn_pacing = QPushButton("Pacing Modes")
        dashboard_layout.addWidget(self.btn_pacing)

        self.btn_parameters = QPushButton("Parameters")
        dashboard_layout.addWidget(self.btn_parameters)

        self.dashboard_group.setLayout(dashboard_layout)

        # Parameters page
        self.params_page = ParametersPage(self)

        # Pacing modes page
        self.pacing_page = PacingModesPage(self)

        self.stack.addWidget(self.dashboard_group)  # index 0
        self.stack.addWidget(self.params_page)      # index 1
        self.stack.addWidget(self.pacing_page)      # index 2   <-- fixed .addWidget

        # --- Connect signals ---
        self.btn_parameters.clicked.connect(
            lambda: self.stack.setCurrentWidget(self.params_page)
        )
        self.btn_pacing.clicked.connect(
            lambda: self.stack.setCurrentWidget(self.pacing_page)
        )

        # Back signals from subpages
        self.params_page.goHome.connect(
            lambda: self.stack.setCurrentWidget(self.dashboard_group)
        )
        self.pacing_page.goHome.connect(
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
        else:
            QMessageBox.warning(self, "Login Failed", "Invalid username or password.")
