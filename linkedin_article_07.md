What a Deterministic Decision Looks Like

Six posts about determinism, and not a single example of what it actually produces.

Fair enough. Here is what a reproducible decision looks like in practice:

Input:
  amount: 1200.0 USD
  ip_country: "XX"
  now_utc_ms: 1700000000000

Output:
  matched: true
  action: DECLINE
  rule: geo_high
  risk_score: 90
  reason: "geo_high"

Run it again. Same input, same bytecode, same engine version.
Same output. Every field. Every time.

Not "same result most of the time."
Exactly the same. Byte-for-byte.

This is what determinism means in a decision engine:

– The rule is compiled to bytecode — not interpreted at runtime.
– Time is not read from the system clock. It is injected explicitly.
– Evaluation order is fixed by priority, not by insertion order.
– Floating-point behavior follows IEEE 754 binary64 — no fast-math, no platform drift.
– The decision carries a trace: which rule matched, what was evaluated, what was skipped.

When an auditor asks "what happened on March 3rd?", you do not reconstruct. You replay.

Same bytecode. Same input. Same answer.

That is the bar.

Language reference and live examples: https://axiom-foundry.github.io/RuleDSL-SDK/

#Determinism #DecisionSystems #FinancialInfrastructure
