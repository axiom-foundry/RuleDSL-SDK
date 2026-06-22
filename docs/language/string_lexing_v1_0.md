# String Lexing (v1.0)

> **Status:** descriptive (shipped v0.9 behavior), not normative. The broader lexical
> contract is in [lexical_core_v1_0.md](lexical_core_v1_0.md) and
> [spec_v1_0.md](spec_v1_0.md); related syntax context is in
> [grammar_v1_0.md](grammar_v1_0.md).

## String literals (v0.9)

- **Delimiter:** a string literal is enclosed in double quotes (`"`).
- **Recognized escapes:** `\n` (newline), `\t` (tab), `\r` (carriage return), `\"` (double quote), `\\` (backslash).
- **Unknown escapes are lenient:** for any other `\X`, the backslash is dropped and the following character is kept verbatim, with no error — e.g. `"x\zy"` lexes to `xzy`.
- **Unterminated literal:** a string with no closing `"` is a compile-time failure.
- **Maximum length:** 4096 bytes; a longer literal fails with `LIMIT_STRING`.

The lenient unknown-escape pass-through diverges from the older "unknown escape is an error" aspiration; the shipped status is recorded in [conformance_status_v0_9.md](conformance_status_v0_9.md).