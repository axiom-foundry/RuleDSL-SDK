# Evidence Sanity

## Forbidden leakage

Evidence artifacts MUST NOT contain host-identifying or ambient-environment leakage, including:

- Absolute host paths (`C:\`, `/Users/`, `/home/`)
- Hostname fragments (`DESKTOP-`)
- Real wall-clock ISO timestamp strings

## Why this matters

Deterministic evidence must remain portable across machines and reproducible across reruns. Host leakage breaks replay confidence and weakens auditability.

## How to fix

- Remove host-specific fields from evidence payloads.
- Keep deterministic fields canonical and environment-independent.
- Re-run the scanner until no forbidden patterns are reported.

Tooling:

- Scanner: `Tools/evidence_sanity/scan_evidence.py`
- CI job: `evidence-sanity`
