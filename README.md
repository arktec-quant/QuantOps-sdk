# QuantOps SDK

QuantOps SDK is a protocol-first, artifact-first SDK for
`quantops-evidence-bundle/v1`. It lets a research or operational project
publish bounded display evidence that a native consumer can validate without
importing the producer's code or contacting its runtime.

It includes no HTTP service, UI, model runtime, market data, research logic,
or embedded Python bridge for native consumers. The SDK is MIT licensed.

## Install

The current public release is source-distributed through GitHub. Install the
tagged Python package with:

```bash
python -m pip install "quantops-sdk @ git+https://github.com/arktec-quant/QuantOps-sdk.git@v0.1.1"
```

The Rust contract crate is available from the same tagged repository:

```toml
[dependencies]
quantops-sdk = { git = "https://github.com/arktec-quant/QuantOps-sdk.git", tag = "v0.1.1", package = "quantops-sdk" }
```

## Python producer

```python
from quantops_sdk import admit_bundle_bytes, build_bundle

bundle = build_bundle(
    bundle_id="run-42",
    publisher="research-pipeline",
    source_run_id="run-42",
    generated_at="2026-09-20T00:00:00Z",
    inputs=[],
    artifacts=[],
    payload={
        "summary": [{"label": "Status", "value": {"kind": "text", "value": "Complete"}}],
        "tables": [],
        "notes": ["Results are published as display evidence."],
    },
)

# Validate the exact bytes that will cross the runtime boundary.
admitted = admit_bundle_bytes(bundle.to_json_bytes())
```

Use `publish_artifact` only to copy an allowlisted file into a producer-owned
artifact directory. Its returned reference is metadata. Consumer admission
must not open, serve, or execute a referenced artifact.

## Native consumer

The Rust crate exposes `admit_bundle_bytes`, `canonical_payload_bytes`,
`EvidenceBundle`, `DisplayValue`, and `EvidenceRefusal`. A consumer admits
untrusted JSON bytes, renders only the returned typed display values, and
handles stable refusal codes without exposing input details.

```text
cargo test --manifest-path rust/Cargo.toml
```

## Contract and safety

- [Evidence Bundle v1](docs/evidence-bundle-v1.md) defines the wire format,
  limits, digest rules, and refusal conditions.
- [Public release boundary](docs/public-release-boundary.md) defines what this
  repository intentionally includes and excludes.
- [Zenith-native adoption](docs/zenith-native-adoption.md) describes how a
  Python research project can retire its Flask UI while retaining its notebooks
  and artifact producer role.
- `schemas/` and `fixtures/` provide the shared cross-language conformance
  corpus.

## Development

Run Python tests with `python -m pytest`. Run Rust tests with
`cargo test --manifest-path rust/Cargo.toml`. Build a Python wheel with
`python -m pip wheel --no-deps .`.

The repository accepts security-sensitive reports through GitHub's private
vulnerability reporting when available. Do not include credentials, private
data, or customer artifacts in public issues.
