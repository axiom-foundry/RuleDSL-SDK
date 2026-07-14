# Cross-machine replay evidence — 2026-07-14

## Scope (read this first)

**First committed same-platform machine reproduction.** A fresh Windows 11 x64
machine — no prior build artifacts, integrity chain verified end to end
(release-bundle SHA → engine DLL SHA → bytecode SHA) — ran the shipped **v1.0.2**
release binaries and reproduced the published golden outputs **byte-for-byte**:

- **DET-001** (standard decision path) `output_bin_sha256` =
  `f3714ba24ad7a84218874bff096eab721bd67bcd5641cd45d2973fd86d55c5e1`
- **DET-003** (deterministic error path) `error_hash_sha256` =
  `9b0dd8f9caeadd8e6ed1fabd65305041bc5d518cbf5716f54178691d88727a65`

Those golden values were originally produced by the project's **CI runners on
Windows-x64 and Linux-x64** (see `reports/determinism_v1_0/2026-07-11/` and
`reports/determinism_compare_v1/2026-07-11/`). Reproducing them on an unrelated
desktop is a genuine machine-to-machine (CI ↔ laptop) reproduction on the same
platform.

**What this is NOT.** This is one operator on two independent machines, not a
proof of universal multi-host determinism. A two-desktop **operator verify**
(machine-a ↔ machine-b `replay_proof` compare) is queued as a follow-up, and
**independent third-party reproduction remains open** — the steps to do it
yourself are below.

## Contents

| Path | What it is |
| --- | --- |
| `machine-a/replay_proof.json` | Portable `replay_proof_v1` record produced on this machine (DET-001 decision). Pair it with a second machine's record and run `Tools/replay_proof/verify_replay_proof.py`. |
| `machine-a/environment.json` | Machine/toolchain fingerprint (OS, Python, engine version — no host/user identifiers). |
| `reproduction/reproduce_transcript.txt` | Full stdout of the reproducer: integrity chain + DET-001/DET-003 hash comparison, both `PASS`. |

The reproducer is committed at
[`Tools/replay_proof/reproduce_cross_machine.py`](../../../Tools/replay_proof/reproduce_cross_machine.py).

## Reproduce it yourself

All inputs and golden values are committed in this repo; the engine is the public
release binary. From the repository root:

```sh
# 1. Download the v1.0.2 SDK bundle for your platform from Releases and verify it
#    against the published SHA256SUMS asset:
#      https://github.com/axiom-foundry/RuleDSL-SDK/releases/tag/v1.0.2
#    (Windows: RuleDSL-SDK-v1.0.2-windows-x86_64.zip, Linux: ...-linux-x86_64.tar.gz)

# 2. Extract it, then run the reproducer against the committed inputs:
python Tools/replay_proof/reproduce_cross_machine.py \
    --bundle <extracted-bundle-dir> \
    --repo   . \
    --emit-dir /tmp/my_machine

# 3. The reproducer prints PASS iff DET-001 and DET-003 reproduce the golden
#    hashes above, and writes your own replay_proof.json + environment.json.
```

To compare two machines' records directly:

```sh
python Tools/replay_proof/verify_replay_proof.py \
    --a machine-a/replay_proof.json \
    --b <second-machine>/replay_proof.json --strict
# PASS means engine version, ABI, bytecode hash, and decision hash all match.
```

## Provenance

- Engine: `RuleDSL/1.0.2 (abi=1)`, from `RuleDSL-SDK-v1.0.2-windows-x86_64.zip`
  (bundle and DLL hashes checked against the published `SHA256SUMS` and the
  bundle's own `manifests/HASHES.txt`).
- Inputs: committed under `reports/determinism_v1_0/2026-07-11/windows-x64/`
  (`ci-windows` for DET-001, `ci-windows-det003` for DET-003).
- This set only **adds** evidence; the historical `2026-06-21`, `2026-06-23`,
  and `2026-07-11` sets are unchanged.
