# QuantOps Evidence Bundle v2

`quantops-evidence-bundle/v2` is the active artifact-first display-evidence
contract. It has the same bounded JSON shape as v1. A producer publishes one
self-contained document. A consumer validates it without contacting the
producer or opening a referenced artifact.

The v2 payload digest is not a JSON reserialization hash. It encodes the
validated payload in fixed field order with explicit UTF-8 byte lengths. Text
and notes use their UTF-8 bytes. Boolean values use a one-byte value. Numeric
values use their validated JSON numeric token as UTF-8 text. This avoids a
Python and Rust parser selecting different binary floating-point values for a
decimal number.

The digest payload begins with the ASCII domain separator
`quantops-evidence-payload/v2` followed by one zero byte. It then encodes:

- summary count, then each label and tagged display value;
- table count, then each title, column count and columns, row count and cells;
- note count, then each note.

Every count and string length is an unsigned 32-bit big-endian integer. Display
value tags are `1` for text, `2` for number, and `3` for boolean. A numeric
token is the compact finite JSON representation produced by the SDK publisher.

The JSON envelope remains:

```json
{
  "schema_version": "quantops-evidence-bundle/v2",
  "bundle_id": "token",
  "payload_sha256": "64-character SHA-256",
  "provenance": {"publisher": "display text", "source_run_id": "token", "generated_at": "YYYY-MM-DDTHH:MM:SSZ", "inputs": [], "artifacts": []},
  "payload": {"summary": [], "tables": [], "notes": []}
}
```

Unknown or duplicate fields, unsafe text, malformed paths, non-finite numbers,
oversized documents, and digest mismatches are refused. Artifact references are
metadata only. Admission never opens, serves, or executes them.

Consumers may keep v1 read compatibility for already-published evidence. New
publishers must use v2.
