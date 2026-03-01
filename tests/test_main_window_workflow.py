from __future__ import annotations

from pytestqt.plugin import QtBot  # type: ignore[import]

from preprocessor.main_window import MainWindow
from preprocessor.workflow_state import WorkflowStep


def test_main_window_initialises_workflow_state(qtbot: QtBot) -> None:
    window = MainWindow(dark_mode=True)
    qtbot.addWidget(window)

    state = window.workflow_state
    assert state.current_step == WorkflowStep.SESSION
    assert state.step_status[WorkflowStep.SESSION] == "ready"
    assert state.step_status[WorkflowStep.IMPORT] == "not_started"


def test_main_window_renders_all_workflow_steps(qtbot: QtBot) -> None:
    window = MainWindow(dark_mode=True)
    qtbot.addWidget(window)

    buttons = window.workflow_step_buttons
    assert set(buttons.keys()) == {
        WorkflowStep.SESSION,
        WorkflowStep.IMPORT,
        WorkflowStep.PREPARE,
        WorkflowStep.PROCESS,
        WorkflowStep.REVIEW,
        WorkflowStep.DEPLOY,
    }


def test_main_window_blocks_forward_navigation_until_current_complete(qtbot: QtBot) -> None:
    window = MainWindow(dark_mode=True)
    qtbot.addWidget(window)

    window.workflow_step_buttons[WorkflowStep.IMPORT].click()

    assert window.workflow_state.current_step == WorkflowStep.SESSION

    window.set_workflow_step_complete(WorkflowStep.SESSION)
    window.workflow_step_buttons[WorkflowStep.IMPORT].click()

    assert window.workflow_state.current_step == WorkflowStep.IMPORT


def test_main_window_exposes_run_insights_panel(qtbot: QtBot) -> None:
    window = MainWindow(dark_mode=True)
    qtbot.addWidget(window)

    assert window.run_health_label.text()
    assert "session" in window.run_health_label.text().lower()
    assert "0" in window.attention_count_label.text()
