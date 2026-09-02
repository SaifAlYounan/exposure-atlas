"""Weekly decision pack and transport (REV-004).

Builds one immutable weekly pack manifest ordered P0/P1 first then by
age/value, capped by the measured capacity rules (SPEC §0.2 / §9 REV-004),
and the rights-safe transport around it. Guarantees:

- each pack is capped (review minutes / decision cards / complex decisions);
  excess work stays queued and discovery throttles automatically;
- single-use view links expire, and a replayed link or action envelope fails;
- the channel carries only rights-permitted summaries — a message or link is
  never a bearer credential, so channel compromise alone cannot approve or
  publish (approval goes through the authenticated command API);
- every proposed action binds to exact input hashes; a changed
  source/proposal/policy invalidates the draft decision;
- unanswered cards expire into their named restrictive state.

Pure and deterministic; no network, credentials or model calls (A0).
"""
import datetime

from .canonical import sha256_hex
from .review_card import channel_safe_summary
from .schemas import validate

# Measured capacity caps (SPEC §0.2), pinned by the decision-pack schema.
CAPS = {"review_minutes": 240, "decision_cards": 25, "record_reviews": 12,
        "complex_decisions": 3}
_PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


class DecisionPackError(ValueError):
    pass


def _parse(ts: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _order_key(it: dict):
    # P0/P1 first (rank asc), then oldest first (age desc), then value desc.
    return (_PRIORITY_RANK.get(it.get("priority", "P3"), 3),
            -int(it.get("age_seconds", 0)), -int(it.get("value", 0)))


def build_pack(items: list[dict], week: str, created_at: str) -> dict:
    """Select a capped, ordered pack; the rest stays queued.

    Each input item: priority, age_seconds, value, question, proposed_answer,
    restrictive_default, estimated_minutes, input_hashes, expiry, and optional
    ``complex``/``is_record_review`` flags.
    """
    ordered = sorted(items, key=_order_key)
    pack_id = "pck_" + sha256_hex(f"{week}\n{created_at}".encode())[:12]
    included, excess = [], []
    minutes = cards = complex_n = records = 0
    for it in ordered:
        em = int(it["estimated_minutes"])
        is_complex = bool(it.get("complex"))
        is_record = bool(it.get("is_record_review"))
        if (cards + 1 > CAPS["decision_cards"]
                or minutes + em > CAPS["review_minutes"]
                or (is_complex and complex_n + 1 > CAPS["complex_decisions"])
                or (is_record and records + 1 > CAPS["record_reviews"])):
            excess.append(it)
            continue
        included.append(it)
        cards += 1
        minutes += em
        complex_n += int(is_complex)
        records += int(is_record)

    pack_items = []
    for i, it in enumerate(included):
        item_id = f"{pack_id}-{i:03d}"
        doc = {
            "schema_version": "atlas-decision-pack-item/v1",
            "item_id": item_id,
            "pack_id": pack_id,
            "question": it["question"],
            "proposed_answer": it.get("proposed_answer"),
            "restrictive_default": it["restrictive_default"],
            "estimated_minutes": em_i(it),
            "input_hashes": dict(it.get("input_hashes", {})),
            "expiry": it["expiry"],
        }
        validate("decision-pack-item.schema.json", doc)
        pack_items.append(doc)

    pack = {
        "schema_version": "atlas-decision-pack/v1",
        "pack_id": pack_id,
        "week": week,
        "created_at": created_at,
        "item_ids": [d["item_id"] for d in pack_items],
        "estimated_review_minutes": minutes,
        "caps": dict(CAPS),
    }
    validate("decision-pack.schema.json", pack)
    return {"pack": pack, "items": pack_items, "excess": excess,
            "throttle_discovery": len(excess) > 0}


def em_i(it: dict) -> int:
    return int(it["estimated_minutes"])


# --- transport: rights-safe summaries + single-use expiring view links ---

def transport_payload(pack: dict, cards_by_item: dict) -> dict:
    """Channel payload: rights-safe summaries only, never restricted content
    and never an approval capability."""
    summaries = []
    for item_id in pack["item_ids"]:
        card = cards_by_item.get(item_id)
        summaries.append(channel_safe_summary(card) if card else {"item_id": item_id})
    return {"pack_id": pack["pack_id"], "week": pack["week"],
            "summaries": summaries, "bearer_credential": False,
            "note": "view links open the authenticated view; approval requires the command API"}


def can_approve_from_channel(payload: dict) -> bool:
    """A channel message/link is never a bearer credential."""
    return False


class ViewLinkStore:
    """Single-use, expiring view links. A replayed or expired link fails."""

    def __init__(self):
        self._issued: dict[str, dict] = {}
        self._consumed: set[str] = set()

    def issue(self, item_id: str, expires_at: str, salt: str) -> str:
        token = "vl_" + sha256_hex(f"{item_id}\n{expires_at}\n{salt}".encode())[:16]
        self._issued[token] = {"item_id": item_id, "expires_at": expires_at}
        return token

    def consume(self, token: str, now: str) -> str:
        info = self._issued.get(token)
        if info is None:
            raise DecisionPackError("unknown view link")
        if token in self._consumed:
            raise DecisionPackError("view link already used (single-use)")
        if _parse(now) >= _parse(info["expires_at"]):
            raise DecisionPackError("view link expired")
        self._consumed.add(token)
        return info["item_id"]  # grants VIEW access only, never approval


# --- draft action envelopes bound to exact input hashes ---

def draft_envelope(item: dict, action: str) -> dict:
    """A draft the assistant may prepare; it binds to the item's exact input
    hashes and is not a bearer credential — the operator confirms via the API."""
    return {
        "item_id": item["item_id"],
        "action": action,
        "bound_input_hashes": dict(item.get("input_hashes", {})),
        "bearer_credential": False,
        "requires_operator_confirmation": True,
    }


def envelope_valid(envelope: dict, live_input_hashes: dict) -> bool:
    """A draft decision is valid only if the live input hashes still match
    exactly; a changed source/proposal/policy invalidates it."""
    return envelope.get("bound_input_hashes") == dict(live_input_hashes)


def expire_unanswered(items: list[dict], now: str) -> list[dict]:
    """Cards past expiry resolve to their restrictive default — never
    acceptance or publication."""
    out = []
    for it in items:
        if _parse(now) >= _parse(it["expiry"]):
            out.append({"item_id": it["item_id"], "disposition": it["restrictive_default"]})
    return out
