# Public release boundary

QuantOps SDK is a public interoperability package. It provides a generic
artifact contract, Python and Rust validators, publication helpers, JSON
Schema, and synthetic conformance fixtures.

## Included

- A deterministic evidence-bundle format and its validation rules.
- Generic, bounded display data and metadata-only artifact references.
- Public Python and Rust libraries that implement the same contract.
- Synthetic test fixtures that demonstrate accepted and refused input.

## Excluded

The repository must not contain QuantOps operational state, tenant records,
research strategies, model code, notebooks, market-data content, credentials,
private endpoints, local filesystem paths, or internal network topology.

The SDK does not authorize access to an artifact. It does not fetch artifacts
while validating a bundle. It does not run producer code, process templates,
or expose a UI.

## Consumer responsibilities

Consumers must validate raw bundle bytes before rendering anything. They must
render only admitted typed display values, preserve the SDK's refusal boundary,
and treat artifact references as metadata unless a separately authorized,
bounded retrieval system handles them.

When reporting a vulnerability, do not put sensitive sample data or secrets in
a public issue. Use GitHub private vulnerability reporting when it is enabled
for this repository.
