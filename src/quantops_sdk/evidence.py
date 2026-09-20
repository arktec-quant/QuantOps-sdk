"""Strict, deterministic QuantOps evidence-bundle admission."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "quantops-evidence-bundle/v2"
LEGACY_SCHEMA_VERSION = "quantops-evidence-bundle/v1"
MAX_BUNDLE_BYTES = 65_536
MAX_TEXT_BYTES = 512
MAX_NOTE_BYTES = 1_024
MAX_SUMMARY_ITEMS = 24
MAX_TABLES = 8
MAX_COLUMNS = 12
MAX_ROWS_PER_TABLE = 100
MAX_PROVENANCE_RECORDS = 16
MAX_ARTIFACT_REFERENCES = 16
ALLOWED_ARTIFACT_EXTENSIONS = {".csv", ".json", ".pdf", ".txt"}
_FORBIDDEN_TEXT = ("<script", "</script", "javascript:", "data:text/html", "<?", "{%", "{{")


class EvidenceRefusal(ValueError):
    """A stable, non-sensitive refusal boundary for untrusted bundle input."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class DisplayValue:
    kind: str
    value: str | float | bool

    def to_mapping(self) -> dict[str, Any]:
        return {"kind": self.kind, "value": self.value}


@dataclass(frozen=True)
class ArtifactReference:
    label: str
    path: str
    sha256: str

    def to_mapping(self) -> dict[str, str]:
        return {"label": self.label, "path": self.path, "sha256": self.sha256}


@dataclass(frozen=True)
class EvidenceBundle:
    schema_version: str
    bundle_id: str
    payload_sha256: str
    provenance: dict[str, Any]
    payload: dict[str, Any]

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "bundle_id": self.bundle_id,
            "payload_sha256": self.payload_sha256,
            "provenance": self.provenance,
            "payload": self.payload,
        }

    def to_json_bytes(self) -> bytes:
        return _compact_json(self.to_mapping())


def _refuse(code: str) -> None:
    raise EvidenceRefusal(code)


def _compact_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


def _strict_json_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _refuse("EVIDENCE_SCHEMA_REFUSED")
        result[key] = value
    return result


def _parse_bytes(data: bytes) -> dict[str, Any]:
    if len(data) > MAX_BUNDLE_BYTES:
        _refuse("EVIDENCE_BUNDLE_SIZE_REFUSED")
    try:
        parsed = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_strict_json_object_pairs,
            parse_constant=lambda _value: _refuse("EVIDENCE_SCHEMA_REFUSED"),
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        _refuse("EVIDENCE_SCHEMA_REFUSED")
    if not isinstance(parsed, dict):
        _refuse("EVIDENCE_SCHEMA_REFUSED")
    return parsed


def _object(value: Any, keys: Sequence[str]) -> Mapping[str, Any]:
    if not isinstance(value, dict) or set(value) != set(keys):
        _refuse("EVIDENCE_SCHEMA_REFUSED")
    return value


def _token(value: Any, limit: int = 96) -> str:
    if not isinstance(value, str) or not value or len(value) > limit:
        _refuse("EVIDENCE_SCHEMA_REFUSED")
    if not all(character.isascii() and (character.isalnum() or character in "._-") for character in value):
        _refuse("EVIDENCE_SCHEMA_REFUSED")
    return value


def _sha256(value: Any) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(character not in "0123456789abcdefABCDEF" for character in value):
        _refuse("EVIDENCE_DIGEST_REFUSED")
    return value


def _display_text(value: Any, limit: int = MAX_TEXT_BYTES) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > limit:
        _refuse("EVIDENCE_CONTENT_REFUSED")
    if any(ord(character) < 32 and character not in "\n\t" for character in value):
        _refuse("EVIDENCE_CONTENT_REFUSED")
    lowered = value.lower()
    if any(needle in lowered for needle in _FORBIDDEN_TEXT):
        _refuse("EVIDENCE_CONTENT_REFUSED")
    return value


def _timestamp(value: Any) -> str:
    if not isinstance(value, str) or len(value) != 20 or not value.endswith("Z"):
        _refuse("EVIDENCE_PROVENANCE_REFUSED")
    separators = {4: "-", 7: "-", 10: "T", 13: ":", 16: ":"}
    if any(value[index] != character for index, character in separators.items()) or not all(
        character.isascii() and character.isdigit() for index, character in enumerate(value) if index not in {4, 7, 10, 13, 16, 19}
    ):
        _refuse("EVIDENCE_PROVENANCE_REFUSED")
    return value


def _artifact_path(value: Any) -> str:
    if not isinstance(value, str) or not value.startswith("artifacts/"):
        _refuse("EVIDENCE_ARTIFACT_REFUSED")
    parts = value.split("/")
    if any(not part or part in {".", ".."} for part in parts) or "\\" in value:
        _refuse("EVIDENCE_ARTIFACT_REFUSED")
    if not any(value.endswith(extension) for extension in ALLOWED_ARTIFACT_EXTENSIONS):
        _refuse("EVIDENCE_ARTIFACT_REFUSED")
    return value


def _display_value(value: Any) -> dict[str, Any]:
    value = _object(value, ("kind", "value"))
    kind = value["kind"]
    raw = value["value"]
    if kind == "text":
        return {"kind": "text", "value": _display_text(raw)}
    if kind == "number" and isinstance(raw, (int, float)) and not isinstance(raw, bool):
        number = float(raw)
        if math.isfinite(number):
            return {"kind": "number", "value": number}
    if kind == "boolean" and isinstance(raw, bool):
        return {"kind": "boolean", "value": raw}
    _refuse("EVIDENCE_CONTENT_REFUSED")


def _payload(value: Any) -> dict[str, Any]:
    value = _object(value, ("summary", "tables", "notes"))
    summary, tables, notes = value["summary"], value["tables"], value["notes"]
    if not all(isinstance(part, list) for part in (summary, tables, notes)):
        _refuse("EVIDENCE_SCHEMA_REFUSED")
    if len(summary) > MAX_SUMMARY_ITEMS or len(tables) > MAX_TABLES or len(notes) > MAX_SUMMARY_ITEMS:
        _refuse("EVIDENCE_PAYLOAD_LIMIT_REFUSED")
    normal_summary = []
    for item in summary:
        item = _object(item, ("label", "value"))
        normal_summary.append({"label": _display_text(item["label"]), "value": _display_value(item["value"])})
    normal_tables = []
    for table in tables:
        table = _object(table, ("title", "columns", "rows"))
        columns, rows = table["columns"], table["rows"]
        if not isinstance(columns, list) or not isinstance(rows, list) or not columns or len(columns) > MAX_COLUMNS or len(rows) > MAX_ROWS_PER_TABLE:
            _refuse("EVIDENCE_CONTENT_REFUSED")
        normal_columns = [_display_text(column) for column in columns]
        normal_rows = []
        for row in rows:
            if not isinstance(row, list) or len(row) != len(normal_columns):
                _refuse("EVIDENCE_CONTENT_REFUSED")
            normal_rows.append([_display_value(cell) for cell in row])
        normal_tables.append({"title": _display_text(table["title"]), "columns": normal_columns, "rows": normal_rows})
    return {"summary": normal_summary, "tables": normal_tables, "notes": [_display_text(note, MAX_NOTE_BYTES) for note in notes]}


def _provenance(value: Any) -> dict[str, Any]:
    value = _object(value, ("publisher", "source_run_id", "generated_at", "inputs", "artifacts"))
    inputs, artifacts = value["inputs"], value["artifacts"]
    if not isinstance(inputs, list) or not isinstance(artifacts, list) or len(inputs) > MAX_PROVENANCE_RECORDS or len(artifacts) > MAX_ARTIFACT_REFERENCES:
        _refuse("EVIDENCE_PROVENANCE_REFUSED")
    normal_inputs = []
    for input_reference in inputs:
        input_reference = _object(input_reference, ("reference_id", "sha256"))
        normal_inputs.append({"reference_id": _token(input_reference["reference_id"]), "sha256": _sha256(input_reference["sha256"])})
    normal_artifacts = []
    for artifact in artifacts:
        artifact = _object(artifact, ("label", "path", "sha256"))
        normal_artifacts.append({"label": _display_text(artifact["label"]), "path": _artifact_path(artifact["path"]), "sha256": _sha256(artifact["sha256"])})
    return {
        "publisher": _display_text(value["publisher"]),
        "source_run_id": _token(value["source_run_id"]),
        "generated_at": _timestamp(value["generated_at"]),
        "inputs": normal_inputs,
        "artifacts": normal_artifacts,
    }


def canonical_payload_bytes(payload: Mapping[str, Any]) -> bytes:
    """Validate and encode a v2 payload in the cross-language digest form."""
    normalized = _payload(dict(payload))
    encoded = bytearray(b"quantops-evidence-payload/v2\0")
    _u32(encoded, len(normalized["summary"]))
    for item in normalized["summary"]:
        _text(encoded, item["label"])
        _display_value_bytes(encoded, item["value"])
    _u32(encoded, len(normalized["tables"]))
    for table in normalized["tables"]:
        _text(encoded, table["title"])
        _u32(encoded, len(table["columns"]))
        for column in table["columns"]:
            _text(encoded, column)
        _u32(encoded, len(table["rows"]))
        for row in table["rows"]:
            for value in row:
                _display_value_bytes(encoded, value)
    _u32(encoded, len(normalized["notes"]))
    for note in normalized["notes"]:
        _text(encoded, note)
    return bytes(encoded)


def _legacy_canonical_payload_bytes(payload: Mapping[str, Any]) -> bytes:
    return _compact_json(_payload(dict(payload)))


def _u32(encoded: bytearray, value: int) -> None:
    encoded.extend(value.to_bytes(4, "big"))


def _text(encoded: bytearray, value: str) -> None:
    raw = value.encode("utf-8")
    _u32(encoded, len(raw))
    encoded.extend(raw)


def _display_value_bytes(encoded: bytearray, value: Mapping[str, Any]) -> None:
    if value["kind"] == "text":
        encoded.append(1)
        _text(encoded, value["value"])
    elif value["kind"] == "number":
        encoded.append(2)
        _text(encoded, _number_token(value["value"]))
    else:
        encoded.append(3)
        encoded.append(1 if value["value"] else 0)


def _number_token(value: float) -> str:
    """Use JSON's finite numeric token, never a runtime float bit pattern."""
    return json.dumps(value, allow_nan=False, separators=(",", ":"))


def payload_sha256(payload: Mapping[str, Any]) -> str:
    """Return the SHA-256 of deterministic, typed v2 payload bytes."""
    return sha256(canonical_payload_bytes(payload)).hexdigest()


def _payload_sha256_for_schema(payload: Mapping[str, Any], schema_version: str) -> str:
    if schema_version == SCHEMA_VERSION:
        return payload_sha256(payload)
    if schema_version == LEGACY_SCHEMA_VERSION:
        return sha256(_legacy_canonical_payload_bytes(payload)).hexdigest()
    _refuse("EVIDENCE_SCHEMA_VERSION_REFUSED")


def admit_bundle_bytes(data: bytes) -> EvidenceBundle:
    """Admit one untrusted JSON bundle without opening its artifact references."""
    raw = _parse_bytes(data)
    raw = _object(raw, ("schema_version", "bundle_id", "payload_sha256", "provenance", "payload"))
    schema_version = raw["schema_version"]
    if schema_version not in {SCHEMA_VERSION, LEGACY_SCHEMA_VERSION}:
        _refuse("EVIDENCE_SCHEMA_VERSION_REFUSED")
    payload = _payload(raw["payload"])
    digest = _sha256(raw["payload_sha256"])
    if _payload_sha256_for_schema(payload, schema_version) != digest:
        _refuse("EVIDENCE_DIGEST_REFUSED")
    return EvidenceBundle(
        schema_version=schema_version,
        bundle_id=_token(raw["bundle_id"]),
        payload_sha256=digest,
        provenance=_provenance(raw["provenance"]),
        payload=payload,
    )


def build_bundle(*, bundle_id: str, publisher: str, source_run_id: str, generated_at: str, inputs: Sequence[Mapping[str, Any]], artifacts: Sequence[Mapping[str, Any] | ArtifactReference], payload: Mapping[str, Any]) -> EvidenceBundle:
    """Build a validated deterministic bundle for publication."""
    artifact_mappings = [artifact.to_mapping() if isinstance(artifact, ArtifactReference) else dict(artifact) for artifact in artifacts]
    normalized_payload = _payload(dict(payload))
    return admit_bundle_bytes(_compact_json({
        "schema_version": SCHEMA_VERSION,
        "bundle_id": bundle_id,
        "payload_sha256": payload_sha256(normalized_payload),
        "provenance": {"publisher": publisher, "source_run_id": source_run_id, "generated_at": generated_at, "inputs": list(inputs), "artifacts": artifact_mappings},
        "payload": normalized_payload,
    }))
