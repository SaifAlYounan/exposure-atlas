"""Manual no-AI vertical slice orchestration (VER-002).

fetch(fixture) -> canonicalize -> assert -> verify -> approve -> project
-> release. State lives in an in-memory Kernel plus the evidence store;
full PostgreSQL persistence is DOM-002/DOM-003 scope in a later G1
session. Every state change appends a hash-chained audit event.
"""
import pathlib
import secrets

from .anchors import create_anchor
from .audit import append_event
from .canonical import sha256_hex
from .documents import CANONICALIZER_VERSION, html_to_canonical, pdf_to_canonical
from .fetchguard import bounded_bytes, check_mime, validate_url
from .policy import evaluate
from .schemas import validate
from .store import EvidenceStore
from .verify import report_sha256, verify_proposal


def _oid(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(6)}"


class UnsupportedLanguageError(ValueError):
    """DOC-003 pilot exclusion: unsupported-language candidates route to
    review/awaiting-capability; no unlabelled translation ever publishes
    (no translation path exists yet)."""


class Kernel:
    def __init__(self, var_dir: pathlib.Path, allowed_hosts: list[str],
                 supported_languages: tuple[str, ...] = ("en",)):
        self.supported_languages = supported_languages
        self.var = pathlib.Path(var_dir)
        self.store = EvidenceStore(self.var / "evidence")
        self.audit_path = self.var / "audit.jsonl"
        self.allowed_hosts = allowed_hosts
        self.source_documents: dict[str, dict] = {}
        self.source_versions: dict[str, dict] = {}
        self.acquisitions: list[dict] = []
        self.text_artifacts: dict[str, dict] = {}
        self.canonical_texts: dict[str, bytes] = {}
        self.anchors: dict[str, dict] = {}
        self.proposals: dict[str, dict] = {}
        self.reports: dict[str, dict] = {}
        self.decisions: dict[str, dict] = {}
        self.assertions: dict[str, dict] = {}

    def _audit(self, action: str, at: str, detail: dict):
        append_event(self.audit_path, "builder-kernel", action, at, detail)

    # -- acquisition (fixture adapter mode; live fetching needs A1) ----
    def ingest_fixture(self, path: pathlib.Path, *, declared_url: str,
                       declared_mime: str, issuer: str, title: str,
                       document_role: str, source_id: str,
                       copy_provenance_state: str, retrieved_at: str,
                       docket: str | None = None,
                       language: str = "en") -> tuple[dict, dict]:
        if language not in self.supported_languages:
            raise UnsupportedLanguageError(
                f"language {language!r} outside pilot boundary; route to "
                "awaiting_capability (DOC-003)")
        validate_url(declared_url, self.allowed_hosts)
        data = bounded_bytes(pathlib.Path(path).read_bytes())
        check_mime(declared_mime, data)
        digest = self.store.put(data)
        sdoc = {"schema_version": "atlas-source-document/v1",
                "source_document_id": _oid("sdoc"), "issuer": issuer,
                "document_role": document_role, "title": title,
                "source_id": source_id}
        if docket:
            sdoc["docket"] = docket
        validate("source-document.schema.json", sdoc)
        sver = {"schema_version": "atlas-source-version/v1",
                "source_version_id": _oid("sver"),
                "source_document_id": sdoc["source_document_id"],
                "content_sha256": digest, "mime_type": declared_mime,
                "size_bytes": len(data),
                "copy_provenance_state": copy_provenance_state,
                "supersedes": None}
        validate("source-version.schema.json", sver)
        acq = {"schema_version": "atlas-acquisition-receipt/v1",
               "acquisition_id": _oid("acq"),
               "source_version_id": sver["source_version_id"],
               "requested_url": declared_url, "final_url": declared_url,
               "redirect_chain": [], "retrieved_at": retrieved_at,
               "adapter": source_id, "adapter_mode": "fixture",
               "content_sha256": digest}
        validate("acquisition-receipt.schema.json", acq)
        self.source_documents[sdoc["source_document_id"]] = sdoc
        self.source_versions[sver["source_version_id"]] = sver
        self.acquisitions.append(acq)
        self._audit("ingest_fixture", retrieved_at,
                    {"source_version_id": sver["source_version_id"],
                     "sha256": digest})
        return sdoc, sver

    def canonicalize(self, source_version_id: str, at: str) -> dict:
        sver = self.source_versions[source_version_id]
        data = self.store.get(sver["content_sha256"])
        if sver["mime_type"] == "text/html":
            text, page_map, extractor = html_to_canonical(data), [], "stdlib-html/1"
        elif sver["mime_type"] == "application/pdf":
            text, page_map = pdf_to_canonical(data)
            extractor = "pymupdf/1.24.10"
        else:
            raise ValueError(f"no canonicalizer for {sver['mime_type']}")
        digest = self.store.put(text)
        artifact = {"schema_version": "atlas-text-artifact/v1",
                    "text_artifact_id": _oid("txt"),
                    "source_version_id": source_version_id,
                    "canonical_sha256": sha256_hex(text),
                    "canonicalizer_version": CANONICALIZER_VERSION,
                    "extractor": extractor, "anchor_basis": "native_text",
                    "language": "en", "page_map": page_map}
        validate("text-artifact.schema.json", artifact)
        self.text_artifacts[artifact["text_artifact_id"]] = artifact
        self.canonical_texts[artifact["text_artifact_id"]] = text
        self._audit("canonicalize", at,
                    {"text_artifact_id": artifact["text_artifact_id"],
                     "canonical_sha256": artifact["canonical_sha256"],
                     "stored": digest})
        return artifact

    def add_anchor(self, text_artifact_id: str, quote: str,
                   occurrence: int | None = None) -> dict:
        anc = create_anchor(self.canonical_texts[text_artifact_id], quote,
                            anchor_id=_oid("anc"),
                            text_artifact_id=text_artifact_id,
                            occurrence=occurrence)
        validate("anchor.schema.json", anc)
        self.anchors[anc["anchor_id"]] = anc
        return anc

    def propose(self, *, source_version_id: str, subject_ref: dict,
                predicate: str, raw_value: str, modality: str,
                value_origin: str, support: list[dict], observed_at: str,
                normalized_value=None, transform=None) -> dict:
        prop = {"schema_version": "atlas-assertion-proposal/v1",
                "proposal_id": _oid("prop"),
                "source_version_id": source_version_id,
                "subject_ref": subject_ref, "predicate": predicate,
                "raw_value": raw_value, "value_status": "stated",
                "procedural_modality": modality, "value_origin": value_origin,
                "support": support, "observed_at": observed_at,
                "proposed_by": "manual",
                "normalized_value": normalized_value, "transform": transform}
        validate("assertion-proposal.schema.json", prop)
        self.proposals[prop["proposal_id"]] = prop
        self._audit("propose", observed_at, {"proposal_id": prop["proposal_id"]})
        return prop

    def verify(self, proposal_id: str) -> dict:
        prop = self.proposals[proposal_id]
        sver = self.source_versions[prop["source_version_id"]]
        sdoc = self.source_documents[sver["source_document_id"]]
        artifact = next(a for a in self.text_artifacts.values()
                        if a["source_version_id"] == sver["source_version_id"])
        text = self.canonical_texts[artifact["text_artifact_id"]]
        report = verify_proposal(
            prop, source_document=sdoc, source_version=sver,
            text_artifact=artifact, canonical_text=text,
            text_sha256=sha256_hex(text), anchors_by_id=self.anchors,
            report_id=_oid("vrp"))
        self.reports[proposal_id] = report
        return report

    def approve(self, proposal_id: str, *, reason: str, decided_at: str,
                decision: str = "accept") -> dict:
        """Operator semantic decision (Alexios). The builder may only
        call this replaying a recorded operator decision envelope."""
        report = self.reports.get(proposal_id)
        if report is None:
            raise RuntimeError("verification must run before a decision")
        if report["overall"] != "pass" and decision == "accept":
            raise RuntimeError("cannot accept a proposal whose mechanical checks fail")
        dec = {"schema_version": "atlas-assertion-acceptance/v1",
               "decision_id": _oid("dec"), "proposal_id": proposal_id,
               "decided_by": "Alexios", "role": "operator_reviewer",
               "decision": decision, "reason": reason, "decided_at": decided_at,
               "validation_report_sha256": report_sha256(report)}
        validate("assertion-acceptance-decision.schema.json", dec)
        self.decisions[dec["decision_id"]] = dec
        self._audit("acceptance_decision", decided_at,
                    {"decision_id": dec["decision_id"], "decision": decision})
        if decision != "accept":
            return dec
        prop = self.proposals[proposal_id]
        assertion = {"schema_version": "atlas-assertion/v1",
                     "assertion_id": _oid("ast"),
                     "proposal_id": proposal_id,
                     "acceptance_decision_id": dec["decision_id"],
                     "source_version_id": prop["source_version_id"],
                     "subject_ref": prop["subject_ref"],
                     "predicate": prop["predicate"],
                     "raw_value": prop["raw_value"],
                     "value_status": prop["value_status"],
                     "procedural_modality": prop["procedural_modality"],
                     "value_origin": prop["value_origin"],
                     "support": prop["support"],
                     "normalized_value": prop.get("normalized_value"),
                     "transform": prop.get("transform"),
                     "mechanical_verification_state": "passed",
                     "semantic_review_state": "human_approved",
                     "observed_at": prop["observed_at"]}
        validate("assertion.schema.json", assertion)
        self.assertions[assertion["assertion_id"]] = assertion
        return assertion

    def policy_check(self, assertion_id: str, at: str, *,
                     effective_distribution_decision: str,
                     suppression_denied: bool = False,
                     boundary_version: str = "1.0.0") -> dict:
        a = self.assertions[assertion_id]
        report = self.reports[a["proposal_id"]]
        return evaluate(validation_report=report,
                        semantic_review_state=a["semantic_review_state"],
                        effective_distribution_decision=effective_distribution_decision,
                        suppression_denied=suppression_denied,
                        operation="publish_public", evaluated_at=at,
                        boundary_version=boundary_version)
