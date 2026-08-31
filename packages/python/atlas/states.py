"""Pure state machines (DOM-004). Every transition not listed fails."""


class TransitionError(ValueError):
    pass


CANDIDATE_WORK = {
    "open": {"fetch_pending", "blocked", "resolved"},
    "fetch_pending": {"triage_pending", "blocked", "resolved"},
    "triage_pending": {"extraction_pending", "blocked", "resolved"},
    "extraction_pending": {"verification_pending", "blocked", "resolved"},
    "verification_pending": {"classification_pending", "blocked", "resolved"},
    "classification_pending": {"review_pending", "blocked", "resolved"},
    "review_pending": {"blocked", "resolved"},
    "blocked": {"open", "fetch_pending", "triage_pending", "extraction_pending",
                "verification_pending", "classification_pending",
                "review_pending", "resolved"},
    "resolved": set(),
}

CANDIDATE_DISPOSITION = {
    "unresolved": {"awaiting_primary", "excluded", "duplicate", "linked_existing",
                   "record_created", "rejected", "quarantined", "escalated"},
    "awaiting_primary": {"excluded", "duplicate", "linked_existing",
                         "record_created", "rejected", "quarantined", "escalated"},
    "escalated": {"awaiting_primary", "excluded", "duplicate", "linked_existing",
                  "record_created", "rejected", "quarantined"},
    "quarantined": {"excluded", "rejected", "escalated"},
    # terminal-ish dispositions change only through audited decisions:
    "excluded": {"unresolved"},   # boundary-change replay
    "duplicate": set(), "linked_existing": set(), "record_created": set(),
    "rejected": set(),
}

REVISION = {
    "draft": {"in_review"},
    "in_review": {"approved", "rejected", "draft"},
    "approved": {"published"},
    "published": {"superseded"},
    "rejected": set(),
    "superseded": set(),
}

VERIFICATION = {
    "not_run": {"running"},
    "running": {"passed", "failed"},
    "passed": set(),   # a retry is a NEW run, never a rewrite
    "failed": set(),
}

JOB = {
    "ready": {"leased", "cancelled"},
    "leased": {"completed", "retry_scheduled", "dead_lettered", "cancelled"},
    "retry_scheduled": {"ready", "cancelled"},
    "completed": set(),
    "dead_lettered": set(),
    "cancelled": set(),
}

MONITORING = {
    "idle": {"checking"},
    "checking": {"idle", "change_pending", "degraded"},
    "degraded": {"checking"},
    "change_pending": {"idle"},   # after review resolves the draft revision
}

MACHINES = {"candidate_work": CANDIDATE_WORK,
            "candidate_disposition": CANDIDATE_DISPOSITION,
            "revision": REVISION, "verification": VERIFICATION,
            "job": JOB, "monitoring": MONITORING}


def transition(machine: str, current: str, target: str) -> str:
    table = MACHINES[machine]
    if current not in table:
        raise TransitionError(f"{machine}: unknown state {current!r}")
    if target not in table.get(current, set()):
        raise TransitionError(f"{machine}: illegal transition {current!r} -> {target!r}")
    return target
