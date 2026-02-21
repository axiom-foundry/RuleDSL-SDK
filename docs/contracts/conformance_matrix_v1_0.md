# Conformance Matrix (v1.0)

This matrix provides placeholder mapping for determinism requirements (DET-001..DET-050).
Test and evidence columns are intentionally empty in this initial RFC and will be filled as conformance assets are published.
Reference evidence paths in this matrix are examples for internal conformance capture and are not shipped in SDK release artifacts.
DET-002 and DET-003 entries below use concrete reference example paths from internal evidence runs.

| Requirement ID | Contract reference | Test | Evidence |
| --- | --- | --- | --- |
| DET-001 | determinism_contract_v1_0.md Section 3 [DET-001] | `Tools/smoke/compiler_smoke_test.ps1` | `reports/determinism_v1_0/<date>/<platform>/<config>/outputs/DET-001_smoke.json` (see `determinism_evidence_bundle_v1_0.md`); example compare report: `reports/determinism_compare_v1/2026-02-21/DET-001/windows-x64__linux-x64/comparison.json` |
| DET-002 | determinism_contract_v1_0.md Section 3 [DET-002] | `axiom_ruledsl_identifier_class_conformance_tests` | `reports/determinism_v1_0/2026-02-21/linux-x64/release-local-det002/outputs/DET-002_smoke.json` (reference example; see `determinism_evidence_bundle_v1_0.md`) |
| DET-003 | determinism_contract_v1_0.md Section 3 [DET-003] | `Tools/smoke/compiler_smoke_test.ps1` | `reports/determinism_compare_v1/2026-02-21/DET-003/windows-x64__linux-x64/comparison.json` (reference example; see `determinism_evidence_bundle_v1_0.md`) |
| DET-004 | determinism_contract_v1_0.md Section 3 [DET-004] | `axiom_ruledsl_identifier_class_conformance_tests` | `reports/determinism_v1_0/<date>/<platform>/<config>/outputs/DET-004_input_normalization.json` (see `determinism_evidence_bundle_v1_0.md`) |
| DET-005 | determinism_contract_v1_0.md Section 3 [DET-005] | `Tools/smoke/compiler_smoke_test.ps1` | `reports/determinism_v1_0/<date>/<platform>/<config>/outputs/DET-005_default_options.json` (see `determinism_evidence_bundle_v1_0.md`) |
| DET-006 | determinism_contract_v1_0.md Section 3 [DET-006] | TBD | `reports/determinism_v1_0/<date>/<platform>/<config>/outputs/DET-006_platform_scope.json` (see `determinism_evidence_bundle_v1_0.md`) |
| DET-007 | determinism_contract_v1_0.md Section 3 [DET-007] | TBD | `reports/determinism_v1_0/<date>/<platform>/<config>/outputs/DET-007_platform_constraints.json` (see `determinism_evidence_bundle_v1_0.md`) |
| DET-008 | determinism_contract_v1_0.md Section 3 [DET-008] | `verify` (GitHub Actions) | `reports/determinism_v1_0/<date>/<platform>/<config>/outputs/DET-008_no_fs_enumeration.json` (see `determinism_evidence_bundle_v1_0.md`) |
| DET-009 | determinism_contract_v1_0.md Section 3 [DET-009] | TBD | `reports/determinism_v1_0/<date>/<platform>/<config>/outputs/DET-009_reserved_options.json` (see `determinism_evidence_bundle_v1_0.md`) |
| DET-010 | determinism_contract_v1_0.md Section 3 [DET-010] | `audit-summary` artifact | `reports/determinism_v1_0/<date>/<platform>/<config>/outputs/DET-010_violation_report.json` (see `determinism_evidence_bundle_v1_0.md`) |
| DET-011 | undefined_behavior_v1_0.md [DET-011] | `ruledslc verify` (malformed input cases) | `reports/determinism_v1_0/<date>/<platform>/<config>/outputs/DET-011_malformed_bytecode.json` (see `determinism_evidence_bundle_v1_0.md`) |
| DET-012 | undefined_behavior_v1_0.md [DET-012] | `ax_check_bytecode_compatibility` integration checks | `reports/determinism_v1_0/<date>/<platform>/<config>/outputs/DET-012_unsupported_version.json` (see `determinism_evidence_bundle_v1_0.md`) |
| DET-013 | undefined_behavior_v1_0.md [DET-013] | `axiom_ruledsl_identifier_class_conformance_tests` | `reports/determinism_v1_0/<date>/<platform>/<config>/outputs/DET-013_non_normalized_input.json` (see `determinism_evidence_bundle_v1_0.md`) |
| DET-014 | undefined_behavior_v1_0.md [DET-014] | TBD | `reports/determinism_v1_0/<date>/<platform>/<config>/outputs/DET-014_input_mutation_race.json` (see `determinism_evidence_bundle_v1_0.md`) |
| DET-015 | undefined_behavior_v1_0.md [DET-015] | `Tools/smoke/compiler_smoke_test.ps1` | `reports/determinism_v1_0/<date>/<platform>/<config>/outputs/DET-015_invalid_args.json` (see `determinism_evidence_bundle_v1_0.md`) |
| DET-016 | TBD |  |  |
| DET-017 | TBD |  |  |
| DET-018 | TBD |  |  |
| DET-019 | TBD |  |  |
| DET-020 | TBD |  |  |
| DET-021 | TBD |  |  |
| DET-022 | TBD |  |  |
| DET-023 | TBD |  |  |
| DET-024 | TBD |  |  |
| DET-025 | TBD |  |  |
| DET-026 | TBD |  |  |
| DET-027 | TBD |  |  |
| DET-028 | TBD |  |  |
| DET-029 | TBD |  |  |
| DET-030 | TBD |  |  |
| DET-031 | TBD |  |  |
| DET-032 | TBD |  |  |
| DET-033 | TBD |  |  |
| DET-034 | TBD |  |  |
| DET-035 | TBD |  |  |
| DET-036 | TBD |  |  |
| DET-037 | TBD |  |  |
| DET-038 | TBD |  |  |
| DET-039 | TBD |  |  |
| DET-040 | TBD |  |  |
| DET-041 | TBD |  |  |
| DET-042 | TBD |  |  |
| DET-043 | TBD |  |  |
| DET-044 | TBD |  |  |
| DET-045 | TBD |  |  |
| DET-046 | TBD |  |  |
| DET-047 | TBD |  |  |
| DET-048 | TBD |  |  |
| DET-049 | TBD |  |  |
| DET-050 | TBD |  |  |
