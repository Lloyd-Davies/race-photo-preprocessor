from __future__ import annotations

from preprocessor.workflow_state import (
    STEP_ORDER,
    WorkflowStep,
    can_navigate_to,
    create_initial_state,
    invalidate_for_prepare_change,
    invalidate_for_reimport,
    invalidate_for_slug_change,
    mark_step_complete,
)


def test_initial_state_starts_on_session_and_only_session_ready() -> None:
    state = create_initial_state()

    assert state.current_step == WorkflowStep.SESSION
    assert state.step_status[WorkflowStep.SESSION] == "ready"
    for step in STEP_ORDER[1:]:
        assert state.step_status[step] == "not_started"


def test_cannot_navigate_forward_until_current_step_complete() -> None:
    state = create_initial_state()

    assert can_navigate_to(state, WorkflowStep.IMPORT) is False

    mark_step_complete(state, WorkflowStep.SESSION)
    assert can_navigate_to(state, WorkflowStep.IMPORT) is True


def test_can_always_navigate_backward() -> None:
    state = create_initial_state()
    mark_step_complete(state, WorkflowStep.SESSION)
    state.current_step = WorkflowStep.PREPARE

    assert can_navigate_to(state, WorkflowStep.SESSION) is True


def test_slug_change_invalidation_marks_downstream_attention() -> None:
    state = create_initial_state()
    for step in STEP_ORDER:
        mark_step_complete(state, step)

    invalidate_for_slug_change(state)

    assert state.step_status[WorkflowStep.PROCESS] == "needs_attention"
    assert state.step_status[WorkflowStep.REVIEW] == "needs_attention"
    assert state.step_status[WorkflowStep.DEPLOY] == "needs_attention"


def test_prepare_change_invalidation_marks_processing_chain_attention() -> None:
    state = create_initial_state()
    for step in STEP_ORDER:
        mark_step_complete(state, step)

    invalidate_for_prepare_change(state)

    assert state.step_status[WorkflowStep.PROCESS] == "needs_attention"
    assert state.step_status[WorkflowStep.REVIEW] == "needs_attention"
    assert state.step_status[WorkflowStep.DEPLOY] == "needs_attention"


def test_reimport_invalidation_marks_review_and_deploy_attention() -> None:
    state = create_initial_state()
    for step in STEP_ORDER:
        mark_step_complete(state, step)

    invalidate_for_reimport(state)

    assert state.step_status[WorkflowStep.REVIEW] == "needs_attention"
    assert state.step_status[WorkflowStep.DEPLOY] == "needs_attention"
