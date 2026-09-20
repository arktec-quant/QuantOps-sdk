//! Runtime-neutral admission and artifact publication for QuantOps evidence.
//!
//! This crate performs no HTTP, UI rendering, Python execution, or artifact
//! dereferencing. Native consumers admit JSON bytes, then use the typed model.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    fmt, fs,
    io::Write,
    path::{Component, Path, PathBuf},
};

pub const SCHEMA_VERSION: &str = "quantops-evidence-bundle/v1";
pub const MAX_BUNDLE_BYTES: usize = 65_536;
pub const MAX_TEXT_BYTES: usize = 512;
pub const MAX_NOTE_BYTES: usize = 1_024;
pub const MAX_SUMMARY_ITEMS: usize = 24;
pub const MAX_TABLES: usize = 8;
pub const MAX_COLUMNS: usize = 12;
pub const MAX_ROWS_PER_TABLE: usize = 100;
pub const MAX_PROVENANCE_RECORDS: usize = 16;
pub const MAX_ARTIFACT_REFERENCES: usize = 16;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EvidenceRefusal {
    pub code: &'static str,
}

impl fmt::Display for EvidenceRefusal {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        self.code.fmt(formatter)
    }
}

impl std::error::Error for EvidenceRefusal {}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct EvidenceBundle {
    pub schema_version: String,
    pub bundle_id: String,
    pub payload_sha256: String,
    pub provenance: Provenance,
    pub payload: DisplayPayload,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Provenance {
    pub publisher: String,
    pub source_run_id: String,
    pub generated_at: String,
    pub inputs: Vec<InputReference>,
    pub artifacts: Vec<ArtifactReference>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct InputReference {
    pub reference_id: String,
    pub sha256: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ArtifactReference {
    pub label: String,
    pub path: String,
    pub sha256: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DisplayPayload {
    pub summary: Vec<SummaryItem>,
    pub tables: Vec<DisplayTable>,
    pub notes: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SummaryItem {
    pub label: String,
    pub value: DisplayValue,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DisplayTable {
    pub title: String,
    pub columns: Vec<String>,
    pub rows: Vec<Vec<DisplayValue>>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(
    tag = "kind",
    content = "value",
    rename_all = "snake_case",
    deny_unknown_fields
)]
pub enum DisplayValue {
    Text(String),
    Number(f64),
    Boolean(bool),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PublishedArtifact {
    pub reference: ArtifactReference,
    pub destination: PathBuf,
}

/// Admits exactly one bundle document. Provenance artifact paths stay metadata.
pub fn admit_bundle_bytes(bytes: &[u8]) -> Result<EvidenceBundle, EvidenceRefusal> {
    if bytes.len() > MAX_BUNDLE_BYTES {
        return Err(refusal("EVIDENCE_BUNDLE_SIZE_REFUSED"));
    }
    let bundle: EvidenceBundle =
        serde_json::from_slice(bytes).map_err(|_| refusal("EVIDENCE_SCHEMA_REFUSED"))?;
    bundle.validate()?;
    Ok(bundle)
}

impl EvidenceBundle {
    /// Validates an already decoded bundle without opening any referenced artifact.
    pub fn validate(&self) -> Result<(), EvidenceRefusal> {
        if self.schema_version != SCHEMA_VERSION || !is_token(&self.bundle_id, 96) {
            return Err(refusal("EVIDENCE_SCHEMA_VERSION_REFUSED"));
        }
        if !is_sha256(&self.payload_sha256) {
            return Err(refusal("EVIDENCE_DIGEST_REFUSED"));
        }
        if payload_sha256(&self.payload)? != self.payload_sha256 {
            return Err(refusal("EVIDENCE_DIGEST_REFUSED"));
        }
        validate_provenance(&self.provenance)?;
        validate_payload(&self.payload)
    }

    /// Returns deterministic compact JSON after the bundle has been validated.
    pub fn canonical_json_bytes(&self) -> Result<Vec<u8>, EvidenceRefusal> {
        self.validate()?;
        serde_json::to_vec(self).map_err(|_| refusal("EVIDENCE_SCHEMA_REFUSED"))
    }
}

/// Serializes a validated payload in the cross-language digest representation.
pub fn canonical_payload_bytes(payload: &DisplayPayload) -> Result<Vec<u8>, EvidenceRefusal> {
    validate_payload(payload)?;
    serde_json::to_vec(payload).map_err(|_| refusal("EVIDENCE_SCHEMA_REFUSED"))
}

/// Returns the lowercase SHA-256 for deterministic, validated payload JSON.
pub fn payload_sha256(payload: &DisplayPayload) -> Result<String, EvidenceRefusal> {
    Ok(format!(
        "{:x}",
        Sha256::digest(canonical_payload_bytes(payload)?)
    ))
}

/// Copies one regular allowlisted file under `artifact_root/artifacts`.
/// The returned reference is metadata only; `admit_bundle_bytes` never opens it.
pub fn publish_artifact(
    source: impl AsRef<Path>,
    artifact_root: impl AsRef<Path>,
    label: impl Into<String>,
) -> Result<PublishedArtifact, EvidenceRefusal> {
    let source = source.as_ref();
    let label = label.into();
    let metadata =
        fs::symlink_metadata(source).map_err(|_| refusal("EVIDENCE_ARTIFACT_SOURCE_REFUSED"))?;
    if metadata.file_type().is_symlink() || !metadata.is_file() {
        return Err(refusal("EVIDENCE_ARTIFACT_SOURCE_REFUSED"));
    }
    if !is_display_text(&label, MAX_TEXT_BYTES) {
        return Err(refusal("EVIDENCE_ARTIFACT_LABEL_REFUSED"));
    }
    let extension = source.extension().and_then(|value| value.to_str());
    if !matches!(extension, Some("csv" | "json" | "pdf" | "txt")) {
        return Err(refusal("EVIDENCE_ARTIFACT_EXTENSION_REFUSED"));
    }
    let root = artifact_root.as_ref();
    fs::create_dir_all(root).map_err(|_| refusal("EVIDENCE_ARTIFACT_DESTINATION_REFUSED"))?;
    let root_metadata =
        fs::symlink_metadata(root).map_err(|_| refusal("EVIDENCE_ARTIFACT_DESTINATION_REFUSED"))?;
    if root_metadata.file_type().is_symlink() || !root_metadata.is_dir() {
        return Err(refusal("EVIDENCE_ARTIFACT_DESTINATION_REFUSED"));
    }
    let directory = root.join("artifacts");
    fs::create_dir_all(&directory).map_err(|_| refusal("EVIDENCE_ARTIFACT_DESTINATION_REFUSED"))?;
    let directory_metadata = fs::symlink_metadata(&directory)
        .map_err(|_| refusal("EVIDENCE_ARTIFACT_DESTINATION_REFUSED"))?;
    if directory_metadata.file_type().is_symlink() || !directory_metadata.is_dir() {
        return Err(refusal("EVIDENCE_ARTIFACT_DESTINATION_REFUSED"));
    }
    let digest = file_sha256(source)?;
    let stem = source
        .file_stem()
        .and_then(|value| value.to_str())
        .unwrap_or("artifact");
    let safe_stem: String = stem
        .chars()
        .map(|value| {
            if value.is_ascii_alphanumeric() || matches!(value, '.' | '_' | '-') {
                value
            } else {
                '-'
            }
        })
        .collect();
    let normalized_stem = safe_stem.trim_matches(&['.', '-'][..]);
    let safe_stem = if normalized_stem.is_empty() {
        "artifact"
    } else {
        normalized_stem
    };
    let file_name = format!(
        "{}-{}.{}",
        &digest[..16],
        safe_stem,
        extension.unwrap_or_default()
    );
    let destination = directory.join(&file_name);
    if destination.exists() {
        let existing = fs::symlink_metadata(&destination)
            .map_err(|_| refusal("EVIDENCE_ARTIFACT_DESTINATION_REFUSED"))?;
        if existing.file_type().is_symlink()
            || !existing.is_file()
            || file_sha256(&destination)? != digest
        {
            return Err(refusal("EVIDENCE_ARTIFACT_DESTINATION_REFUSED"));
        }
    } else {
        let temporary = directory.join(format!(".{file_name}.tmp"));
        let result = (|| -> Result<(), EvidenceRefusal> {
            let mut incoming =
                fs::File::open(source).map_err(|_| refusal("EVIDENCE_ARTIFACT_SOURCE_REFUSED"))?;
            let mut outgoing = fs::OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(&temporary)
                .map_err(|_| refusal("EVIDENCE_ARTIFACT_DESTINATION_REFUSED"))?;
            std::io::copy(&mut incoming, &mut outgoing)
                .map_err(|_| refusal("EVIDENCE_ARTIFACT_DESTINATION_REFUSED"))?;
            outgoing
                .flush()
                .map_err(|_| refusal("EVIDENCE_ARTIFACT_DESTINATION_REFUSED"))?;
            outgoing
                .sync_all()
                .map_err(|_| refusal("EVIDENCE_ARTIFACT_DESTINATION_REFUSED"))?;
            fs::rename(&temporary, &destination)
                .map_err(|_| refusal("EVIDENCE_ARTIFACT_DESTINATION_REFUSED"))
        })();
        if result.is_err() {
            let _ = fs::remove_file(&temporary);
        }
        result?;
    }
    Ok(PublishedArtifact {
        reference: ArtifactReference {
            label,
            path: format!("artifacts/{file_name}"),
            sha256: digest,
        },
        destination,
    })
}

fn validate_provenance(provenance: &Provenance) -> Result<(), EvidenceRefusal> {
    if !is_display_text(&provenance.publisher, MAX_TEXT_BYTES)
        || !is_token(&provenance.source_run_id, 96)
        || !is_timestamp(&provenance.generated_at)
        || provenance.inputs.len() > MAX_PROVENANCE_RECORDS
        || provenance.artifacts.len() > MAX_ARTIFACT_REFERENCES
    {
        return Err(refusal("EVIDENCE_PROVENANCE_REFUSED"));
    }
    for input in &provenance.inputs {
        if !is_token(&input.reference_id, 96) || !is_sha256(&input.sha256) {
            return Err(refusal("EVIDENCE_PROVENANCE_REFUSED"));
        }
    }
    for artifact in &provenance.artifacts {
        if !is_display_text(&artifact.label, MAX_TEXT_BYTES)
            || !is_relative_artifact(&artifact.path)
            || !is_sha256(&artifact.sha256)
        {
            return Err(refusal("EVIDENCE_ARTIFACT_REFUSED"));
        }
    }
    Ok(())
}

fn validate_payload(payload: &DisplayPayload) -> Result<(), EvidenceRefusal> {
    if payload.summary.len() > MAX_SUMMARY_ITEMS
        || payload.tables.len() > MAX_TABLES
        || payload.notes.len() > MAX_SUMMARY_ITEMS
    {
        return Err(refusal("EVIDENCE_PAYLOAD_LIMIT_REFUSED"));
    }
    for summary in &payload.summary {
        if !is_display_text(&summary.label, MAX_TEXT_BYTES) || !is_display_value(&summary.value) {
            return Err(refusal("EVIDENCE_CONTENT_REFUSED"));
        }
    }
    for table in &payload.tables {
        if !is_display_text(&table.title, MAX_TEXT_BYTES)
            || table.columns.is_empty()
            || table.columns.len() > MAX_COLUMNS
            || table.rows.len() > MAX_ROWS_PER_TABLE
            || table
                .columns
                .iter()
                .any(|value| !is_display_text(value, MAX_TEXT_BYTES))
            || table.rows.iter().any(|row| {
                row.len() != table.columns.len() || row.iter().any(|value| !is_display_value(value))
            })
        {
            return Err(refusal("EVIDENCE_CONTENT_REFUSED"));
        }
    }
    if payload
        .notes
        .iter()
        .any(|value| !is_display_text(value, MAX_NOTE_BYTES))
    {
        return Err(refusal("EVIDENCE_CONTENT_REFUSED"));
    }
    Ok(())
}

fn is_display_value(value: &DisplayValue) -> bool {
    match value {
        DisplayValue::Text(value) => is_display_text(value, MAX_TEXT_BYTES),
        DisplayValue::Number(value) => value.is_finite(),
        DisplayValue::Boolean(_) => true,
    }
}

fn is_display_text(value: &str, limit: usize) -> bool {
    !value.is_empty()
        && value.len() <= limit
        && value
            .chars()
            .all(|character| character == '\n' || character == '\t' || !character.is_control())
        && ![
            "<script",
            "</script",
            "javascript:",
            "data:text/html",
            "<?",
            "{%",
            "{{",
        ]
        .iter()
        .any(|needle| value.to_ascii_lowercase().contains(needle))
}

fn is_relative_artifact(value: &str) -> bool {
    let path = Path::new(value);
    value.starts_with("artifacts/")
        && !value.contains('\\')
        && !path.is_absolute()
        && path
            .components()
            .all(|component| matches!(component, Component::Normal(_)))
        && matches!(
            path.extension().and_then(|value| value.to_str()),
            Some("csv" | "json" | "pdf" | "txt")
        )
}

fn is_timestamp(value: &str) -> bool {
    value.len() == 20
        && value.ends_with('Z')
        && value.as_bytes().get(4) == Some(&b'-')
        && value.as_bytes().get(7) == Some(&b'-')
        && value.as_bytes().get(10) == Some(&b'T')
        && value.as_bytes().get(13) == Some(&b':')
        && value.as_bytes().get(16) == Some(&b':')
        && value
            .bytes()
            .enumerate()
            .filter(|(index, _)| ![4, 7, 10, 13, 16, 19].contains(index))
            .all(|(_, byte)| byte.is_ascii_digit())
}

fn is_token(value: &str, limit: usize) -> bool {
    !value.is_empty()
        && value.len() <= limit
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'_' | b'-'))
}
fn is_sha256(value: &str) -> bool {
    value.len() == 64 && value.bytes().all(|byte| byte.is_ascii_hexdigit())
}
fn refusal(code: &'static str) -> EvidenceRefusal {
    EvidenceRefusal { code }
}

fn file_sha256(path: &Path) -> Result<String, EvidenceRefusal> {
    let bytes = fs::read(path).map_err(|_| refusal("EVIDENCE_ARTIFACT_SOURCE_REFUSED"))?;
    Ok(format!("{:x}", Sha256::digest(bytes)))
}
