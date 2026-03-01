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
from preprocessor.session_step import SessionStep
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
        self.tabs.tabBar().hide()

        self._workflow_action_bar = QWidget()
        action_layout = QHBoxLayout(self._workflow_action_bar)
        action_layout.setContentsMargins(10, 0, 10, 10)
        action_layout.setSpacing(8)
        action_layout.addStretch()

        self.workflow_primary_button = QPushButton("")
        self.workflow_primary_button.clicked.connect(self._on_primary_action)
        action_layout.addWidget(self.workflow_primary_button)

        main_layout.addWidget(self._step_indicator)
        main_layout.addWidget(self.tabs, 1)
        main_layout.addWidget(self._workflow_action_bar)
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
        self.session_step = SessionStep(self)
        self.import_tab = ImportTab(self)
        self.process_tab = ProcessTab(self)
        self.bibs_tab = BibsTab(self)
        self.deploy_tab = DeployTab(self)

        self.tabs.addTab(self.session_step, "  Session  ")
        self.tabs.addTab(self.import_tab, "  Import  ")
        self.tabs.addTab(self.process_tab, "  Process  ")
        self.tabs.addTab(self.bibs_tab, "  Bibs  ")
        self.tabs.addTab(self.deploy_tab, "  Deploy  ")

        self.import_tab.selection_changed.connect(lambda *_: self._sync_workflow_ui())
        self.process_tab.run_finished.connect(self._on_process_finished)
        self.deploy_tab.deploy_finished.connect(self._on_deploy_finished)

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
            WorkflowStep.SESSION: 0,
            WorkflowStep.IMPORT: 1,
            WorkflowStep.PREPARE: 2,
            WorkflowStep.PROCESS: 2,
            WorkflowStep.REVIEW: 3,
            WorkflowStep.DEPLOY: 4,
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

        self._sync_primary_action()

        active = self._step_to_tab_index(self._workflow_state.current_step)
        if active is not None:
            self.tabs.setCurrentIndex(active)

    def _on_step_requested(self, step: WorkflowStep) -> None:
        if not can_navigate_to(self._workflow_state, step):
            self.set_status("Complete the current step before moving forward.")
            return

        self._workflow_state.current_step = step
        self._sync_workflow_ui()

    def _sync_primary_action(self) -> None:
        step = self._workflow_state.current_step
        if step == WorkflowStep.SESSION:
            self.workflow_primary_button.hide()
            return

        self.workflow_primary_button.show()

        if step == WorkflowStep.IMPORT:
            selected = len(self.import_tab.selected_paths())
            self.workflow_primary_button.setText("Complete Import")
            self.workflow_primary_button.setEnabled(selected > 0)
            return

        if step == WorkflowStep.PREPARE:
            self.workflow_primary_button.setText("Save & Continue")
            self.workflow_primary_button.setEnabled(True)
            return

        if step == WorkflowStep.PROCESS:
            self.workflow_primary_button.setText("Start Processing")
            self.workflow_primary_button.setEnabled(True)
            return

        if step == WorkflowStep.REVIEW:
            self.workflow_primary_button.setText("Approve & Continue")
            self.workflow_primary_button.setEnabled(True)
            return

        self.workflow_primary_button.setText("Deploy")
        self.workflow_primary_button.setEnabled(True)

    def _on_primary_action(self) -> None:
        step = self._workflow_state.current_step
        if step == WorkflowStep.IMPORT:
            self.complete_import()
            return

        if step == WorkflowStep.PREPARE:
            self.complete_prepare()
            return

        if step == WorkflowStep.PROCESS:
            self.start_process_step()
            return

        if step == WorkflowStep.REVIEW:
            self.complete_review()
            return

        if step == WorkflowStep.DEPLOY:
            self.start_deploy_step()

    def set_workflow_step_complete(self, step: WorkflowStep) -> None:
        from preprocessor.workflow_state import mark_step_complete

        mark_step_complete(self._workflow_state, step)
        self._sync_workflow_ui()

    def complete_session(self) -> None:
        self.set_workflow_step_complete(WorkflowStep.SESSION)
        self._workflow_state.current_step = WorkflowStep.IMPORT
        self._sync_workflow_ui()

    def complete_import(self) -> None:
        selected = self.import_tab.selected_paths()
        if not selected:
            self.set_status("Select at least one image before completing Import.")
            self._sync_workflow_ui()
            return

        self.set_workflow_step_complete(WorkflowStep.IMPORT)
        self._workflow_state.current_step = WorkflowStep.PREPARE
        self._sync_workflow_ui()

    def complete_prepare(self) -> None:
        self.set_workflow_step_complete(WorkflowStep.PREPARE)
        self._workflow_state.current_step = WorkflowStep.PROCESS
        self._sync_workflow_ui()

    def start_process_step(self) -> None:
        self.set_workflow_step_status(WorkflowStep.PROCESS, "running")
        self.process_tab.start_processing()

    def _on_process_finished(self, success: bool) -> None:
        self.set_workflow_step_status(
            WorkflowStep.PROCESS,
            "complete" if success else "needs_attention",
        )
        if success:
            self.set_workflow_step_status(WorkflowStep.REVIEW, "ready")
            self._workflow_state.current_step = WorkflowStep.REVIEW
        self._sync_workflow_ui()

    def complete_review(self) -> None:
        self.set_workflow_step_complete(WorkflowStep.REVIEW)
        self._workflow_state.current_step = WorkflowStep.DEPLOY
        self._sync_workflow_ui()

    def start_deploy_step(self) -> None:
        self.set_workflow_step_status(WorkflowStep.DEPLOY, "running")
        self.deploy_tab.start_upload()

    def _on_deploy_finished(self, success: bool) -> None:
        self.set_workflow_step_status(
            WorkflowStep.DEPLOY,
            "complete" if success else "needs_attention",
        )
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
