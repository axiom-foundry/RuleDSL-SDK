# RuleDSL Bytecode Workflow (v0.9)

## 1. Overview

Rule sets are authored in the RuleDSL language (see `docs/language/`).
Those rules are compiled into deterministic bytecode artifacts (for example, `.axbc`).
The RuleDSL runtime then loads and evaluates bytecode through the public C API.

The bytecode format is versioned.
The bytecode format is intentionally undocumented at structural level.
The bytecode format is not a public stability contract.

## 2. Compilation Flow

```text
rule.dsl
   ->
RuleDSL Compiler (licensed binary)
   ->
rule.axbc
   ->
ruledslc verify
   ->
C API (ax_check_bytecode_compatibility -> ax_eval_bytecode)
```

This flow is the supported producer/consumer path for v0.9 distribution.
Public documentation defines behavior and compatibility expectations, not byte-level encoding details.

## 3. Determinism Model

Determinism applies to evaluation semantics.
For a fixed compiler version, equivalent DSL input produces equivalent bytecode semantics.
Deterministic semantics do not imply a stable byte-level binary layout across different versions.

## 4. Versioning

Bytecode interoperability is governed by multiple version dimensions:

- Language version (`v0.9`) defines the rule language contract.
- Compiler version defines the producer behavior for bytecode artifacts.
- Engine version defines the consumer behavior for loading and evaluation.
- Bytecode version is embedded in the artifact and validated by the engine.
- Incompatible bytecode versions are rejected by the engine.

## 5. Security & Encapsulation

The bytecode format is intentionally opaque.
Users should not generate, patch, or transform bytecode manually.
The official RuleDSL compiler is the only supported bytecode producer.
