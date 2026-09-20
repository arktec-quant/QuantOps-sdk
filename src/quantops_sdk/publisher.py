"""Safe, explicit artifact publication; admission never dereferences artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import os
import re
import shutil

from .evidence import ALLOWED_ARTIFACT_EXTENSIONS, ArtifactReference, EvidenceRefusal, MAX_TEXT_BYTES


@dataclass(frozen=True)
class PublishedArtifact:
    reference: ArtifactReference
    destination: Path


def publish_artifact(source: str | Path, artifact_root: str | Path, label: str) -> PublishedArtifact:
    """Copy one regular, allowlisted artifact beneath `artifact_root/artifacts`.

    The returned path is metadata for evidence bundles only. This function never
    makes artifact bytes part of bundle validation or consumer admission.
    """
    source_path = Path(source)
    try:
        source_stat = source_path.lstat()
    except OSError as error:
        raise EvidenceRefusal("EVIDENCE_ARTIFACT_SOURCE_REFUSED") from error
    if not source_path.is_file() or source_path.is_symlink() or source_stat.st_size < 0:
        raise EvidenceRefusal("EVIDENCE_ARTIFACT_SOURCE_REFUSED")
    extension = source_path.suffix
    if extension not in ALLOWED_ARTIFACT_EXTENSIONS:
        raise EvidenceRefusal("EVIDENCE_ARTIFACT_EXTENSION_REFUSED")
    if not isinstance(label, str) or not label or len(label.encode("utf-8")) > MAX_TEXT_BYTES:
        raise EvidenceRefusal("EVIDENCE_ARTIFACT_LABEL_REFUSED")
    root = Path(artifact_root)
    try:
        root.mkdir(parents=True, exist_ok=True)
        if root.is_symlink() or not root.is_dir():
            raise OSError("artifact root is not a plain directory")
        destination_dir = root / "artifacts"
        destination_dir.mkdir(exist_ok=True)
        if destination_dir.is_symlink() or not destination_dir.is_dir():
            raise OSError("artifact directory is not a plain directory")
    except OSError as error:
        raise EvidenceRefusal("EVIDENCE_ARTIFACT_DESTINATION_REFUSED") from error
    digest = _file_sha256(source_path)
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "-", source_path.stem).strip(".-") or "artifact"
    destination = destination_dir / f"{digest[:16]}-{safe_name}{extension}"
    if destination.exists() and (destination.is_symlink() or not destination.is_file() or _file_sha256(destination) != digest):
        raise EvidenceRefusal("EVIDENCE_ARTIFACT_DESTINATION_REFUSED")
    if not destination.exists():
        temporary = destination_dir / f".{destination.name}.{os.getpid()}.tmp"
        try:
            with source_path.open("rb") as incoming, temporary.open("xb") as outgoing:
                shutil.copyfileobj(incoming, outgoing)
                outgoing.flush()
                os.fsync(outgoing.fileno())
            os.replace(temporary, destination)
        except OSError as error:
            temporary.unlink(missing_ok=True)
            raise EvidenceRefusal("EVIDENCE_ARTIFACT_DESTINATION_REFUSED") from error
    return PublishedArtifact(ArtifactReference(label=label, path=f"artifacts/{destination.name}", sha256=digest), destination)


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(64 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
