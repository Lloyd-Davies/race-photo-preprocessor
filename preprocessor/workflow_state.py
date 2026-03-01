from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class WorkflowStep(StrEnum):
    SESSION = "session"
    IMPORT = "import"
    PREPARE = "prepare"
    PROCESS = "process"
    REVIEW = "review"
    DEPLOY = "deploy"


STEP_ORDER: tuple[WorkflowStep, ...] = (
    WorkflowStep.SESSION,
    WorkflowStep.IMPORT,
    WorkflowStep.PREPARE,
    WorkflowStep.PROCESS,
    WorkflowStep.REVIEW,
    WorkflowStep.DEPLOY,
)


StepStatus = Literal["not_started", "ready", "running", "needs_attention", "complete"]


@dataclass
class WorkflowState:
    current_step: WorkflowStep
    step_status: dict[WorkflowStep, StepStatus]


def create_initial_state() -> WorkflowState:
    status: dict[WorkflowStep, StepStatus] = {
        step: "not_started" for step in STEP_ORDER
    }
    status[WorkflowStep.SESSION] = "ready"
    return WorkflowState(current_step=WorkflowStep.SESSION, step_status=status)


def can_navigate_to(state: WorkflowState, target: WorkflowStep) -> bool:
    current_idx = STEP_ORDER.index(state.current_step)
    target_idx = STEP_ORDER.index(target)

    if target_idx <= current_idx:
        return True

    return state.step_status[state.current_step] == "complete"


def mark_step_complete(state: WorkflowState, step: WorkflowStep) -> None:
    state.step_status[step] = "complete"

    step_idx = STEP_ORDER.index(step)
    if step_idx < len(STEP_ORDER) - 1:
        next_step = STEP_ORDER[step_idx + 1]
        if state.step_status[next_step] == "not_started":
            state.step_status[next_step] = "ready"


def invalidate_for_slug_change(state: WorkflowState) -> None:
    state.step_status[WorkflowStep.PROCESS] = "needs_attention"
    state.step_status[WorkflowStep.REVIEW] = "needs_attention"
    state.step_status[WorkflowStep.DEPLOY] = "needs_attention"


def invalidate_for_prepare_change(state: WorkflowState) -> None:
    state.step_status[WorkflowStep.PROCESS] = "needs_attention"
    state.step_status[WorkflowStep.REVIEW] = "needs_attention"
    state.step_status[WorkflowStep.DEPLOY] = "needs_attention"


def invalidate_for_reimport(state: WorkflowState) -> None:
    state.step_status[WorkflowStep.REVIEW] = "needs_attention"
    state.step_status[WorkflowStep.DEPLOY] = "needs_attention"
