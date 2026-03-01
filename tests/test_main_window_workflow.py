from __future__ import annotations

from pathlib import Path

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


def test_main_window_session_step_is_initial_page(qtbot: QtBot) -> None:
    window = MainWindow(dark_mode=True)
    qtbot.addWidget(window)

    assert window.tabs.currentWidget() is window.session_step


def test_session_create_moves_to_import_when_valid(qtbot: QtBot, tmp_path) -> None:
    window = MainWindow(dark_mode=True)
    qtbot.addWidget(window)

    window.sidebar.slug_input.setText("my-race")
    window.sidebar.name_input.setText("My Race")
    window.sidebar.output_input.setText(str(tmp_path))
    window.sidebar.store_url_input.setText("https://photos.example.com")
    window.sidebar.store_token_input.setText("credential")

    window.session_step.create_session_button.click()

    assert window.workflow_state.step_status[WorkflowStep.SESSION] == "complete"
    assert window.workflow_state.current_step == WorkflowStep.IMPORT
    assert window.tabs.currentWidget() is window.import_tab


def test_session_create_shows_validation_errors_when_missing_fields(qtbot: QtBot) -> None:
    window = MainWindow(dark_mode=True)
    qtbot.addWidget(window)

    window.sidebar.slug_input.setText("")
    window.sidebar.name_input.setText("")
    window.sidebar.output_input.setText("")
    window.sidebar.store_url_input.setText("")
    window.sidebar.store_token_input.setText("")

    window.session_step.create_session_button.click()

    assert window.workflow_state.step_status[WorkflowStep.SESSION] != "complete"
    assert "required" in window.session_step.validation_label.text().lower()


def test_import_primary_action_blocked_without_selection(qtbot: QtBot, tmp_path: Path) -> None:
    window = MainWindow(dark_mode=True)
    qtbot.addWidget(window)

    window.sidebar.slug_input.setText("my-race")
    window.sidebar.name_input.setText("My Race")
    window.sidebar.output_input.setText(str(tmp_path))
    window.sidebar.store_url_input.setText("https://photos.example.com")
    window.sidebar.store_token_input.setText("credential")
    window.session_step.create_session_button.click()

    assert window.workflow_state.current_step == WorkflowStep.IMPORT
    assert window.workflow_primary_button.isEnabled() is False


def test_import_primary_action_completes_with_selection(
    qtbot: QtBot,
    tmp_path: Path,
    photo_folder: Path,
) -> None:
    window = MainWindow(dark_mode=True)
    qtbot.addWidget(window)

    window.sidebar.slug_input.setText("my-race")
    window.sidebar.name_input.setText("My Race")
    window.sidebar.output_input.setText(str(tmp_path))
    window.sidebar.store_url_input.setText("https://photos.example.com")
    window.sidebar.store_token_input.setText("credential")
    window.session_step.create_session_button.click()

    window.import_tab._load_folder(str(photo_folder))

    assert window.workflow_primary_button.isEnabled() is True
    window.workflow_primary_button.click()

    assert window.workflow_state.step_status[WorkflowStep.IMPORT] == "complete"
    assert window.workflow_state.current_step == WorkflowStep.PREPARE
