use quantops_sdk::{admit_bundle_bytes, canonical_payload_bytes, payload_sha256};
use std::path::PathBuf;

fn fixture(name: &str) -> Vec<u8> {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .join("fixtures");
    std::fs::read(root.join(name)).expect("fixture")
}

#[test]
fn valid_fixture_has_shared_integral_f64_digest() {
    let bundle = admit_bundle_bytes(&fixture("valid-integral-number.json")).expect("valid fixture");
    let expected = "b81f9dd7bd3eb7246acc5fcb2d1ab709096191fdd393007e09e583f28ca076dc";
    assert_eq!(bundle.payload_sha256, expected);
    assert_eq!(payload_sha256(&bundle.payload).expect("digest"), expected);
    assert!(canonical_payload_bytes(&bundle.payload)
        .expect("canonical")
        .windows(b"\"value\":42.0".len())
        .any(|window| window == b"\"value\":42.0"));
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
