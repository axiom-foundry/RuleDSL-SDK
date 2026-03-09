# RuleDSL Rule Cookbook

Practical examples for every grammar feature, organized by business scenario.
Each example is a complete, compilable rule file.

## Table of Contents

1. [Basic Allow / Decline](#1-basic-allow--decline)
2. [Priority Ordering](#2-priority-ordering)
3. [Geo Blocking with IN Lists](#3-geo-blocking-with-in-lists)
4. [Channel Control with IN](#4-channel-control-with-in)
5. [Email Domain Check with MATCH](#5-email-domain-check-with-match)
6. [Currency-Aware Thresholds](#6-currency-aware-thresholds)
7. [Daily Spending Limits](#7-daily-spending-limits)
8. [Computed Risk Score](#8-computed-risk-score)
9. [Boolean Logic with NOT](#9-boolean-logic-with-not)
10. [Range-Based Review](#10-range-based-review)
11. [Multi-Action Rules](#11-multi-action-rules)
12. [Catch-All Fallback Pattern](#12-catch-all-fallback-pattern)

---

## 1. Basic Allow / Decline

The simplest possible rule: if the amount exceeds a threshold, decline.

```ruledsl
rule high_risk {
  when amount >= 1000;
  then decline;
}

rule default_allow {
  when amount < 1000;
  then allow;
}
```

**Use case:** Hard limit on transaction value.

---

## 2. Priority Ordering

Rules are evaluated in priority order (highest number first). The first match wins.

```ruledsl
rule vip_override priority 200 {
  when is_vip and amount <= 50000;
  then allow;
}

rule high_amount priority 100 {
  when amount > 10000;
  then decline;
}

rule default_allow {
  when true;
  then allow;
}
```

**Use case:** VIP customers bypass normal amount limits. Priority 200 is evaluated before priority 100. Rules without an explicit priority default to 0.

---

## 3. Geo Blocking with IN Lists

Use `IN` to check membership in a list of values.

```ruledsl
rule block_high_risk_geo priority 100 {
  when amount > 5000 and ip_country in [NG, RU, KP];
  then risk_score = 90, reason = "geo_high", decline;
}

rule allow_otherwise {
  when true;
  then allow;
}
```

**Use case:** Block high-value transactions from specific countries. The `IN` list accepts identifiers (bare words) and strings.

---

## 4. Channel Control with IN

```ruledsl
rule block_risky_channel {
  when channel in [ECOM, APP] and amount > 1000;
  then reason = "risky_channel", decline;
}

rule allow_other {
  when true;
  then allow;
}
```

**Use case:** E-commerce and mobile app channels get stricter limits than POS.

---

## 5. Email Domain Check with MATCH

Use `MATCH` for substring checks on text fields.

```ruledsl
rule flag_internal_domain {
  when email match "@example.com";
  then reason = "internal_domain", review;
}

rule allow_other {
  when true;
  then allow;
}
```

**Use case:** Flag transactions from internal email domains for manual review. MATCH expects the field to be a text value — applying it to a number raises a runtime error (`MATCH_EXPECTS_TEXT`). Always ensure the matched field is a string.

---

## 6. Currency-Aware Thresholds

Append a currency code to numeric literals for currency-aware comparisons.

```ruledsl
rule decline_large_usd {
  when amount >= 10000 USD;
  then reason = "usd_threshold", decline;
}

rule review_large_eur {
  when amount >= 8000 EUR;
  then reason = "eur_threshold", review;
}

rule allow_other {
  when true;
  then allow;
}
```

**Use case:** Different thresholds per currency. Note: the currency literal (`10000 USD`) attaches metadata to the comparison but the engine compares the **numeric value only** — it does not filter by currency. To enforce currency-specific rules, add an explicit condition: `when amount >= 10000 and currency == "USD"`.

---

## 7. Daily Spending Limits

Use `LIMIT ... PER` to enforce velocity windows.

```ruledsl
rule daily_spending_cap priority 80 {
  when amount > 2500;
  then reason = "daily_limit", limit 200 USD per 1 D;
}

rule allow_small {
  when amount <= 2500;
  then allow;
}
```

**Use case:** Limit high-value customers to 200 USD per day. Supported time units: `S` (second), `M` (minute), `H` (hour), `D` (day).

> **Note:** LIMIT rules require `now_utc_ms` to be provided in the input context. The Python and C# bindings auto-inject this from the system clock; the C API requires explicit injection.

---

## 8. Computed Risk Score

Arithmetic expressions in the `THEN` clause let you compute values.

```ruledsl
rule compute_risk priority 50 {
  when amount > 0;
  then risk_score = (amount / 100) + velocity_1h, review;
}
```

**Use case:** Dynamic risk scoring based on transaction amount and pre-computed velocity. Supported operators: `+`, `-`, `*`, `/`. Parentheses control evaluation order.

The host application provides `velocity_1h` as an input field (pre-computed from your database).

---

## 9. Boolean Logic with NOT

Full boolean logic: `AND`, `OR`, `NOT`, with parentheses for grouping.

```ruledsl
rule trusted_device {
  when card_present and not is_new_device;
  then reason = "trusted_device", allow;
}

rule new_device_high_amount {
  when is_new_device and amount > 500;
  then reason = "new_device_risk", review;
}

rule default_review {
  when true;
  then review;
}
```

**Use case:** Device trust logic. Boolean fields (`card_present`, `is_new_device`) are provided as `true`/`false` by the host.

---

## 10. Range-Based Review

Combine comparisons with `AND` to create ranges.

```ruledsl
rule review_medium_amount priority 50 {
  when amount > 1000 and amount <= 5000;
  then risk_score = 60, reason = "medium_amount", review;
}

rule decline_high_amount priority 100 {
  when amount > 5000;
  then risk_score = 95, reason = "high_amount", decline;
}

rule allow_small {
  when amount <= 1000;
  then allow;
}
```

**Use case:** Tiered risk bands. Medium amounts get review, high amounts get declined, low amounts pass.

---

## 11. Multi-Action Rules

A single rule can set multiple output fields and make a decision, separated by commas.

```ruledsl
rule fraud_score priority 100 {
  when amount > 3000 and ip_country in [NG, RU] and is_new_device;
  then risk_score = 95,
       reason = "multi_signal_fraud",
       category = "high_risk",
       decline;
}
```

**Use case:** Enrich the decision context with metadata for downstream systems. The host application receives all assigned fields in the decision result.

---

## 12. Catch-All Fallback Pattern

Always end your rule set with a catch-all rule to ensure every input gets a decision.

```ruledsl
rule block_sanctioned priority 200 {
  when ip_country in [KP, IR, SY];
  then reason = "sanctioned", decline;
}

rule review_high_amount priority 100 {
  when amount > 5000;
  then reason = "high_amount", review;
}

rule limit_daily priority 50 {
  when amount > 1000;
  then limit 500 USD per 1 D;
}

rule allow_default {
  when true;
  then reason = "baseline", risk_score = 10, allow;
}
```

**Use case:** Production rule set pattern. Rules are evaluated top-to-bottom by priority. The first match stops evaluation. `when true` catches everything that didn't match above.

---

## Patterns & Best Practices

### Missing Fields Raise Runtime Errors

If a field referenced in a rule condition is not provided in the input context, the engine raises a runtime error (`UNKNOWN_PATH`). This is an explicit failure — the engine does not silently treat missing fields as false.

**Always provide all fields referenced in your rules.** If a field might not exist, check for it in your host application before passing input to the engine, or use a catch-all rule with `when true` as a fallback in a separate rule set that does not reference the optional field.

### Host Pre-Computes, Engine Decides

The engine is deliberately minimal. Features like aggregation (SUM, COUNT), date arithmetic, and string manipulation are handled by the host application. The host computes derived fields (e.g., `velocity_1h`, `days_since_signup`, `is_vip`) and passes them as input.

This separation keeps the engine deterministic and auditable.

### Rule File Organization

- One rule file per policy domain (e.g., `transaction_risk.rule`, `spending_limits.rule`)
- Use priority to control evaluation order within a file
- Always include a catch-all fallback rule
- Use descriptive rule names — they appear in decision results

### Input Field Naming

- Use `snake_case` for field names: `amount`, `ip_country`, `is_new_device`
- Use dotted paths for nested data: `customer.risk_level`, `merchant.category`
- Reserved field: `now_utc_ms` — required for LIMIT rules

---

## Grammar Feature Matrix

| Feature | Syntax | Example |
|---------|--------|---------|
| Rule block | `rule NAME { when EXPR; then ACTION; }` | See all examples above |
| Priority | `rule NAME priority N { ... }` | [Example 2](#2-priority-ordering) |
| Comparison | `==`, `!=`, `<`, `<=`, `>`, `>=` | [Example 1](#1-basic-allow--decline) |
| Boolean logic | `and`, `or`, `not` | [Example 9](#9-boolean-logic-with-not) |
| List membership | `field in [A, B, C]` | [Example 3](#3-geo-blocking-with-in-lists) |
| Substring match | `field match "substring"` | [Example 5](#5-email-domain-check-with-match) |
| Currency literal | `1000 USD` | [Example 6](#6-currency-aware-thresholds) |
| Arithmetic | `+`, `-`, `*`, `/` | [Example 8](#8-computed-risk-score) |
| Assignment | `field = expr` | [Example 11](#11-multi-action-rules) |
| Velocity limit | `limit N CUR per N UNIT` | [Example 7](#7-daily-spending-limits) |
| Decision types | `allow`, `decline`, `review` | All examples |
| Dotted path | `customer.level` | See [Input Field Naming](#input-field-naming) |
| Parentheses | `(expr)` | [Example 8](#8-computed-risk-score) |
| Boolean literal | `true`, `false` | [Example 12](#12-catch-all-fallback-pattern) |
