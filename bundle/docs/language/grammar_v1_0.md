# RuleDSL Language Grammar v1.0

## 1. Status & Scope

This grammar defines the syntactic surface for language version v1.0 with active profile `decision-rules-v1.0`.

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
- [SYN-TOK-012] _Reserved — removed from v0.9 baseline._
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
- [SYN-TOK-028] `=` SHALL be recognized as the assignment operator token.
- [SYN-TOK-029] `[` SHALL be recognized as punctuation token LBRACKET.
- [SYN-TOK-030] `]` SHALL be recognized as punctuation token RBRACKET.

### 2.2 Core Keyword Tokens

- [SYN-TOK-040] `priority` SHALL be recognized as a core keyword token.
- [SYN-TOK-041] `in` SHALL be recognized as a core keyword token.
- [SYN-TOK-042] `match` SHALL be recognized as a core keyword token.

### 2.3 Operator Precedence

The following precedence levels apply:

- PLUS and MINUS use additive precedence.
- STAR and SLASH use multiplicative precedence.
- Multiplicative precedence is higher than additive precedence.
- Binary operators at the same precedence level associate left-to-right.

Note: This subsection defines parsing precedence classes. Token identity is defined in the Token Inventory.

### 2.4 Profile Tokens (`decision-rules-v1.0`)

- [SYN-TOK-050] `allow` SHALL be recognized as an active profile keyword token.
- [SYN-TOK-051] `decline` SHALL be recognized as an active profile keyword token.
- [SYN-TOK-052] `review` SHALL be recognized as an active profile keyword token.
- [SYN-TOK-053] `limit` SHALL be recognized as an active profile keyword token.
- [SYN-TOK-054] `per` SHALL be recognized as an active profile keyword token.

## 3. Operator Precedence and Associativity

Highest to lowest precedence:

- [SYN-PREC-001] Unary logical negation (`not`) SHALL bind at the highest precedence and SHALL be right-associative.
- [SYN-PREC-002] Multiplicative operators (`*`, `/`) SHALL be left-associative.
- [SYN-PREC-003] Additive operators (`+`, `-`) SHALL be left-associative.
- [SYN-PREC-004] Relational operators (`<`, `<=`, `>`, `>=`) SHALL be left-associative.
- [SYN-PREC-005] Membership (`in`) and substring (`match`) operators SHALL be non-associative.
- [SYN-PREC-006] Equality operators (`==`, `!=`) SHALL be left-associative.
- [SYN-PREC-007] Logical AND (`and`) SHALL be left-associative.
- [SYN-PREC-008] Logical OR (`or`) SHALL be left-associative and SHALL have the lowest precedence.

## 4. EBNF Grammar

Condition contexts reference `Expression`; type and coercion constraints are defined outside this grammar.

`[SYN-GRAM-001]`
`Program ::= { RuleBlock } ;`

`[SYN-GRAM-002]`
`RuleBlock ::= "rule" IDENTIFIER [ "priority" NUMBER ] "{" "when" Expression ";" "then" ThenClause ";" "}" ;`

`[SYN-GRAM-003]`
`ThenClause ::= ThenItem { "," ThenItem } ;`

`[SYN-GRAM-004]`
`ThenItem ::= Assignment | DecisionStatement | LimitClause ;`

`[SYN-GRAM-005]`
`Assignment ::= IDENTIFIER "=" Expression ;`

`[SYN-GRAM-006]`
`DecisionStatement ::= "allow" | "decline" | "review" ;`

`[SYN-GRAM-007]`
`LimitClause ::= "limit" NUMBER [ IDENTIFIER ] "per" NUMBER IDENTIFIER ;`

`[SYN-GRAM-008]`
`Expression ::= LogicalOr ;`

`[SYN-GRAM-009]`
`LogicalOr ::= LogicalAnd { "or" LogicalAnd } ;`

`[SYN-GRAM-010]`
`LogicalAnd ::= Equality { "and" Equality } ;`

`[SYN-GRAM-011]`
`Equality ::= Membership { ( "==" | "!=" ) Membership } ;`

`[SYN-GRAM-012]`
`Membership ::= Relational [ "in" ListLiteral | "match" Primary ] ;`

`[SYN-GRAM-013]`
`Relational ::= Additive { ( "<" | "<=" | ">" | ">=" ) Additive } ;`

`[SYN-GRAM-014]`
`Additive ::= Multiplicative { ( "+" | "-" ) Multiplicative } ;`

`[SYN-GRAM-015]`
`Multiplicative ::= Unary { ( "*" | "/" ) Unary } ;`

`[SYN-GRAM-016]`
`Unary ::= "not" Unary | "-" Unary | Primary ;`

`[SYN-GRAM-017]`
`Primary ::= NUMBER [ IDENTIFIER ] | STRING | BOOLEAN | IDENTIFIER | "(" Expression ")" ;`

`[SYN-GRAM-018]`
`ListLiteral ::= "[" ListElement { "," ListElement } "]" ;`

`[SYN-GRAM-019]`
`ListElement ::= IDENTIFIER | STRING | NUMBER ;`

## 5. Profile -> Grammar Mapping Appendix

- `allow` maps to `DecisionStatement(kind=ALLOW)`.
- `decline` maps to `DecisionStatement(kind=DECLINE)`.
- `review` maps to `DecisionStatement(kind=REVIEW)`.
- `limit` + `per` map to `LimitClause` (`limit` quantity with optional currency tag and `per` window with time-unit identifier).
- `priority` maps to optional priority annotation on `RuleBlock`.
- `in` maps to `Membership` list-membership test.
- `match` maps to `Membership` substring-match test.
- Only keywords in `decision-rules-v1.0` participate in these mappings for v1.0 grammar.

## 6. Currency and Time-Unit Conventions (Non-normative)

Currency tags on numeric literals (e.g., `1000 USD`) follow the `NUMBER [ IDENTIFIER ]` production in `Primary`. The identifier is interpreted as an ISO 4217 currency code by the runtime.

Time-unit identifiers in `LimitClause` (e.g., `1 D`) use the following conventions:

| Code | Unit |
|------|------|
| `S` | Second |
| `M` | Minute |
| `H` | Hour |
| `D` | Day |
