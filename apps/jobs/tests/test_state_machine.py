import pytest

from apps.jobs.state_machine import IllegalTransitionError, JobStatus, validate_transition


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (JobStatus.NEW, JobStatus.ASSIGNED),
        (JobStatus.ASSIGNED, JobStatus.EN_ROUTE),
        (JobStatus.ASSIGNED, JobStatus.CANCELLED),
        (JobStatus.EN_ROUTE, JobStatus.ON_SITE),
        (JobStatus.ON_SITE, JobStatus.COMPLETED),
    ],
)
def test_valid_transitions_pass(from_status: str, to_status: str) -> None:
    validate_transition(from_status, to_status)  # must not raise


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (JobStatus.NEW, JobStatus.COMPLETED),
        (JobStatus.NEW, JobStatus.EN_ROUTE),
        (JobStatus.EN_ROUTE, JobStatus.COMPLETED),
        (JobStatus.COMPLETED, JobStatus.NEW),
        (JobStatus.CANCELLED, JobStatus.ASSIGNED),
    ],
)
def test_illegal_transitions_raise(from_status: str, to_status: str) -> None:
    with pytest.raises(IllegalTransitionError):
        validate_transition(from_status, to_status)


def test_terminal_states_have_no_allowed_next() -> None:
    for terminal in (JobStatus.COMPLETED, JobStatus.CANCELLED):
        with pytest.raises(IllegalTransitionError):
            validate_transition(terminal, JobStatus.NEW)


def test_unknown_status_raises() -> None:
    with pytest.raises(IllegalTransitionError):
        validate_transition("not-a-real-status", JobStatus.NEW)
