# Published Evidence Index (v1.0)

## 1. Purpose

This index distinguishes published evidence from reference example paths used in contract docs.  
Published evidence means a concrete evidence bundle has been produced and retained with verification results.  
Reference example paths are naming examples and do not imply public artifact availability.

## 2. Publication policy

- Evidence bundles are not shipped inside SDK release artifacts.
- When evidence is published, it is delivered as:
  - an evidence bundle directory conforming to `docs/contracts/determinism_evidence_bundle_v1_0.md`
  - optional comparison report(s) for cross-platform claims

## 3. Minimum acceptance for a published claim

- Bundle verification passes (`verify-existing` exit code `0`).
- A comparison report is present when a cross-platform claim is made.
- `environment/tool_versions.json` and `environment/platform_fingerprint.json` are present.

## 4. Current v1.0 status

| Requirement | Status |
| --- | --- |
| DET-001 | Evidence available internally; public publication TBD. |
| DET-002 | Evidence available internally; locale provisioning caveats documented; public publication TBD. |
| DET-003 | Evidence available internally; canonical compare artifact defined; public publication TBD. |

Multi-host evidence is TBD.
