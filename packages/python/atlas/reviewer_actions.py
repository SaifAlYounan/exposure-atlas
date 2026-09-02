"""Authenticated reviewer actions (REV-003).

The decision core behind the authenticated command API. Real WebAuthn/passkey
authentication, CSRF and HTTP transport bind at the service layer via an
injected, already-authenticated ``Session``; this module enforces the
security *properties* deterministically (A0, pure — no network, credentials
or model calls):

- a session must be authenticated, unexpired, and present its CSRF token;
- the actor is the single operator (Alexios); the assistant is never a
  reviewer and never holds the operator session;
- the four logical roles are separate decision types — an earlier decision of
  one type never satisfies a later right/policy/release decision;
- nonce replay is rejected; idempotency keys make retries safe (no double
  apply); optimistic locking stops concurrent silent overwrites;
- an edited fact without valid support/derivation cannot be saved approved;
- material corrections and boundary/rubric/source-policy/rights-policy changes
  need a same-operator cooling-period confirmation on a later calendar day
  against a fresh diff (not dual adjudication);
- sensitive decision classes can never be bulk-approved.

Every applied decision yields an immutable, schema-valid ``ReviewDecision``
recording actor, role, input version(s), time and reason, plus the resulting
output version.
"""
import dataclasses
import datetime

from .canonical import sha256_hex
from .review_card import CardError, _assertion_ok
from .schemas import validate

HUMAN_ROLES = ("operator_reviewer", "policy_rights_adjudicator", "release_approver")
AUTOMATION_ROLES = ("release_bot",)
OPERATOR = "Alexios"

ACTIONS = ("approve", "reject", "edit", "request_source", "merge", "link",
           "split", "escalate", "correct", "withdraw", "suppress", "retract",
           "defer")

# Decision classes and the role each requires (separation of decision types).
CLASS_REQUIRED_ROLE = {
    "ordinary_review": "operator_reviewer",
    "identity_merge_split": "operator_reviewer",
    "conflict": "operator_reviewer",
    "material_correction": "operator_reviewer",
    "rights_personal_data": "policy_rights_adjudicator",
    "policy_override": "policy_rights_adjudicator",
    "suppression_retraction": "policy_rights_adjudicator",
    "release_approval": "release_approver",
    "automation_qualification": "release_approver",
}
# Classes that can never be bulk-approved.
SENSITIVE_NO_BULK = frozenset({
    "rights_personal_data", "conflict", "identity_merge_split", "policy_override",
    "material_correction", "suppression_retraction", "release_approval",
    "automation_qualification",
})
# Changes needing a later-calendar-day cooling-period confirmation.
COOLING_PERIOD_CLASSES = frozenset({
    "material_correction", "boundary_change", "rubric_change",
    "source_policy_change", "rights_policy_change",
})


class ReviewerActionError(ValueError):
    pass


class AuthError(ReviewerActionError):
    pass


class RoleError(ReviewerActionError):
    pass


class ReplayError(ReviewerActionError):
    pass


class ConcurrencyError(ReviewerActionError):
    pass


class SupportError(ReviewerActionError):
    pass


class CoolingPeriodError(ReviewerActionError):
    pass


class BulkForbiddenError(ReviewerActionError):
    pass


@dataclasses.dataclass
class Session:
    actor: str
    roles: frozenset
    authenticated: bool
    expires_at: str
    csrf_token: str

    def check(self, now: str, csrf: str) -> None:
        if not self.authenticated:
            raise AuthError("session is not authenticated")
        if self.actor != OPERATOR:
            raise AuthError(f"{self.actor!r} is not the operator; the assistant is never a reviewer")
        if _parse(now) >= _parse(self.expires_at):
            raise AuthError("session expired")
        if csrf != self.csrf_token:
            raise AuthError("bad CSRF token")


@dataclasses.dataclass
class ActionRequest:
    task_id: str
    action: str
    role: str
    decision_class: str
    target_ref: str
    expected_version: str
    reason: str
    nonce: str
    idempotency_key: str
    csrf: str
    input_hashes: dict = dataclasses.field(default_factory=dict)
    edited_assertion: dict | None = None
    fresh_diff_hash: str | None = None


def _parse(ts: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def build_decision(task_id: str, action: str, role: str, decided_at: str,
                   reason: str, input_hashes: dict, nonce: str) -> dict:
    dec = {
        "schema_version": "atlas-review-decision/v1",
        "decision_id": "rvd_" + sha256_hex(
            f"{task_id}\n{action}\n{role}\n{decided_at}\n{nonce}".encode())[:12],
        "task_id": task_id,
        "action": action,
        "decided_by": OPERATOR,
        "role": role,
        "decided_at": decided_at,
        "reason": reason,
        "input_hashes": input_hashes,
    }
    validate("review-decision.schema.json", dec)
    return dec


class ActionProcessor:
    """Applies authenticated reviewer actions with the REV-003 guarantees."""

    def __init__(self):
        self._versions: dict[str, str] = {}       # target_ref -> current version
        self._nonces: set[str] = set()
        self._idem: dict[str, dict] = {}          # idempotency_key -> result
        self._staged: dict[tuple, dict] = {}      # (target_ref, class) -> {date, diff}

    def current_version(self, target_ref: str) -> str:
        return self._versions.get(target_ref, "v0")

    def stage_cooling_period(self, target_ref: str, decision_class: str,
                             staged_at: str, diff_hash: str) -> None:
        """Record day-1 intent for a cooling-period change."""
        self._staged[(target_ref, decision_class)] = {
            "date": _parse(staged_at).date().isoformat(), "diff": diff_hash}

    def _require_role(self, req: ActionRequest, session: Session) -> None:
        if req.role not in HUMAN_ROLES:
            raise RoleError(f"{req.role!r} cannot make review decisions")
        if req.role not in session.roles:
            raise RoleError(f"session lacks role {req.role!r}")
        required = CLASS_REQUIRED_ROLE.get(req.decision_class)
        if required is None:
            raise RoleError(f"unknown decision_class {req.decision_class!r}")
        if req.role != required:
            raise RoleError(
                f"decision_class {req.decision_class!r} requires role {required!r}, "
                f"not {req.role!r} (decision types are separate)")

    def process(self, session: Session, req: ActionRequest, now: str) -> dict:
        session.check(now, req.csrf)
        if req.action not in ACTIONS:
            raise ReviewerActionError(f"unknown action {req.action!r}")
        self._require_role(req, session)
        # Idempotent retry: return the prior result, do not re-apply.
        if req.idempotency_key in self._idem:
            return self._idem[req.idempotency_key]
        if req.nonce in self._nonces:
            raise ReplayError("nonce already used (replay)")
        # Optimistic locking: reject a stale write.
        if req.expected_version != self.current_version(req.target_ref):
            raise ConcurrencyError(
                f"stale write: expected {req.expected_version!r}, "
                f"current {self.current_version(req.target_ref)!r}")
        # An edited fact must have valid support/derivation before approval.
        if req.edited_assertion is not None:
            try:
                _assertion_ok(req.edited_assertion)
            except CardError as e:
                raise SupportError(str(e)) from e
        # Cooling-period confirmation for material/policy changes.
        if req.decision_class in COOLING_PERIOD_CLASSES:
            staged = self._staged.get((req.target_ref, req.decision_class))
            if staged is None:
                raise CoolingPeriodError("no staged intent; a cooling-period change must be staged first")
            if staged["date"] >= _parse(now).date().isoformat():
                raise CoolingPeriodError("confirmation must be on a later calendar day than staging")
            if not req.fresh_diff_hash or req.fresh_diff_hash != staged["diff"]:
                raise CoolingPeriodError("confirmation requires the same fresh diff seen at staging")

        # Apply: bump version, record immutable decision.
        input_version = self.current_version(req.target_ref)
        output_version = "v" + str(int(input_version[1:]) + 1) if input_version.startswith("v") \
            else sha256_hex(input_version.encode())[:8]
        hashes = dict(req.input_hashes)
        decision = build_decision(req.task_id, req.action, req.role, now,
                                  req.reason, hashes, req.nonce)
        self._versions[req.target_ref] = output_version
        self._nonces.add(req.nonce)
        result = {"decision": decision, "input_version": input_version,
                  "output_version": output_version, "target_ref": req.target_ref}
        self._idem[req.idempotency_key] = result
        if req.decision_class in COOLING_PERIOD_CLASSES:
            self._staged.pop((req.target_ref, req.decision_class), None)
        return result

    def process_bulk(self, session: Session, reqs: list[ActionRequest], now: str) -> list[dict]:
        """Apply several actions at once; refused if ANY is a sensitive class."""
        offending = [r.decision_class for r in reqs if r.decision_class in SENSITIVE_NO_BULK]
        if offending:
            raise BulkForbiddenError(f"bulk approval is forbidden for sensitive classes: {sorted(set(offending))}")
        return [self.process(session, r, now) for r in reqs]
