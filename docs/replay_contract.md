# Replay Contract (C API)

Replay support provides a memory-only path for deterministic evidence capture.

## Replay Header (current schema)

Each replay blob begins with a fixed header serialized in little-endian order:

```c
typedef struct ReplayHeader {
  uint32_t magic;      // 'AXRP' (0x50525841)
  uint16_t schema_ver; // 1
  uint16_t flags;      // 0 in current schema
  uint32_t payload_len;
  uint32_t crc32;      // CRC32 of payload bytes only
} ReplayHeader;
```

## Versioning and Extension Policy

- `magic` identifies replay payload family.
- `schema_ver` defines binary schema; incompatible versions are rejected.
- `flags` is reserved for additive behavior switches and must be zero for the current schema.
- New schema versions must preserve deterministic serialization order and add explicit validation rules.

## Guarantees

- Replay operates only on caller-provided memory buffers.
- No file I/O, network I/O, or database dependency is introduced.
- Record APIs report required buffer size through `out_size`.
- Replay APIs validate header, bounds, and CRC before replaying.
- For identical bytecode and replay payload, replay must produce identical decision outputs.

## Ownership Rules

- Caller owns output buffers passed to replay record APIs.
- Caller owns replay buffer structs and referenced memory.
- Caller owns `AXDecision` and must release SDK-owned strings with `ax_decision_reset`.
- Replay APIs never free caller-owned buffers.
