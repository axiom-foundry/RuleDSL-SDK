# RuleDSL Language Grammar v0.9

## 1. Status & Scope

This grammar defines the syntactic surface for language version v0.9 with active profile `decision-rules-v0.9`.

This document defines syntax only. Semantic behavior is defined by language annexes, and determinism constraints remain binding. Keyword spellings shown here are canonical forms; lexical matching follows ASCII case-insensitive keyword rules.

## 2. Token Inventory

### 2.1 Core Tokens

- [SYN-TOK-001] `IDENTIFIER` SHALL denote identifier tokens defined by lexical core rules.
- [SYN-TOK-002] `NUMBER` SHALL denote numeric literal tokens defined by lexical core rules.
- [SYN-TOK-003] `STRING` SHALL denote string literal tokens defined by string-lexing rules.
- [SYN-TOK-004] `BOOLEAN` SHALL denote the boolean literal tokens `true` and `false`.
- [SYN-TOK-005] `rule` SHALL be recognized as a core keyword token.
- [SYN-TOK-006] `when` SHALL be recognized as a core keyword token.
- [SYN-TOK-007] `then` SHALL be recognized as a core keyword token.
- [SYN-TOK-008] `+` SHALL be recognized as the PLUS token.
- [SYN-TOK-009] `-` SHALL be recognized as the MINUS token.
- [SYN-TOK-010] `*` SHALL be recognized as the STAR token.
- [SYN-TOK-011] `/` SHALL be recognized as the SLASH token.
- [SYN-TOK-012] `%` SHALL be recognized as the PERCENT token.
- [SYN-TOK-013] `==` SHALL be recognized as an equality operator token.
- [SYN-TOK-014] `!=` SHALL be recognized as an equality operator token.
- [SYN-TOK-015] `<` SHALL be recognized as a relational operator token.
- [SYN-TOK-016] `<=` SHALL be recognized as a relational operator token.
- [SYN-TOK-017] `>` SHALL be recognized as a relational operator token.
- [SYN-TOK-018] `>=` SHALL be recognized as a relational operator token.
- [SYN-TOK-019] `and` SHALL be recognized as a logical-AND operator token.
- [SYN-TOK-020] `or` SHALL be recognized as a logical-OR operator token.
- [SYN-TOK-021] `not` SHALL be recognized as a unary logical-negation token.
- [SYN-TOK-022] `(` SHALL be recognized as punctuation token LPAREN.
- [SYN-TOK-023] `)` SHALL be recognized as punctuation token RPAREN.
- [SYN-TOK-024] `{` SHALL be recognized as punctuation token LBRACE.
- [SYN-TOK-025] `}` SHALL be recognized as punctuation token RBRACE.
- [SYN-TOK-026] `;` SHALL be recognized as punctuation token SEMICOLON.
- [SYN-TOK-027] `,` SHALL be recognized as punctuation token COMMA.

### 2.2 Operator Precedence

The following precedence levels SHALL apply:

- PLUS and MINUS SHALL have additive precedence.
- STAR, SLASH, and PERCENT SHALL have multiplicative precedence.
- Multiplicative precedence SHALL be higher than additive precedence.
- Binary operators at the same precedence level SHALL associate left-to-right.

Note: This subsection defines parsing precedence classes. Token identity is defined in the Token Inventory.

### 2.3 Profile Tokens (`decision-rules-v0.9`)

- [SYN-TOK-028] `allow` SHALL be recognized as an active profile keyword token.
- [SYN-TOK-029] `decline` SHALL be recognized as an active profile keyword token.
- [SYN-TOK-030] `review` SHALL be recognized as an active profile keyword token.
- [SYN-TOK-031] `limit` SHALL be recognized as an active profile keyword token.
- [SYN-TOK-032] `per` SHALL be recognized as an active profile keyword token.

## 3. Operator Precedence and Associativity

Highest to lowest precedence:

- [SYN-PREC-001] Unary logical negation (`not`) SHALL bind at the highest precedence and SHALL be right-associative.
- [SYN-PREC-002] Multiplicative operators (`*`, `/`, `%`) SHALL be left-associative.
- [SYN-PREC-003] Additive operators (`+`, `-`) SHALL be left-associative.
- [SYN-PREC-004] Relational operators (`<`, `<=`, `>`, `>=`) SHALL be left-associative.
- [SYN-PREC-005] Equality operators (`==`, `!=`) SHALL be left-associative.
- [SYN-PREC-006] Logical AND (`and`) SHALL be left-associative.
- [SYN-PREC-007] Logical OR (`or`) SHALL be left-associative and SHALL have the lowest precedence.

## 4. EBNF Grammar

Condition contexts reference `Expression`; type and coercion constraints are defined outside this grammar.

`[SYN-GRAM-001]` (Conformance placeholder: see `docs/language/conformance_map.md`)  
`Program ::= { RuleBlock } ;`

`[SYN-GRAM-002]` (Conformance placeholder: see `docs/language/conformance_map.md`)  
`RuleBlock ::= "rule" IDENTIFIER "{" "when" Expression ";" "then" DecisionStatement [ "," LimitClause ] ";" "}" ;`

`[SYN-GRAM-003]` (Conformance placeholder: see `docs/language/conformance_map.md`)  
`DecisionStatement ::= "allow" | "decline" | "review" ;`

`[SYN-GRAM-004]` (Conformance placeholder: see `docs/language/conformance_map.md`)  
`LimitClause ::= "limit" NUMBER "per" IDENTIFIER ;`

`[SYN-GRAM-005]` (Conformance placeholder: see `docs/language/conformance_map.md`)  
`Expression ::= LogicalOr ;`

`[SYN-GRAM-006]` (Conformance placeholder: see `docs/language/conformance_map.md`)  
`LogicalOr ::= LogicalAnd { "or" LogicalAnd } ;`

`[SYN-GRAM-007]` (Conformance placeholder: see `docs/language/conformance_map.md`)  
`LogicalAnd ::= Equality { "and" Equality } ;`

`[SYN-GRAM-008]` (Conformance placeholder: see `docs/language/conformance_map.md`)  
`Equality ::= Relational { ( "==" | "!=" ) Relational } ;`

`[SYN-GRAM-009]` (Conformance placeholder: see `docs/language/conformance_map.md`)  
`Relational ::= Additive { ( "<" | "<=" | ">" | ">=" ) Additive } ;`

`[SYN-GRAM-010]` (Conformance placeholder: see `docs/language/conformance_map.md`)  
`Additive ::= Multiplicative { ( "+" | "-" ) Multiplicative } ;`

`[SYN-GRAM-011]` (Conformance placeholder: see `docs/language/conformance_map.md`)  
`Multiplicative ::= Unary { ( "*" | "/" | "%" ) Unary } ;`

`[SYN-GRAM-012]` (Conformance placeholder: see `docs/language/conformance_map.md`)  
`Unary ::= "not" Unary | "-" Unary | Primary ;`

`[SYN-GRAM-013]` (Conformance placeholder: see `docs/language/conformance_map.md`)  
`Primary ::= NUMBER | STRING | BOOLEAN | IDENTIFIER | "(" Expression ")" ;`

## 5. Profile -> Grammar Mapping Appendix

- `allow` maps to `DecisionStatement(kind=ALLOW)`.
- `decline` maps to `DecisionStatement(kind=DECLINE)`.
- `review` maps to `DecisionStatement(kind=REVIEW)`.
- `limit` + `per` map to `LimitClause` (`limit` quantity and `per` scope identifier).
- Only keywords in `decision-rules-v0.9` participate in these mappings for v0.9 baseline grammar.
