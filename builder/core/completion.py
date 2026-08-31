"""Provider-neutral completion gate (HAR-000-03/HAR-005).

TaskTransition is authoritative: a provider result — success, failure,
interruption, max-turn exit, or success-without-valid-output — can only
PROPOSE completion. `done` requires a passing evidence receipt bound to
the exact result commit; gate satisfaction additionally requires the
receipt to be non-self-asserted (clean-checkout CI). This wraps the
same logic tools/atlas_plan.py enforces so both paths cannot diverge.
"""
import atlas_plan


class CompletionRefused(RuntimeError):
    pass


VALID_TERMINATIONS = {"complete"}


def close_task(task_id: str, *, termination_reason: str,
               structured_output_valid: bool) -> str:
    """Returns 'done' or raises. Never trusts the provider signal."""
    if termination_reason not in VALID_TERMINATIONS:
        raise CompletionRefused(
            f"termination {termination_reason!r} cannot complete a task")
    if not structured_output_valid:
        raise CompletionRefused(
            "provider success without valid structured output cannot complete")
    if atlas_plan.task_verify(task_id) != 0:
        raise CompletionRefused(
            "no passing evidence receipt bound to HEAD; task stays open")
    return "done"
