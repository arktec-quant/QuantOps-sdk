use quantops_sdk::{
    admit_bundle_bytes, canonical_payload_bytes, payload_sha256, LEGACY_SCHEMA_VERSION,
};
use std::path::PathBuf;

fn fixture(name: &str) -> Vec<u8> {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .join("fixtures");
    std::fs::read(root.join(name)).expect("fixture")
}

#[test]
fn legacy_v1_fixture_remains_admissible() {
    let bundle = admit_bundle_bytes(&fixture("valid-integral-number.json")).expect("valid fixture");
    let expected = "b81f9dd7bd3eb7246acc5fcb2d1ab709096191fdd393007e09e583f28ca076dc";
    assert_eq!(bundle.schema_version, LEGACY_SCHEMA_VERSION);
    assert_eq!(bundle.payload_sha256, expected);
}

#[test]
fn v2_digest_preserves_the_validated_numeric_token() {
    let bundle = admit_bundle_bytes(&fixture("valid-decimal-v2.json")).expect("v2 fixture");
    assert_eq!(
        bundle.payload_sha256,
        "aba523562772023653fb7417c200a1b8878b0943939f51bdd25b5057cc13dacb"
    );
    assert_eq!(
        payload_sha256(&bundle.payload).expect("digest"),
        bundle.payload_sha256
    );
    assert!(canonical_payload_bytes(&bundle.payload)
        .expect("canonical")
        .starts_with(b"quantops-evidence-payload/v2\0"));
}

#[test]
fn shared_invalid_fixtures_are_refused() {
    for name in [
        "invalid-digest-tampered.json",
        "invalid-unknown-field.json",
        "invalid-unsafe-content.json",
        "invalid-unsafe-artifact.json",
    ] {
        assert!(admit_bundle_bytes(&fixture(name)).is_err(), "{name}");
    }
}
