# RuleDSL v1.0 Decision Rules Profile (Baseline)

This document defines the v1.0 baseline language profile for decision-rule authoring.

## 1) Profile Name and Scope

- [VER-0007] The v1.0 baseline profile SHALL be named `decision-rules-v1.0` and SHALL define the profile-scoped keyword surface used by baseline lexing/parsing.

## 2) Profile-contributed Reserved Keywords

- [SYN-0019] The Decision Rules profile keyword set SHALL be exactly: `allow`, `decline`, `review`, `limit`, `per`.
- [SYN-0020] No additional profile-scoped reserved keywords are defined for `decision-rules-v1.0`.

## 3) High-level Syntactic Intent (Non-normative)

- `allow`, `decline`, and `review` denote decision outcomes.
- `limit` and `per` denote limit-window style rule constructs.

Normative parsing/lexing binding:

- [SEM-0031] When `decision-rules-v1.0` is active, lexer and parser SHALL classify ASCII case-insensitive profile-keyword matches as reserved tokens and SHALL NOT classify those matches as identifiers.

## 4) Profile Activation and Selection in v1.0

- [VER-0008] v1.0 language mode SHALL activate `decision-rules-v1.0` as the baseline profile.
- [VER-0009] v1.0 SHALL NOT support selecting alternative profiles.

## 5) Decision Resolution (Non-normative)

This section describes the shipped v0.9 evaluation behavior; see [conformance_status_v0_9.md](conformance_status_v0_9.md) for the full conformance record.

- The first rule whose `when` condition is true wins, and evaluation stops at that rule.
- This includes assign-only rules: an assign-only rule (one that only assigns and never reaches `allow`/`decline`/`review`/`limit`) with a broad `when` **shadows** any lower-priority decision rule. The outcome is `matched = true` with the profile default action (`review`) and an empty/`NULL` `rule_name`.
- The `limit` decision **expresses** a velocity cap (an amount and a `per` window); it does not enforce anything by itself. The engine is stateless and does not track cumulative spend — the host system enforces the cap. `now_utc_ms` must be supplied for a `limit` rule and is validated as present and numeric, but is not used computationally in v0.9.
