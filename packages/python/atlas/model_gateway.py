"""Provider-neutral runtime-model gateway (AI-001).

Single choke point for every runtime-model call. It is provider-neutral
(providers/snapshots come from ``config/model-gateway/gateway.yaml``),
**fail-closed**, and emits a full provenance receipt for each successful
call. Building and fixture-testing the gateway is A0; making a real call on
a real document is A2 and stays gated per run (``activated: false`` in
config, and the default transport refuses).

Guarantees (SPEC §9 AI-001 acceptance):

- **Exact snapshots only.** Aliases (``latest``/``newest``/``stable``/
  ``current``/``default`` and any ``*-latest`` form) are rejected; the
  model id must also be in the config allowlist.
- **Full receipt.** Each successful call yields a ``ModelRunReceipt`` with
  source/text hashes, prompt/params/rubric versions, the exact model, the
  code commit, the rights-decision ids, the no-tool proof, held-out
  isolation, token cost, attempts and run id.
- **Retry once, then one idempotent review item.** Invalid output retries
  at most once (retriable), then a single deterministic ``ReviewTask`` is
  created; the id is stable across re-runs, so retries never duplicate it.
- **Outage queues, never corrupts.** A model outage returns an idempotent
  ``JobEnvelope`` and writes nothing; state cannot be half-written and
  nothing is published.
- **No accepted writes.** A model run is always ``output_tier: proposal``;
  the gateway never touches an accepted table.
- **Separate from the harness; no tools, no ambient credentials.** The
  transport receives only (provider, model_id, prompt, params, timeout).
  Requests carrying tool/function/control-channel fields are rejected; a
  transport that reports any offered tool, tool call, or exposed credential
  fails the run. Over-limit payloads fail closed.
- **Inert source text.** Legitimate URLs, command-like phrases and hostile
  instructions inside permitted source-text fields are never scanned,
  blanket-rejected, or executed — only the *structure* of the request is
  policed.
- **Rights pre-call gate.** No subject is sent to a model without a
  non-expired ``RightsDecision`` on the ``third_party_model_processing``
  axis whose outcome permits processing; otherwise the run fails closed.

Deterministic given injected clock/run-id/transport; pure otherwise.
"""
import decimal
import pathlib
import re
import typing

import yaml

from .canonical import canonical_json_bytes, obj_sha256, sha256_hex
from .schemas import validate

ROOT = pathlib.Path(__file__).resolve().parents[3]
CONFIG_PATH = ROOT / "config" / "model-gateway" / "gateway.yaml"

# Alias tokens forbidden in a runtime model id (SPEC 0.1.16 / 5).
ALIAS_TOKENS = frozenset(
    {"latest", "newest", "stable", "current", "default", "preview", "auto"})
_SEGMENT = re.compile(r"[^a-z0-9]+")

# The pre-call gate requires a rights decision on this axis.
RIGHTS_AXIS = "third_party_model_processing"
# Outcomes on that axis that permit sending the subject to a third-party
# model. Everything else (pending/prohibited/withdrawn/metadata-only) fails
# closed: metadata-only does not clear sending source text.
ACCEPTABLE_RIGHTS_OUTCOMES = frozenset(
    {"cleared_public", "cleared_licensee", "internal_only"})

ALLOWED_ROLES = frozenset({"system", "user"})
# Top-level request keys the gateway understands. Anything else is rejected
# (control-channel / tool-addressing attempts fail).
ALLOWED_REQUEST_KEYS = frozenset({
    "stage", "provider", "model_id", "prompt", "params", "output_schema",
    "subject_refs", "input_hashes", "prompt_version", "rubric_version",
    "pack_id", "partition_id",
})
# Keys that are never acceptable anywhere in a request payload.
FORBIDDEN_KEYS = frozenset({
    "tools", "functions", "tool", "tool_choice", "tool_calls", "system_tools",
    "function_call", "credentials", "api_key", "apikey", "secret", "token",
    "authorization",
})


class GatewayError(Exception):
    """Base for every fail-closed gateway refusal."""


class ConfigError(GatewayError):
    pass


class GatewayNotActivated(GatewayError):
    pass


class AliasForbidden(GatewayError):
    pass


class SnapshotNotApproved(GatewayError):
    pass


class ProviderNotApproved(GatewayError):
    pass


class RightsGateFailed(GatewayError):
    pass


class BudgetExceeded(GatewayError):
    pass


class PayloadRejected(GatewayError):
    pass


class ToolLeak(GatewayError):
    pass


class ModelOutage(GatewayError):
    """Raised by a transport when the provider is unavailable.

    The gateway catches it and returns an idempotent queued job.
    """


class OutputInvalid(GatewayError):
    """Structured output failed schema validation (retriable once)."""


class RawOutput(typing.NamedTuple):
    structured: dict
    input_tokens: int
    output_tokens: int
    cost_usd: str
    tools_offered: int = 0
    tool_calls_observed: int = 0
    ambient_credentials_exposed: bool = False


class Transport(typing.Protocol):
    def generate(self, *, provider: str, model_id: str, prompt: dict,
                 params: dict, timeout_s) -> RawOutput:
        ...


class FailClosedTransport:
    """Default transport: refuses every call. A real transport must be
    injected explicitly, which only happens inside the A2 pilot env."""

    def generate(self, **_kwargs) -> RawOutput:
        raise GatewayNotActivated(
            "no runtime transport is wired; real model calls require A2 "
            "activation in the isolated pilot environment")


class RightsProvider(typing.Protocol):
    def decision_for(self, subject_ref: dict, axis: str) -> dict | None:
        ...


def _is_alias(model_id: str) -> bool:
    if not model_id or not model_id.strip():
        return True
    lo = model_id.lower()
    if any(seg in ALIAS_TOKENS for seg in _SEGMENT.split(lo) if seg):
        return True
    return lo.endswith("-latest") or lo.endswith(".latest")


def load_config(path: pathlib.Path | None = None) -> dict:
    doc = yaml.safe_load((path or CONFIG_PATH).read_text())
    if not isinstance(doc, dict) or doc.get("schema_version") != "atlas-gateway-config/v1":
        raise ConfigError("gateway config missing/invalid schema_version")
    return doc


def config_hash(config: dict) -> str:
    return obj_sha256(config)


def _scan_forbidden(obj, where: str = "request") -> None:
    """Reject tool/credential/control keys anywhere in the structure.

    Note this walks *keys* only. String *values* (source text) are never
    inspected — hostile instructions there stay inert data."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in FORBIDDEN_KEYS:
                raise PayloadRejected(f"forbidden key {k!r} in {where}")
            _scan_forbidden(v, where)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _scan_forbidden(v, where)


def _validate_prompt(prompt) -> None:
    if not isinstance(prompt, dict) or set(prompt) != {"messages"}:
        raise PayloadRejected("prompt must be {'messages': [...]}")
    msgs = prompt["messages"]
    if not isinstance(msgs, list) or not msgs:
        raise PayloadRejected("prompt.messages must be a non-empty list")
    for m in msgs:
        if not isinstance(m, dict) or set(m) != {"role", "content"}:
            # extra keys in a message = tool-addressing attempt
            raise PayloadRejected("each message must be exactly {role, content}")
        if m["role"] not in ALLOWED_ROLES:
            raise PayloadRejected(
                f"role {m['role']!r} not allowed (no tool/function/assistant channels)")
        if not isinstance(m["content"], str):
            raise PayloadRejected("message content must be a string")


def _dec(x) -> decimal.Decimal:
    return decimal.Decimal(str(x))


class BudgetLedger:
    """In-memory spend ledger with fail-closed caps. Caps are Decimal
    strings from config; a null cap fails closed."""

    def __init__(self, budgets: dict):
        self._per_call = self._cap(budgets.get("per_call_usd_cap"))
        self._per_pack = self._cap(budgets.get("per_pack_usd_cap"))
        self._per_day = self._cap(budgets.get("per_day_usd_cap"))
        self.currency = budgets.get("currency", "USD")
        self._day_spent: dict[str, decimal.Decimal] = {}
        self._pack_spent: dict[str, decimal.Decimal] = {}

    @staticmethod
    def _cap(v):
        return None if v is None else _dec(v)

    def check_before(self, day: str, pack_id: str | None) -> None:
        if self._per_call is None or self._per_day is None or self._per_pack is None:
            raise BudgetExceeded("budget cap unset; fail closed")
        day_s = self._day_spent.get(day, decimal.Decimal(0))
        if day_s + self._per_call > self._per_day:
            raise BudgetExceeded(f"per-day cap would be exceeded ({day})")
        if pack_id is not None:
            pack_s = self._pack_spent.get(pack_id, decimal.Decimal(0))
            if pack_s + self._per_call > self._per_pack:
                raise BudgetExceeded(f"per-pack cap would be exceeded ({pack_id})")

    def record(self, day: str, pack_id: str | None, cost_usd: str) -> None:
        cost = _dec(cost_usd)
        if self._per_call is not None and cost > self._per_call:
            raise BudgetExceeded("actual cost exceeded per-call cap")
        self._day_spent[day] = self._day_spent.get(day, decimal.Decimal(0)) + cost
        if pack_id is not None:
            self._pack_spent[pack_id] = self._pack_spent.get(
                pack_id, decimal.Decimal(0)) + cost


def _short(digest: str) -> str:
    return digest[:12]


class ModelGateway:
    def __init__(self, config: dict, *, transport: Transport | None = None,
                 rights: RightsProvider | None = None,
                 code_commit: str = "uncommitted",
                 clock: typing.Callable[[], str] | None = None,
                 run_id_fn: typing.Callable[[], str] | None = None):
        self.config = config
        self.transport = transport or FailClosedTransport()
        self.rights = rights
        self.code_commit = code_commit
        self._clock = clock or (lambda: "1970-01-01T00:00:00Z")
        self._n = 0
        self._run_id_fn = run_id_fn or self._auto_run_id
        self.ledger = BudgetLedger(config.get("budgets", {}))
        self.config_hash = config_hash(config)

    def _auto_run_id(self) -> str:
        self._n += 1
        return f"run-{self._n}"

    # --- pre-call gates ---------------------------------------------------
    def _check_activation(self) -> None:
        if not self.config.get("activated"):
            raise GatewayNotActivated(
                "gateway config activated=false; real calls require A2 activation")

    def _check_model(self, provider: str, model_id: str) -> None:
        if _is_alias(model_id):
            raise AliasForbidden(f"alias-like model id rejected: {model_id!r}")
        approved = self.config.get("approved_snapshots") or []
        if model_id not in approved:
            raise SnapshotNotApproved(f"{model_id!r} not in approved_snapshots")
        providers = {p.get("id") for p in (self.config.get("approved_providers") or [])}
        if provider not in providers:
            raise ProviderNotApproved(f"{provider!r} not an approved provider")

    def _check_rights(self, subject_refs: list) -> list[str]:
        if self.rights is None:
            raise RightsGateFailed("no rights provider wired; fail closed")
        ids: list[str] = []
        for ref in subject_refs:
            dec = self.rights.decision_for(ref, RIGHTS_AXIS)
            if dec is None:
                raise RightsGateFailed(f"no rights decision for {ref} on {RIGHTS_AXIS}")
            validate("rights-decision.schema.json", dec)
            if dec["axis"] != RIGHTS_AXIS:
                raise RightsGateFailed("rights decision axis mismatch")
            if dec["outcome"] not in ACCEPTABLE_RIGHTS_OUTCOMES:
                raise RightsGateFailed(
                    f"rights outcome {dec['outcome']!r} does not permit processing")
            exp = dec.get("expiry")
            if exp is not None and exp <= self._clock():
                raise RightsGateFailed("rights decision expired")
            ids.append(dec["rights_decision_id"])
        return ids

    # --- request validation ----------------------------------------------
    def _validate_request(self, req: dict) -> None:
        if not isinstance(req, dict):
            raise PayloadRejected("request must be an object")
        unknown = set(req) - ALLOWED_REQUEST_KEYS
        if unknown:
            raise PayloadRejected(f"unknown request keys: {sorted(unknown)}")
        for k in ("stage", "provider", "model_id", "output_schema"):
            if not isinstance(req.get(k), str) or not req[k]:
                raise PayloadRejected(f"missing/invalid {k}")
        if not isinstance(req.get("params"), dict):
            raise PayloadRejected("params must be an object")
        ih = req.get("input_hashes")
        if not isinstance(ih, dict) or not ih:
            raise PayloadRejected("input_hashes must be a non-empty object")
        for name, h in ih.items():
            if not (isinstance(h, str) and re.fullmatch(r"[0-9a-f]{64}", h)):
                raise PayloadRejected(f"input hash {name} is not sha256 hex")
        refs = req.get("subject_refs")
        if not isinstance(refs, list) or not refs:
            raise PayloadRejected("subject_refs must be a non-empty list")
        _scan_forbidden(req)
        _validate_prompt(req.get("prompt"))
        # payload size ceiling
        limit = self.config.get("max_request_bytes")
        size = len(canonical_json_bytes({"prompt": req["prompt"], "params": req["params"]}))
        if limit is not None and size > limit:
            raise PayloadRejected(f"request payload {size}B over limit {limit}B")

    # --- idempotency keys -------------------------------------------------
    def _idem_digest(self, req: dict) -> str:
        return obj_sha256({
            "stage": req["stage"], "model_id": req["model_id"],
            "input_hashes": req["input_hashes"],
            "prompt_hash": sha256_hex(canonical_json_bytes(req["prompt"])),
            "output_schema": req["output_schema"],
        })

    def _queued_job(self, req: dict, digest: str) -> dict:
        job = {
            "schema_version": "atlas-job-envelope/v1",
            "run_id": self._run_id_fn(),
            "correlation_id": "mgw_" + _short(digest),
            "idempotency_key": "mgw_outage_" + _short(digest),
            "kind": "model_run_retry",
            "input_hashes": dict(req["input_hashes"]),
            "code_commit": self.code_commit,
            "config_hashes": {"gateway": self.config_hash},
            "created_at": self._clock(),
            "payload": {"stage": req["stage"], "reason": "model_outage"},
        }
        validate("job-envelope.schema.json", job)
        return job

    def _review_task(self, req: dict, digest: str) -> dict:
        task = {
            "schema_version": "atlas-review-task/v1",
            "task_id": "rvt_" + _short(digest),
            "queue": "quarantine",
            "priority": "P2",
            "question": (f"Runtime model produced invalid structured output for "
                         f"stage {req['stage']!r} after one retry; human review needed."),
            "restrictive_default": "hold",
            "created_at": self._clock(),
            "expiry": self._clock(),
            "input_hashes": dict(req["input_hashes"]),
        }
        validate("review-task.schema.json", task)
        return task

    def _build_receipt(self, req: dict, raw: RawOutput, attempts: int,
                       rights_ids: list[str], started: str, finished: str) -> dict:
        prompt_hash = sha256_hex(canonical_json_bytes(req["prompt"]))
        params_hash = sha256_hex(canonical_json_bytes(req["params"]))
        output_hash = obj_sha256(raw.structured)
        digest = obj_sha256({"ph": prompt_hash, "oh": output_hash,
                             "ih": req["input_hashes"], "st": req["stage"]})
        receipt = {
            "schema_version": "atlas-model-run-receipt/v1",
            "receipt_id": "mrr_" + _short(digest),
            "run_id": self._run_id_fn(),
            "stage": req["stage"],
            "output_tier": "proposal",
            "provider": req["provider"],
            "model_id": req["model_id"],
            "input_hashes": dict(req["input_hashes"]),
            "prompt_hash": prompt_hash,
            "params_hash": params_hash,
            "prompt_version": req.get("prompt_version"),
            "rubric_version": req.get("rubric_version"),
            "code_commit": self.code_commit,
            "rights_decision_ids": rights_ids,
            "no_tool_proof": {
                "tools_offered": 0,
                "tool_calls_observed": 0,
                "ambient_credentials_exposed": False,
            },
            "held_out_isolation": {"held_out_readable": False},
            "token_cost": {
                "input_tokens": raw.input_tokens,
                "output_tokens": raw.output_tokens,
                "cost_usd": raw.cost_usd,
                "currency": self.ledger.currency,
            },
            "attempts": attempts,
            "started_at": started,
            "finished_at": finished,
            "output_hash": output_hash,
        }
        pid = req.get("partition_id")
        if pid is not None:
            receipt["held_out_isolation"]["partition_id"] = pid
        validate("model-run-receipt.schema.json", receipt)
        return receipt

    def _assert_no_tools(self, raw: RawOutput) -> None:
        if (raw.tools_offered or raw.tool_calls_observed
                or raw.ambient_credentials_exposed):
            raise ToolLeak(
                "transport reported tools/tool-calls/ambient credentials; "
                "runtime model calls must receive none")

    # --- public entry point ----------------------------------------------
    def run(self, request: dict) -> dict:
        """Execute one runtime-model call through every gate.

        Returns one of:
          {"status": "ok", "receipt": ..., "output": ...}
          {"status": "queued", "job": ...}          (model outage)
          {"status": "review", "review_task": ..., "attempts": 2}
        Raises GatewayError (fail closed) for every policy refusal.
        """
        self._validate_request(request)
        self._check_activation()
        self._check_model(request["provider"], request["model_id"])
        rights_ids = self._check_rights(request["subject_refs"])
        pack_id = request.get("pack_id")
        started = self._clock()
        day = started[:10]
        self.ledger.check_before(day, pack_id)

        digest = self._idem_digest(request)
        attempts = 0
        last_err: Exception | None = None
        raw: RawOutput | None = None
        while attempts < self.config["budgets"]["max_retries"] + 1:
            attempts += 1
            try:
                raw = self.transport.generate(
                    provider=request["provider"], model_id=request["model_id"],
                    prompt=request["prompt"], params=request["params"],
                    timeout_s=self.config["budgets"].get("timeout_s"))
            except ModelOutage:
                # outage: queue idempotently, write nothing, publish nothing
                return {"status": "queued", "job": self._queued_job(request, digest)}
            self._assert_no_tools(raw)
            try:
                validate(request["output_schema"], raw.structured)
                break
            except Exception as e:  # schema-invalid output is retriable once
                last_err = e
                raw = None
                continue
        if raw is None:
            # exhausted retries with invalid output -> one idempotent review item
            return {"status": "review",
                    "review_task": self._review_task(request, digest),
                    "attempts": attempts, "last_error": str(last_err)}

        self.ledger.record(day, pack_id, raw.cost_usd)
        finished = self._clock()
        receipt = self._build_receipt(request, raw, attempts, rights_ids,
                                      started, finished)
        return {"status": "ok", "receipt": receipt, "output": raw.structured}
