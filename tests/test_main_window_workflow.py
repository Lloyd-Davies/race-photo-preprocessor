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
