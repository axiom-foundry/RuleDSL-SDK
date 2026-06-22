# RuleDSL v0.9 Engine Conformance Status

The v1.0 specification documents (`spec_v1_0.md` and the language annexes) define the
normative **target**. The shipped v0.9 engine implements the subset described below;
every known deviation from the v1.0 target is listed explicitly. The engine's behavior
is **deliberate and deterministic** — the same bytecode evaluated against the same
explicit inputs always yields the same decision. This page is the authoritative record
of where the shipped engine matches the v1.0 target and where it does not.

> **Status:** descriptive (engine behavior), not normative. Where this page and a v1.0
> annex disagree, the annex states the *target* and this page states the *shipped v0.9
> behavior*.

## 1. Conformant

The shipped engine matches the v1.0 target for these requirements (several are covered
by the strict conformance test suites — `logical_ops`, `keyword_case`,
`identifier_class`, `numeric_literal`):

- **Numeric model:** Number is IEEE 754 binary64 (SEM-0009); rounding is
  round-to-nearest-ties-to-even at the platform IEEE default (DET-0014).
- **Lexical surface:** ASCII-only identifiers with Unicode rejection (SYN-0012);
  numeric literal forms including exponent, and the `.5` / `5.` rejection (SYN-0015,
  SYN-0016, SYN-0017); whitespace treatment (SYN-0007/0008/0009); keyword set and
  ASCII case-insensitive keyword matching with case-sensitive identifiers
  (SEM-0030, SEM-0031); unary sign is literal-position only.
- **Comments:** all three forms `#`, `//`, `/* … */` are accepted; block comments do
  not nest (first `*/` closes); an unterminated block comment is a compile-time failure
  (SYN-0010, SYN-0011, ERR-0026).
- **Strings & identifiers:** string equality is byte-exact over UTF-8 octets (SEM-0019);
  identifier lookup/equality uses octet matching with no Unicode normalization and is
  independent of host map iteration order (SEM-0024/0025/0026, DET-0021).

> Note: the *behavior* above is conformant, but compile/runtime error **identity**
> (naming) differs from the spec's symbolic taxonomy — see §3.

## 2. Divergences (v1.0 target → shipped v0.9 behavior)

All behaviors below are deterministic; they differ from the v1.0 *target* semantics.

| Requirement | v1.0 target | Shipped v0.9 engine (probe-verified) |
|---|---|---|
| SEM-0022 | Numeric ordering uses exact IEEE 754 comparison | Ordering/equality use a **relative epsilon** tolerance (`1e-9` × `max(1, |a|, |b|)`); thresholds are "fuzzy" near ~1e-9 (e.g. a value 1e-10 above a bound is treated as equal). |
| TYP-0002 / TYP-0006, SEM-0017, ERR-0013 | No implicit coercion; condition context accepts only Boolean; a non-Boolean condition raises a condition-type error | Condition context applies **dynamic truthiness coercion** via `to_bool` (Number: `false` when within epsilon of 0; String/Ident: `false` when empty; Missing: `false`); **no condition-type error exists**. |
| SEM-0018 / ERR-0014, SEM-0021 / ERR-0016 | Cross-type `==`/`!=` and ordering raise a type-mismatch error | Cross-type comparisons are **silent**: `==`/`<`/`<=`/`>`/`>=` → `false`, `!=` → `true`; no error, no trace. |
| SEM-0020 | `missing == missing` → `true` | `missing == missing` → **`false`** (missing equals nothing, including another missing); `missing != missing` → `true`. |
| ERR-0020 | A missing operand raises `MISSING_OPERAND` and halts | **Advisory + graceful degradation, never halts:** comparison → `false`; arithmetic → `TYPE_MISMATCH` and a missing result; assignment → `ASSIGN_VALUE_MISSING`; an absent field path → `UNKNOWN_PATH`. All map to `AX_ERR_RUNTIME=11`, the decision is still populated, and evaluation continues. |
| SEM-0004 | Conditional evaluation SHALL short-circuit | `and`/`or` **evaluate both operands**; a runtime error in the right operand surfaces even when the left already determines the result. |
| ERR-0010 | Overflow raises a distinct `NUMERIC_OVERFLOW` | Overflow / Inf / NaN all fold into a single finiteness guard → `NON_FINITE` (`AX_ERR_NON_FINITE=6`); there is no distinct overflow code. (An over-large numeric *literal* is rejected earlier, at compile time.) |
| ERR-0008 / ERR-0012 | A runtime numeric-environment check raises `NUMERIC_ENVIRONMENT_MISMATCH` | **Not implemented.** Determinism is enforced only by a compile-time anti-fast-math guard (`#error` on `__FAST_MATH__`; CMake rejects `-ffast-math`/`-Ofast`); there is no runtime rounding-mode/`fenv` check. |
| TYP-0003 / TYP-0004 | Statically detectable type violations fail at compile time | **No static type checking** — type compatibility is fully dynamic; mismatches surface only at runtime (`TYPE_MISMATCH`). Some string-in-arithmetic forms are rejected at compile time, but as *grammar/parse* errors, not type errors. |

## 3. Error-identity taxonomy (shipped mapping)

The v1.0 specs use symbolic `ERR.RUNTIME.<TOKEN>` / `ERR.COMPILE.<TOKEN>` identities. The
shipped engine emits a trace string code and maps it to the frozen public `AX_ERR_*`
numeric enum (first runtime error wins). The distinct symbolic taxonomy is **not yet
implemented**; several runtime tokens collapse onto the generic `AX_ERR_RUNTIME=11`, and
every compile/lex/parse failure collapses onto `AX_ERR_COMPILE=2` with a free-text
message.

**Runtime** (trace `RuntimeError(<TOKEN>)` → `AX_ERR_*`):

| Engine token | `AX_ERR_*` (numeric) |
|---|---|
| `NON_FINITE` | `AX_ERR_NON_FINITE` (6) |
| `DIV_ZERO` | `AX_ERR_DIV_ZERO` (7) |
| `MISSING_NOW_UTC_MS` | `AX_ERR_MISSING_NOW_UTC_MS` (4) |
| `NOW_UTC_MS_NOT_NUMBER` | `AX_ERR_NOW_UTC_MS_NOT_NUMBER` (5) |
| `LIMIT_FUEL`, `LIMIT_LIST` | `AX_ERR_LIMIT_EXCEEDED` (9) |
| `CONCURRENT_COMPILER_USE` | `AX_ERR_CONCURRENT_COMPILER_USE` (8) |
| `UNKNOWN_PATH`, `TYPE_MISMATCH`, `MATCH_EXPECTS_TEXT`, `ASSIGN_VALUE_MISSING`, `INVALID_TIME_WINDOW` | `AX_ERR_RUNTIME` (11, generic) |

Note: `UNARY_EXPECTS_NUMBER` is emitted only by the internal AST oracle; the shipped
bytecode path silently yields a missing value for a non-numeric unary operand.

**Compile / lex / parse:** every failure → `AX_ERR_COMPILE=2` with a free-text message,
e.g. `Parse error, expected: …`, `Lex error`, `Unterminated block comment`,
`LIMIT_DEPTH`, `LIMIT_TOKENS`, `LIMIT_STRING`, `Missing expression`,
`Unsupported expression`. No symbolic `ERR.COMPILE.<TOKEN>` identities are emitted.

## 4. String escape behavior (v0.9)

The string-lexing surface (see `string_lexing_v1_0.md`) recognizes the escapes
`\n` `\t` `\r` `\"` `\\`. An **unknown escape is lenient**: the backslash is dropped and
the following character is kept verbatim, with no error (e.g. `"x\zy"` lexes to `xzy`).
An unterminated string literal is a compile-time failure, and the maximum string length
is 4096 bytes (`LIMIT_STRING`). This lenient pass-through diverges from the older
"unknown escape is an error" aspiration.

## 5. Decision resolution (v0.9)

The first rule whose `when` condition is true wins and evaluation stops. This includes
assign-only rules: an assign-only rule with a broad `when` **shadows** any lower-priority
decision rule — the outcome is `matched = true` with the profile default action
(`review`) and an empty/`NULL` `rule_name` (see `profile_decision_rules_v1_0.md` §5).
