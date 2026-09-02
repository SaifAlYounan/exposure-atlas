"""Evaluation governance (EVAL-000).

Frozen before any prompt/model development. This module is the executable
half of the governance frozen in ``config/eval/governance.yaml`` and the
``eval-governance`` / ``eval-item`` schemas:

- one-time, deterministic partition assignment (examples / development /
  calibration / held_out) so an item can never migrate between partitions;
- held-out access control: runtime and release credentials can never read
  held-out labels/answer keys, and neither can the builder;
- blinded ordering: for calibration/held-out items the operator commits the
  initial label before any model votes are revealed; a later same-operator
  reconsideration is retained separately and is not dual adjudication;
- underpowered slices resolve to the governance disposition
  (``review_only``/``unsupported``), never silently pooled;
- prompt/rubric authors cannot self-certify a G2 slice: certification needs
  the operator's frozen labels AND the operator's gate decision.

Pure functions; no network, no credentials, no model calls (A0).
"""
import datetime
import pathlib

import yaml

from .canonical import sha256_hex
from .schemas import validate

ROOT = pathlib.Path(__file__).resolve().parents[3]
GOVERNANCE_PATH = ROOT / "config" / "eval" / "governance.yaml"

# Only the operator (a human) may read held-out labels/answer keys. Runtime
# workers, the release bot and the builder are all denied — the held-out keys
# never enter any automated read path.
_HOLDOUT_READERS = frozenset({"operator"})


def load_governance(path: pathlib.Path | None = None) -> dict:
    """Load and schema-validate the frozen governance manifest."""
    doc = yaml.safe_load((path or GOVERNANCE_PATH).read_text())
    validate("eval-governance.schema.json", doc)
    return doc


def eval_item_id(stage: str, matter_ref: str) -> str:
    """Deterministic evaluation-item id (stable for a stage+matter pair)."""
    return "evi_" + sha256_hex(f"{stage}\n{matter_ref}".encode())[:12]


def assign_partition(item_key: str, governance: dict) -> str:
    """One-time, deterministic partition for an item.

    The partition is a pure function of ``item_key`` and the frozen salt, so
    re-running assignment always yields the same partition — an item can never
    leak from held_out into development.
    """
    pa = governance["partition_assignment"]
    weights = pa["weights"]
    parts = sorted(weights)  # deterministic order, independent of dict order
    total = sum(weights[p] for p in parts)
    bucket = int(sha256_hex(f"{pa['salt']}\n{item_key}".encode()), 16) % total
    acc = 0
    for p in parts:
        acc += weights[p]
        if bucket < acc:
            return p
    return parts[-1]  # pragma: no cover - total guarantees a hit


def can_read_holdout(role: str, governance: dict | None = None) -> bool:
    """Whether ``role`` may read held-out labels/answer keys.

    Governance pins ``runtime_can_read_labels: false``; only the operator
    may read. Runtime/release/builder roles are always denied.
    """
    if governance is not None and governance["holdout_access"]["runtime_can_read_labels"]:
        # Defensive: a manifest that ever flipped this is rejected upstream by
        # the schema (const false); treat any truthy value as still denying
        # non-operator roles.
        pass
    return role in _HOLDOUT_READERS


def slice_disposition(n_items: int, stage: str, governance: dict) -> str:
    """'supported' when the slice meets the stage's min items, else the
    governance underpowered disposition (never silently pooled)."""
    reg = next((s for s in governance["stage_metrics"] if s["stage"] == stage), None)
    if reg is None:
        raise KeyError(f"no stage_metrics registration for stage {stage!r}")
    if n_items >= reg["min_items_supported"]:
        return "supported"
    return governance["underpowered_disposition"]


def _parse(ts: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def blinded_ordering_ok(item: dict) -> bool:
    """For a blinded item, the operator's initial label must be committed
    before model votes are revealed. Non-blinded items are unconstrained; a
    blinded item whose votes are not yet revealed is fine."""
    if not item.get("blinded"):
        return True
    lc = item.get("label_commit")
    if not lc:
        return False
    revealed = item.get("votes_revealed_at")
    if revealed is None:
        return True
    return _parse(revealed) >= _parse(lc["committed_at"])


def reconsideration_is_separate(item: dict) -> bool:
    """A same-operator reconsideration must be retained separately from the
    committed label and is never counted as a second adjudication."""
    rec = item.get("reconsideration")
    if rec is None:
        return True
    return rec.get("retained_separately") is True


def is_dual_adjudication(item: dict) -> bool:
    """A reconsideration by the single operator is NOT dual adjudication."""
    return False


def can_certify_gate(author_role: str, certifier_role: str,
                     has_operator_frozen_labels: bool,
                     has_operator_gate_decision: bool) -> bool:
    """G2 certification requires the operator (not a prompt/rubric author) to
    certify, backed by the operator's frozen labels AND gate decision. A
    prompt/rubric author can never self-certify."""
    return (certifier_role == "operator"
            and author_role != "operator"
            and has_operator_frozen_labels
            and has_operator_gate_decision)
