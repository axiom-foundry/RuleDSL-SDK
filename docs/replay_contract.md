# Replay Lite Contract (C API)

`ax_eval_record_ex2` and `ax_eval_replay_ex2` provide a memory-only replay path for deterministic evidence capture.

## Replay Header (V1)

Each replay blob begins with a fixed 16-byte header serialized in little-endian order:

```c
typedef struct ReplayHeaderV1 {
  uint32_t magic;      // 'AXRP' (0x50525841)
  uint16_t schema_ver; // 1
  uint16_t flags;      // 0 in V1
  uint32_t payload_len;
  uint32_t crc32;      // CRC32 of payload bytes only
} ReplayHeaderV1;
```

Payload bytes start immediately after the header and contain deterministic evaluation snapshot data.

## Versioning and Extension Policy

- `magic` identifies replay payload family.
- `schema_ver` defines binary schema; incompatible versions are rejected.
- `flags` is reserved for additive behavior switches and must be zero for V1.
- New schema versions must preserve deterministic serialization order and add explicit validation rules.

## Guarantees

- Replay operates only on caller-provided memory buffers.
- No file I/O, network I/O, or database dependency is introduced.
- `ax_eval_record_ex2` reports required buffer size through `out_size`.
- `ax_eval_replay_ex2` validates header, bounds, and CRC before replaying.
- For identical bytecode and replay payload, replay must produce identical decision outputs.

## What Invalidates Replay

Replay is rejected when any of the following changes:

- Header magic/schema/flags do not match supported V1 values.
- `payload_len` does not match actual payload bytes.
- Payload CRC32 does not match stored CRC.
- Recorded bytecode size/checksum do not match caller-provided bytecode.
- Replayed decision result differs from recorded snapshot.

## Ownership Rules

- Caller owns `out_buffer` memory passed to `ax_eval_record_ex2`.
- Caller owns `AXReplayBufferV1` and the memory referenced by `AXReplayBufferV1.data`.
- Caller owns `AXDecisionV2` and must release SDK-owned strings with `ax_decision_reset_v2`.
- Replay APIs never free caller-owned buffers.

## Error Behavior

- `AX_ERR_LIMIT_EXCEEDED`: output buffer capacity is insufficient; `out_size` reports required bytes.
- `AX_ERR_BAD_STRUCT_SIZE`: struct_size contract failed.
- `AX_ERR_INVALID_ARGUMENT`: malformed buffer bounds/lengths or null/unsupported inputs.
- `AX_ERR_VERIFY`: incompatible replay schema, CRC mismatch, bytecode mismatch, or decision mismatch.
