# RuleDSL v0.9 Numeric Model Annex

This annex defines concrete numeric behavior for v0.9 and binds section 6 of `docs/language/spec_v0_9.md`.

## 1) Number Representation

- [SEM-0009] The language Number value SHALL be IEEE 754 binary64.
- [SEM-0017] Exponent-form numeric literals (`e`/`E`) SHALL NOT be part of the v0.9 language surface and SHALL be rejected at compile time.

## 2) Rounding and Arithmetic Environment

- [DET-0014] The effective rounding mode during evaluation SHALL be round-to-nearest, ties-to-even.
- [ERR-0008] If the runtime environment cannot guarantee the required rounding-mode behavior, evaluation SHALL fail with a defined numeric-environment runtime error.

## 3) Non-finite Value Policy

- [SEM-0010] Non-finite numeric inputs (`NaN`, `+Inf`, `-Inf`) SHALL be rejected with a defined error outcome before arithmetic evaluation.
- [SEM-0011] If any arithmetic operation yields a non-finite result, evaluation SHALL terminate with a defined non-finite runtime error.

## 4) Overflow, Underflow, and Subnormals

- [SEM-0012] Finite overflow SHALL produce a defined runtime overflow error; silent saturation and wraparound are forbidden.
- [SEM-0013] Underflow SHALL follow IEEE 754 binary64 behavior, including subnormal values when representable.

## 5) Determinism-critical Build/Runtime Constraints

- [DET-0015] Compiler and runtime settings SHALL disable fast-math style transformations that can alter observable numeric outcomes.
- [DET-0016] Arithmetic evaluation SHALL avoid reassociation, contraction, or excess-precision modes that change externally observable results.

## 6) Non-normative Examples

Example A (overflow):

Multiplying sufficiently large finite operands results in a runtime overflow error.

Example B (non-finite result):

`x / 0` with finite non-zero `x` results in a non-finite runtime error instead of producing `+Inf` or `-Inf` as a language value.


## 7) Numeric Error Taxonomy

The numeric taxonomy uses stable symbolic identifiers with the namespace `ERR.RUNTIME.<TOKEN>`.

- [ERR-0009] Numeric runtime taxonomy identifiers SHALL use the `ERR.RUNTIME.<TOKEN>` namespace and SHALL preserve identifier meaning across compatible versions.
- [ERR-0010] When a finite operation overflows, evaluation SHALL raise `ERR.RUNTIME.NUMERIC_OVERFLOW`; classification is runtime error and identifier meaning SHALL remain stable.
- [ERR-0011] When an operation yields a non-finite numeric result, evaluation SHALL raise `ERR.RUNTIME.NUMERIC_NONFINITE_RESULT`; classification is runtime error and identifier meaning SHALL remain stable.
- [ERR-0012] When required numeric-environment constraints (including rounding mode) are not satisfied, evaluation SHALL raise `ERR.RUNTIME.NUMERIC_ENVIRONMENT_MISMATCH`; classification is runtime error and identifier meaning SHALL remain stable.

## 8) Compile-time Constant Folding

Constant folding is optional but constrained by runtime-equivalence rules.

- [SEM-0014] The compiler MAY perform constant folding for expressions that are compile-time constants.
- [DET-0017] If constant folding is performed, folded results SHALL obey the same numeric constraints as runtime evaluation, including rounding behavior, non-finite policy, overflow policy, and underflow/subnormal policy.
- [SEM-0015] The compiler SHALL NOT emit a folded result when equivalence to constrained runtime evaluation cannot be established.
- [SEM-0016] If safe folding cannot be established, the compiler MAY keep the expression for runtime evaluation or MAY emit a compile-time error with a defined diagnostic outcome.
