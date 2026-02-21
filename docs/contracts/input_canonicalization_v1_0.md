# Input Canonicalization (v1.0)

This document defines the canonical input normalization contract referenced by the RuleDSL 1.0 determinism contract.

## 1. Canonicalization scope

- [DET-021] Callers MUST canonicalize evaluation input before passing fields to the public C API when determinism evidence is claimed.
- [DET-022] Canonicalization MUST be locale-independent and timezone-independent.
- [DET-023] Canonicalization MUST be applied consistently across Windows x64 and Linux x64 execution paths.

## 2. Field ordering

- [DET-024] Canonical field ordering SHALL be ascending byte-wise lexicographic order over UTF-8 key bytes.
- [DET-025] Ordering comparisons MUST use raw byte comparison and MUST NOT use locale collation or Unicode normalization.
- [DET-026] When nested field paths are represented as flattened keys, ordering SHALL apply to the fully qualified key bytes.

## 3. Duplicate keys policy

- [DET-027] Duplicate keys in the same normalized input payload MUST be rejected.
- [DET-028] Deterministic resolution by "first wins" or "last wins" MUST NOT be used in RuleDSL 1.0 determinism evidence.

## 4. Numeric canonicalization

- [DET-029] Decimal text normalization MUST use `.` as the decimal separator.
- [DET-030] Numeric parsing MUST NOT depend on locale-specific grouping or decimal separators.
- [DET-031] `NaN`, `+Inf`, and `-Inf` input values MUST be rejected.
- [DET-032] Numeric values SHOULD be normalized to a stable decimal representation before conversion to runtime numeric form.

## 5. String canonicalization

- [DET-033] Input strings MUST be valid UTF-8 octet sequences.
- [DET-034] Canonicalization MUST NOT apply Unicode normalization (NFC/NFD/NFKC/NFKD).
- [DET-035] Canonicalization MUST preserve string bytes exactly after UTF-8 validation.

## 6. Time and locale independence

- [DET-036] Canonicalization MUST NOT read system timezone or locale settings.
- [DET-037] If a time value is needed by policy, it MUST be caller-supplied in explicit numeric form and MUST NOT be inferred from wall-clock state.

## 7. Output of canonicalization

- [DET-038] Canonicalization output SHOULD be auditable with stable serialization order for determinism evidence generation.
- [DET-039] Canonicalization failures MUST be treated as input errors and SHOULD be surfaced before evaluation.
