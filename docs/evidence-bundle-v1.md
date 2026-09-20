# QuantOps Evidence Bundle v1

`quantops-evidence-bundle/v1` is an artifact-first, display-data interchange
format. A producer serializes a self-contained JSON document; a consumer
validates that document without contacting a producer or opening a referenced
artifact. The format carries no provider, framework, UI, or runtime identity.

## Wire shape

```json
{
  "schema_version": "quantops-evidence-bundle/v1",
  "bundle_id": "token",
  "payload_sha256": "64-character SHA-256",
  "provenance": {
    "publisher": "display text",
    "source_run_id": "token",
    "generated_at": "YYYY-MM-DDTHH:MM:SSZ",
    "inputs": [{"reference_id": "token", "sha256": "SHA-256"}],
    "artifacts": [{"label": "display text", "path": "artifacts/name.json", "sha256": "SHA-256"}]
  },
  "payload": {
    "summary": [{"label": "display text", "value": {"kind": "text|number|boolean", "value": "scalar"}}],
    "tables": [{"title": "display text", "columns": ["display text"], "rows": [[{"kind": "text|number|boolean", "value": "scalar"}]]}],
    "notes": ["display text"]
  }
}
```

Every object rejects unknown and duplicate fields. `payload_sha256` is the
lowercase SHA-256 of the compact UTF-8 JSON serialization of a validated
payload, using the field order shown above. JSON numbers are normalized to
finite IEEE-754 `f64`; the shared valid fixture uses `42.0` to lock the
cross-language integral-number representation.

## Limits and refusal boundary

- Bundle: 65,536 bytes; summary: 24 items; tables: 8; columns: 12 per table;
  rows: 100 per table; notes: 24.
- Display fields are at most 512 UTF-8 bytes, except notes at 1,024 bytes.
  Only text, finite numbers, and booleans are admitted.
- `inputs` and artifact metadata each allow at most 16 entries.
- Artifact references must be relative paths below `artifacts/`, with `.csv`,
  `.json`, `.pdf`, or `.txt` extensions. They are metadata only: validation
  and native admission never read, serve, or execute their paths.
- Unsafe text (script/tag/template markers), unsafe paths, unknown fields,
  malformed/oversized values, and digest mismatches are refused with stable
  `EVIDENCE_*_REFUSED` error codes.

Python `publish_artifact` and Rust `publish_artifact` copy a regular,
allowlisted source into a caller-owned `artifacts/` directory and return a
metadata reference. The publication helper does not change the admission rule:
consumers still validate the bundle only.
