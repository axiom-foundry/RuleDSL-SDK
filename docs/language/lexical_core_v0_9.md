# RuleDSL v0.9 Lexical Core Annex

This annex defines lexical core behavior for whitespace, comments, identifiers, keywords, and numeric literals.

## 1) Whitespace and Newline Treatment

- [SYN-0007] The lexical whitespace set SHALL be exactly: space (U+0020), horizontal tab (U+0009), carriage return (U+000D), and line feed (U+000A).
- [SYN-0008] Whitespace outside string literals and comments SHALL act only as token separators and SHALL have no standalone semantic value.
- [SYN-0009] Newline characters SHALL NOT imply statement termination unless a separate normative syntax rule explicitly defines it.

## 2) Comment Syntax

- [SYN-0010] Comment syntax in v0.9 SHALL be limited to the compatibility surface `#...<newline>`, `//...<newline>`, and `/*...*/`; no additional comment delimiters or forms are allowed.
- [SYN-0011] Block comments (`/*...*/`) SHALL NOT nest and SHALL terminate at the first subsequent `*/`.
- [ERR-0026] Unterminated block comments SHALL cause compile-time failure with `ERR.COMPILE.UNTERMINATED_BLOCK_COMMENT`; identifier meaning SHALL remain stable across compatible versions.

## 3) Identifiers and Keywords

- [SYN-0012] Identifier tokens SHALL match the ASCII grammar `[A-Za-z_][A-Za-z0-9_]*`.
- [SYN-0013] Unicode identifier characters outside the ASCII grammar SHALL be out of scope for v0.9 and SHALL be rejected as lexical errors.
- [DET-0024] Identifier lexing and keyword classification SHALL use ASCII rules only and SHALL NOT depend on locale.
- [SYN-0017] Core reserved keywords for lexical core v0.9 SHALL be exactly: `rule`, `priority`, `when`, `then`, `or`, `and`, `not`, `in`, `match`, `true`, `false`; these spellings are canonical documentation forms.
- [SYN-0018] Domain/profile-specific keywords SHALL be out of scope for lexical core v0.9 and SHALL be specified only by an active profile document.
Profile keywords for the v0.9 baseline are canonically defined by `docs/language/profile_decision_rules_v0_9.md`.
- [SYN-0014] DEPRECATED: the previous single combined keyword-list rule SHALL be retained only for historical traceability and SHALL NOT be used for new conformance claims.
- [SEM-0030] Keyword-versus-identifier resolution SHALL perform ASCII case-insensitive matching for reserved keywords from the core set and any active profile set, and keyword matches SHALL take precedence over identifier token classification; identifier tokens SHALL remain case-sensitive octet sequences.

## 4) Numeric Literal Lexical Forms

- [SYN-0015] Numeric literals in v0.9 SHALL use only these lexical forms: decimal integer (`[0-9]+`) and decimal fraction (`[0-9]+\.[0-9]+`). Exponent forms (`e`/`E`) are out-of-contract for v0.9 and SHALL be rejected at compile time.
- [SYN-0016] Leading sign characters (`+` or `-`) SHALL NOT be part of a numeric literal token and SHALL be parsed by expression grammar as unary operators.
- [ERR-0027] Malformed numeric literal text and unsupported exponent-form literals SHALL cause compile-time failure with `ERR.COMPILE.INVALID_NUMERIC_LITERAL`; identifier meaning SHALL remain stable across compatible versions.

## 5) Generic Lexical Error Handling

- [ERR-0028] Any source octet sequence that cannot be tokenized by v0.9 lexical rules SHALL cause compile-time failure with `ERR.COMPILE.INVALID_TOKEN`; identifier meaning SHALL remain stable across compatible versions.

## 6) Compile-time Lexical Error Taxonomy

Compile-time lexical diagnostics in this annex use the `ERR.COMPILE.<TOKEN>` namespace.

- [ERR-0029] Lexical compile-time error identifiers SHALL use `ERR.COMPILE.<TOKEN>` and SHALL preserve identifier meaning across compatible versions.

Taxonomy entries:

- `ERR.COMPILE.UNTERMINATED_BLOCK_COMMENT`
  - Trigger: `/*` comment reaches end-of-source without `*/`.
  - Classification: compile-time error.
  - Stability: symbolic identifier meaning is stable across compatible versions.
- `ERR.COMPILE.INVALID_NUMERIC_LITERAL`
  - Trigger: numeric token text does not match an allowed numeric-literal form.
  - Classification: compile-time error.
  - Stability: symbolic identifier meaning is stable across compatible versions.
- `ERR.COMPILE.INVALID_TOKEN`
  - Trigger: source text contains a token not recognized by v0.9 lexical rules.
  - Classification: compile-time error.
  - Stability: symbolic identifier meaning is stable across compatible versions.
