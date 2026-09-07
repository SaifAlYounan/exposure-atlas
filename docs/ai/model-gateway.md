# Provider-neutral runtime-model gateway (AI-001)

The single choke point for every runtime-model call. Engine:
`packages/python/atlas/model_gateway.py`; config:
`config/model-gateway/gateway.yaml`; receipt schema:
`schemas/domain/model-run-receipt.schema.json`.

**Authorization.** Building and fixture-testing the gateway is A0 (no
network, no credentials, no real model calls). Making a real call on a real
document is **A2** and stays gated per run: the shipped config has
`activated: false`, the default transport refuses, and no snapshot is
approved. Activation is a reviewed commit the operator makes after wiring
the runtime model (D-031).

## What every call passes through, in order

1. **Request structure** — only known top-level keys are accepted; any
   `tools`/`functions`/`tool_choice`/`tool_calls`/credential key anywhere in
   the payload is rejected; the prompt must be `{"messages":[{role,content}]}`
   with `role ∈ {system,user}` only; over-limit payloads fail closed. String
   *values* (source text) are never scanned — a URL, a command-like phrase or
   a hostile instruction inside a permitted field stays inert data.
2. **Activation** — `activated:false` ⇒ `GatewayNotActivated`.
3. **Exact snapshot** — alias-like ids (`latest`/`newest`/`stable`/
   `current`/`default`/`*-latest`…) are rejected, and the id must be in
   `approved_snapshots`; the provider must be in `approved_providers`.
4. **Rights pre-call gate** — each `subject_ref` needs a non-expired
   `RightsDecision` on the `third_party_model_processing` axis whose outcome
   permits processing (`cleared_public`/`cleared_licensee`/`internal_only`).
   Missing/pending/prohibited/withdrawn/metadata-only ⇒ fail closed.
5. **Budget** — per-call/per-pack/per-day caps; a null cap fails closed; the
   pre-call check reserves the per-call cap against the day/pack remaining and
   the actual cost is re-checked against the per-call cap before it is
   recorded.

## Execution, retry, outage

- The **transport** (injected; provider-specific) receives only
  `(provider, model_id, prompt, params, timeout_s)` — no tools, no ambient
  credentials. A transport that reports any offered tool, tool call or
  exposed credential fails the run (`ToolLeak`).
- **Invalid structured output** retries **at most once** (schema-invalid is
  retriable), then creates **one idempotent `ReviewTask`** (deterministic id
  from the input hashes/stage/model — retries never duplicate it).
- **Model outage** returns an idempotent `JobEnvelope`
  (`kind: model_run_retry`) and writes/publishes nothing; state is never
  half-written.
- **Success** yields a `ModelRunReceipt` (`output_tier: proposal`) and the
  parsed output. A model run is always proposal-tier — **it can never write
  an accepted table**, and model agreement never satisfies a G2 decision.

## Receipt provenance (SPEC §11.9)

Each successful call records: source/text `input_hashes`, `prompt_hash`,
`params_hash`, `prompt_version`/`rubric_version`, exact `provider`/`model_id`,
`code_commit`, `run_id`, `rights_decision_ids`, a `no_tool_proof`
(0 tools / 0 tool-calls / no ambient credentials), `held_out_isolation`
(`held_out_readable:false`), `token_cost` (cost as a decimal string, never a
float) and `attempts`.

## Guarantees → SPEC §9 AI-001 acceptance

- Full provenance receipt — `test_successful_run_emits_full_receipt`,
  `test_receipt_hashes_are_deterministic`.
- Retry once then one idempotent review item —
  `test_invalid_output_retries_once_then_review_item`,
  `test_review_item_is_idempotent`, `test_valid_after_one_retry_records_two_attempts`.
- Outage queues without corrupting state or publishing —
  `test_model_outage_queues_idempotently_without_publishing`.
- Models cannot write accepted tables — `test_models_cannot_write_accepted_tables`.
- Separate from the harness; no tools/ambient credentials —
  `test_tool_leak_from_transport_fails_run`, `test_default_transport_refuses`.
- Rights pre-call gate — `test_rights_gate_blocks_*`, `test_rights_cleared_public_permitted`.
- Unexpected keys / tool-addressing / over-limit fail; hostile source text
  stays inert — `test_unknown_top_level_key_rejected`,
  `test_tool_addressing_keys_rejected`, `test_tool_role_message_rejected`,
  `test_extra_message_key_rejected`, `test_over_limit_payload_rejected`,
  `test_hostile_source_text_stays_inert`.
- Exact snapshots only — `test_alias_model_ids_rejected`,
  `test_snapshot_not_in_allowlist_rejected`, `test_provider_not_approved_rejected`.
- Fail-closed config/budgets — `test_shipped_config_is_fail_closed`,
  `test_budget_unset_fails_closed`, `test_per_day_cap_enforced`.

## Activation checklist (operator, at A2)

Fill `config/model-gateway/gateway.yaml` and flip `activated: true` in a
reviewed commit once all four hold:

1. `approved_providers[]` (id + `api_style`/region/retention) and the exact
   `approved_snapshots` id(s) for the K2 Horizon runtime (no aliases).
2. `budgets.*` spend caps and `timeout_s`.
3. the provider API key provisioned as an operator-held protected-environment
   secret (as with `CL_API_TOKEN`) — never in config or chat.
4. data-handling (retention / no-training) confirmed per provider.

Until then the gateway is inert by construction. AI-002 (registries),
AI-003 (long-document planner), TRIAGE-002, EXT-001/002, CLASS-001 and
ROUTE-001 build on this gateway.
