# RuleDSL v0.9 Decision Rules Profile (Baseline)

This document defines the v0.9 baseline language profile for decision-rule authoring.

## 1) Profile Name and Scope

- [VER-0007] The v0.9 baseline profile SHALL be named `decision-rules-v0.9` and SHALL define the profile-scoped keyword surface used by baseline lexing/parsing.

## 2) Profile-contributed Reserved Keywords

- [SYN-0019] The Decision Rules profile keyword set SHALL be exactly: `allow`, `decline`, `review`, `limit`, `per`.
- [SYN-0020] No additional profile-scoped reserved keywords are defined for `decision-rules-v0.9`.

## 3) High-level Syntactic Intent (Non-normative)

- `allow`, `decline`, and `review` denote decision outcomes.
- `limit` and `per` denote limit-window style rule constructs.

Normative parsing/lexing binding:

- [SEM-0031] When `decision-rules-v0.9` is active, lexer and parser SHALL classify ASCII case-insensitive profile-keyword matches as reserved tokens and SHALL NOT classify those matches as identifiers.

## 4) Profile Activation and Selection in v0.9

- [VER-0008] v0.9 language mode SHALL activate `decision-rules-v0.9` as the baseline profile.
- [VER-0009] v0.9 SHALL NOT support selecting alternative profiles.
