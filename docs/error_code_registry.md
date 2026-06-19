# AXErrorCode Registry

The canonical, stable error-code registry for the v1.x public ABI is
[`contracts/error_codes_registry_v1_0.md`](contracts/error_codes_registry_v1_0.md) — the numeric
map (values 0–11) and the ABI stability contract.

For per-code explanations and the reserved error-band scheme
(`0` success, `1–63` user/integration, `64–127` artifact, `128–191` engine/runtime, `192–255`
reserved), see [`errors.md`](errors.md), which matches the shipped header `include/axiom/ruledsl_c.h`.

This file is intentionally a pointer so the registry lives in exactly one place and cannot drift.
