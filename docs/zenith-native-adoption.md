# Zenith-native adoption

## Goal

A Python research project can use QuantOps SDK to publish evidence to a
Zenith-hosted QuantOps application without retaining a Flask-based user
interface. Python remains responsible for research, notebooks, batch work, and
artifact production. QuantOps's Rust platform becomes the interface where
authorized users inspect admitted evidence.

The runtime boundary is intentionally narrow:

```text
Python research or notebook
  -> QuantOps SDK bundle
  -> authenticated Zenith delivery
  -> QuantOps Spire admission
  -> Rust SSR pages and governed UI
```

No notebook, Python module, or research runtime crosses this boundary. A
consumer receives a versioned artifact plus its provenance. It does not import
or execute the producer's code.

## Migration phases

### 1. Publish evidence

Keep existing Python research workflows. At each approved publication point,
build a `quantops-evidence-bundle/v2` with bounded summaries, tables, notes,
input references, and metadata-only artifact references.

Use the SDK's local admission before delivery. This keeps Python output aligned
with the Rust consumer's validator.

### 2. Deliver through Zenith

Add a Zenith delivery adapter that accepts only an authenticated, versioned
bundle envelope. The adapter writes to a consumer-owned inbox or queue. It does
not accept arbitrary paths, Python objects, notebooks, or executable payloads.

The receiving QuantOps Spire validates the raw bytes with the Rust SDK crate.
On refusal it records a stable non-sensitive code and does not render the
untrusted content.

### 3. Render in QuantOps

Build Rust SSR pages for the research project's evidence catalog, run detail,
and admitted payload. QuantOps owns navigation, roles, audit presentation,
theme, and user-facing lifecycle views.

The producer remains a source of evidence only. Its UI routes, Flask templates,
and client session state are not part of the integrated platform.

### 4. Retire the Flask UI

Once the Rust pages meet the required user workflows, remove Flask HTML routes.
The Python project may retain a small command-line publisher or a job worker.
A read-only service may remain temporarily for compatibility, but it should not
be the primary UI or authority for evidence admission.

## Contract expansion

The first contract is display evidence. Additional contracts should be added as
separate versioned schemas rather than expanding this bundle into a generic
application protocol:

- `quantops-research-catalog/v1` for a bounded list of published runs.
- `quantops-workspace-snapshot/v1` for a role-filtered dashboard snapshot.
- `quantops-job-result/v1` for a governed batch result and publication state.
- `quantops-artifact-manifest/v1` for authorized retrieval metadata after
  admission.

Each contract needs Python and Rust conformance fixtures, byte limits,
canonicalization rules, refusal codes, and a clear statement of who owns
authorization. Do not add arbitrary JSON, remote URLs, executable content, or
opaque serialized Python objects to the contracts.

## Delivery gates

Before a producer retires its Flask UI, verify that the Zenith path has:

- authenticated producer identity and consumer authorization;
- version-pinned contract validation on both sides;
- deterministic handling for retries and duplicate bundle IDs;
- provenance and audit events that do not expose private payloads;
- role-filtered Rust SSR views for every required evidence workflow; and
- an explicit retention and artifact retrieval policy.

This creates a platform boundary that lets Python projects remain useful for
research while QuantOps and Zenith own the governed application experience.
