"""Main application window."""
from __future__ import annotations

from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from preprocessor.sidebar import Sidebar
from preprocessor.tabs.import_tab import ImportTab
from preprocessor.tabs.process_tab import ProcessTab
from preprocessor.tabs.bibs_tab import BibsTab
from preprocessor.tabs.deploy_tab import DeployTab
from preprocessor.workflow_state import (
    STEP_ORDER,
    WorkflowState,
    WorkflowStep,
    can_navigate_to,
    create_initial_state,
)


class MainWindow(QMainWindow):
    def __init__(self, dark_mode: bool = True) -> None:
        super().__init__()
        self._dark_mode = dark_mode
        self._workflow_state: WorkflowState = create_initial_state()
        self.setWindowTitle("Race Photo Preprocessor")
        self.resize(1280, 800)
        self.setMinimumSize(900, 600)

        # ── Central layout ────────────────────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Splitter: sidebar | tabs ──────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        layout.addWidget(splitter)

        # Sidebar
        self.sidebar = Sidebar(window=self)
        self.sidebar.setProperty("sidebar", True)
        self.sidebar.setMinimumWidth(220)
        self.sidebar.setMaximumWidth(300)
        splitter.addWidget(self.sidebar)

        # Main area: workflow stepper + tabs
        main_area = QWidget()
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._step_buttons: dict[WorkflowStep, QPushButton] = {}
        self._step_indicator = QWidget()
        step_layout = QHBoxLayout(self._step_indicator)
        step_layout.setContentsMargins(10, 8, 10, 8)
        step_layout.setSpacing(6)

        for step in STEP_ORDER:
            btn = QPushButton()
            btn.setProperty("secondary", True)
            btn.clicked.connect(lambda _checked=False, s=step: self._on_step_requested(s))
            step_layout.addWidget(btn)
            self._step_buttons[step] = btn

        step_layout.addStretch()

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        main_layout.addWidget(self._step_indicator)
        main_layout.addWidget(self.tabs, 1)
        splitter.addWidget(main_area)

        # Right insights panel
        insights = QWidget()
        insights.setMinimumWidth(220)
        insights.setMaximumWidth(320)
        insights_layout = QVBoxLayout(insights)
        insights_layout.setContentsMargins(12, 12, 12, 12)
        insights_layout.setSpacing(8)

        health_title = QLabel("Run Health")
        health_title.setProperty("heading", True)
        insights_layout.addWidget(health_title)

        self.run_health_label = QLabel("")
        self.run_health_label.setWordWrap(True)
        insights_layout.addWidget(self.run_health_label)

        attention_title = QLabel("Attention")
        attention_title.setProperty("heading", True)
        insights_layout.addWidget(attention_title)

        self.attention_count_label = QLabel("")
        self.attention_count_label.setWordWrap(True)
        insights_layout.addWidget(self.attention_count_label)

        insights_layout.addStretch()
        splitter.addWidget(insights)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([240, 1040])

        # ── Tabs ──────────────────────────────────────────────────────────────
        self.import_tab = ImportTab(self)
        self.process_tab = ProcessTab(self)
        self.bibs_tab = BibsTab(self)
        self.deploy_tab = DeployTab(self)

        self.tabs.addTab(self.import_tab, "  Import  ")
        self.tabs.addTab(self.process_tab, "  Process  ")
        self.tabs.addTab(self.bibs_tab, "  Bibs  ")
        self.tabs.addTab(self.deploy_tab, "  Deploy  ")

        self._sync_workflow_ui()

        # ── Status bar ────────────────────────────────────────────────────────
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready")

    # ── Public helpers ────────────────────────────────────────────────────────

    def set_status(self, message: str) -> None:
        self._status.showMessage(message)

    def _step_to_tab_index(self, step: WorkflowStep) -> int | None:
        mapping = {
            WorkflowStep.IMPORT: 0,
            WorkflowStep.PREPARE: 1,
            WorkflowStep.PROCESS: 1,
            WorkflowStep.REVIEW: 2,
            WorkflowStep.DEPLOY: 3,
        }
        return mapping.get(step)

    def _status_label(self, step: WorkflowStep) -> str:
        label = str(self._workflow_state.step_status[step]).replace("_", " ")
        return f"{step.value.title()} · {label}"

    def _sync_workflow_ui(self) -> None:
        attention_count = 0
        for step in STEP_ORDER:
            button = self._step_buttons[step]
            button.setText(self._status_label(step))
            button.setEnabled(can_navigate_to(self._workflow_state, step) or step == self._workflow_state.current_step)
            if self._workflow_state.step_status[step] == "needs_attention":
                attention_count += 1

        current_status = self._workflow_state.step_status[self._workflow_state.current_step]
        self.run_health_label.setText(
            f"Current: {self._workflow_state.current_step.value} ({str(current_status).replace('_', ' ')})"
        )
        self.attention_count_label.setText(f"Needs attention: {attention_count}")

        active = self._step_to_tab_index(self._workflow_state.current_step)
        if active is not None:
            self.tabs.setCurrentIndex(active)

    def _on_step_requested(self, step: WorkflowStep) -> None:
        if not can_navigate_to(self._workflow_state, step):
            self.set_status("Complete the current step before moving forward.")
            return

        self._workflow_state.current_step = step
        self._sync_workflow_ui()

    def set_workflow_step_complete(self, step: WorkflowStep) -> None:
        from preprocessor.workflow_state import mark_step_complete

        mark_step_complete(self._workflow_state, step)
        self._sync_workflow_ui()

    def set_workflow_step_status(self, step: WorkflowStep, status: str) -> None:
        self._workflow_state.step_status[step] = status  # type: ignore[assignment]
        self._sync_workflow_ui()

    def get_event_slug(self) -> str:
        return self.sidebar.slug_input.text().strip()

    def get_selected_images(self) -> list[str]:
        return self.import_tab.selected_paths()

    @property
    def dark_mode(self) -> bool:
        return self._dark_mode

    @property
    def workflow_state(self) -> WorkflowState:
        return self._workflow_state

    @property
    def workflow_step_buttons(self) -> dict[WorkflowStep, QPushButton]:
        return self._step_buttons

    def toggle_theme(self) -> None:
        """Switch between dark and light themes and persist the choice."""
        from preprocessor.app import get_stylesheet
        self._dark_mode = not self._dark_mode
        QApplication.instance().setStyleSheet(get_stylesheet(self._dark_mode))  # type: ignore[union-attr]
        QSettings("RacePhotoStore", "Preprocessor").setValue("ui/dark_mode", self._dark_mode)
        self.sidebar.update_theme_button(self._dark_mode)
