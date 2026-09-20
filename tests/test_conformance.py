from __future__ import annotations

from pathlib import Path

import pytest

from quantops_sdk import EvidenceRefusal, LEGACY_SCHEMA_VERSION, SCHEMA_VERSION, admit_bundle_bytes, build_bundle, payload_sha256, publish_artifact


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_legacy_v1_fixture_remains_admissible() -> None:
    raw = fixture("valid-integral-number.json")
    admitted = admit_bundle_bytes(raw)
    expected = "b81f9dd7bd3eb7246acc5fcb2d1ab709096191fdd393007e09e583f28ca076dc"
    assert admitted.schema_version == LEGACY_SCHEMA_VERSION
    assert admitted.payload_sha256 == expected
    assert b'"value":42.0' in admitted.to_json_bytes()


def test_v2_digest_preserves_exact_decimal_bits() -> None:
    bundle = build_bundle(
        bundle_id="decimal-conformance",
        publisher="test publisher",
        source_run_id="run-1",
        generated_at="2026-09-20T00:00:00Z",
        inputs=[],
        artifacts=[],
        payload={
            "summary": [{"label": "Decimal", "value": {"kind": "number", "value": 1.0457787078281227}}],
            "tables": [],
            "notes": ["Exact numeric digest."],
        },
    )
    assert bundle.schema_version == SCHEMA_VERSION
    assert payload_sha256(bundle.payload) == bundle.payload_sha256
    assert admit_bundle_bytes(bundle.to_json_bytes()) == bundle


@pytest.mark.parametrize(
    "name",
    [
        "invalid-digest-tampered.json",
        "invalid-unknown-field.json",
        "invalid-unsafe-content.json",
        "invalid-unsafe-artifact.json",
    ],
)
def test_shared_invalid_fixtures_are_refused(name: str) -> None:
    with pytest.raises(EvidenceRefusal):
        admit_bundle_bytes(fixture(name))


def test_builder_round_trip_and_safe_artifact_publication(tmp_path: Path) -> None:
    source = tmp_path / "report.json"
    source.write_text('{"result":"ok"}', encoding="utf-8")
    published = publish_artifact(source, tmp_path / "published", "report")
    assert published.reference.path.startswith("artifacts/")
    bundle = build_bundle(
        bundle_id="publisher-test",
        publisher="test publisher",
        source_run_id="run-1",
        generated_at="2026-09-20T00:00:00Z",
        inputs=[],
        artifacts=[published.reference],
        payload={"summary": [], "tables": [], "notes": []},
    )
    assert admit_bundle_bytes(bundle.to_json_bytes()) == bundle
