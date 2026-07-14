#!/usr/bin/env python3
"""
Cross-machine determinism reproducer for RuleDSL DET-001 / DET-003.

Runs the shipped v1.0.x engine binary on the CURRENT machine against the
committed determinism inputs and checks that the decision-output bytes (DET-001)
and the deterministic error-payload bytes (DET-003) hash byte-for-byte to the
published golden values that the project's CI produced on Windows-x64 and
Linux-x64. It then emits a portable `replay_proof_v1` record plus an environment
fingerprint, so a second machine's record can later be compared with
`Tools/replay_proof/verify_replay_proof.py`.

This does NOT require network access or the CI toolchain: the engine comes from
the public release bundle, the inputs are committed in this repo, and the golden
values are the committed evidence.

Usage:
    python Tools/replay_proof/reproduce_cross_machine.py \
        --bundle <extracted-SDK-bundle-dir> [--repo <repo-root>] [--emit-dir <dir>]

`--bundle` is the extracted release bundle (contains bin/, bindings/, manifests/).
`--repo`   defaults to this repo (two levels up from this script).
`--emit-dir`, if given, receives replay_proof.json + environment.json.

Exit code 0 iff both DET-001 and DET-003 reproduce the golden hashes.

Output is intentionally free of absolute paths / usernames so transcripts can be
committed as evidence.
"""

import argparse
import ctypes
import hashlib
import json
import platform
import struct
import sys
from pathlib import Path

# --- Committed golden values (produced by CI on Windows-x64 and Linux-x64) -----
GOLDEN = {
    "bytecode_sha256": "d9707fb46f7f7bd62bfa16615bf6739b9f7d607f67df663539b0df168738f131",
    "det001_output_sha256": "f3714ba24ad7a84218874bff096eab721bd67bcd5641cd45d2973fd86d55c5e1",
    "det003_error_sha256": "9b0dd8f9caeadd8e6ed1fabd65305041bc5d518cbf5716f54178691d88727a65",
}

# Committed evidence bundle used as the source of inputs (v1.0.2 set, 2026-07-11).
DET001_DIR = "reports/determinism_v1_0/2026-07-11/windows-x64/ci-windows"
DET003_DIR = "reports/determinism_v1_0/2026-07-11/windows-x64/ci-windows-det003"

# DET-001 canonical input (from inputs/canonical_input.json).
DET001_FIELDS = {"amount": 100.0, "country": "TR", "now_utc_ms": 1700000000000.0}
# DET-003 canonical input (amount is the string "INVALID_NUMBER").
DET003_FIELDS = {"amount": "INVALID_NUMBER", "country": "TR", "now_utc_ms": 1700000000000.0}


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dll_name() -> str:
    return "ruledsl_capi.dll" if platform.system() == "Windows" else "libruledsl_capi.so"


def platform_label() -> str:
    sysname = "windows" if platform.system() == "Windows" else (
        "linux" if platform.system() == "Linux" else platform.system().lower())
    arch = "x64" if platform.machine().lower() in ("amd64", "x86_64") else platform.machine().lower()
    return f"{sysname}-{arch}"


def verify_dll_integrity(bundle: Path, engine, out_lines) -> bool:
    """Confirm the loaded engine binary matches the bundle's own manifest hash."""
    dll_path = bundle / "bin" / dll_name()
    dll_sha = sha256_hex(dll_path.read_bytes())
    manifest = (bundle / "manifests" / "HASHES.txt").read_text(encoding="utf-8")
    expected = None
    for line in manifest.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].endswith("bin/" + dll_name()):
            expected = parts[0]
            break
    ok = expected is not None and dll_sha == expected
    out_lines.append(f"  engine binary        : bin/{dll_name()}")
    out_lines.append(f"  engine sha256        : {dll_sha}")
    out_lines.append(f"  manifest sha256      : {expected}")
    out_lines.append(f"  integrity            : {'MATCH' if ok else 'MISMATCH'}")
    return ok


def serialize_decision(status_code: int, dec) -> bytes:
    """Reproduce the committed DET-001 output.bin layout (little-endian):
    int32 status | int32 matched | int32 action_type | double amount
    | len-prefixed currency (-1=null) | double window_count
    | len-prefixed window_unit (-1=null) | len-prefixed rule_name (-1=null)
    """
    def s(x):
        if x is None:
            return struct.pack("<i", -1)
        b = x.encode("utf-8")
        return struct.pack("<i", len(b)) + b

    out = struct.pack("<i", status_code)
    out += struct.pack("<i", 1 if dec.matched else 0)
    out += struct.pack("<i", int(dec.action_type))
    out += struct.pack("<d", float(dec.amount or 0.0))
    out += s(dec.currency)
    out += struct.pack("<d", float(dec.window_count or 0.0))
    out += s(dec.window_unit)
    out += s(dec.rule_name)
    return out


def reproduce_det001(engine, repo: Path, out_lines):
    from ruledsl import RuleDSL  # noqa: F401  (import proven available by caller)
    bc = (repo / DET001_DIR / "inputs" / "bytecode.axbc").read_bytes()
    bc_sha = sha256_hex(bc)
    dec = engine.evaluate(bc, DET001_FIELDS)
    serialized = serialize_decision(0, dec)
    out_sha = sha256_hex(serialized)
    committed = (repo / DET001_DIR / "outputs" / "DET-001_output.bin").read_bytes()

    ok = (bc_sha == GOLDEN["bytecode_sha256"]
          and out_sha == GOLDEN["det001_output_sha256"]
          and serialized == committed)
    out_lines.append("DET-001 (standard decision path)")
    out_lines.append(f"  bytecode sha256      : {bc_sha}")
    out_lines.append(f"  bytecode golden      : {GOLDEN['bytecode_sha256']}")
    out_lines.append(f"  decision             : matched={dec.matched} action={dec.action} "
                     f"rule={dec.rule_name!r}")
    out_lines.append(f"  output sha256        : {out_sha}")
    out_lines.append(f"  output golden        : {GOLDEN['det001_output_sha256']}")
    out_lines.append(f"  bytes == committed   : {serialized == committed}")
    out_lines.append(f"  DET-001              : {'PASS' if ok else 'FAIL'}")
    return ok, dec, bc_sha


def reproduce_det003(engine, repo: Path, out_lines):
    import ruledsl
    from ruledsl import RuleDSL, _AXBytecode, _AXEvalOptions, _AXDecision  # noqa: F401
    L = engine._lib
    bc = (repo / DET003_DIR / "inputs" / "bytecode.axbc").read_bytes()
    buf = (ctypes.c_ubyte * len(bc)).from_buffer_copy(bc)
    c_bc = _AXBytecode()
    c_bc.data = ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte))
    c_bc.size = len(bc)
    fields, _refs = RuleDSL._build_fields(DET003_FIELDS)

    opts = _AXEvalOptions()
    opts.struct_size = 0  # DET-003 trigger: options struct_size too small
    dec = _AXDecision()
    dec.struct_size = ctypes.sizeof(_AXDecision)
    err = ctypes.create_string_buffer(2048)

    code = L.ax_eval_bytecode(engine._compiler, ctypes.byref(c_bc), fields, 3,
                              ctypes.byref(opts), ctypes.byref(dec), err, len(err))
    msg = err.value
    err_sha = sha256_hex(msg)
    committed = (repo / DET003_DIR / "outputs" / "DET-003_output.bin").read_bytes()

    ok = (code == 10 and err_sha == GOLDEN["det003_error_sha256"] and msg == committed)
    out_lines.append("DET-003 (deterministic error path)")
    out_lines.append(f"  status_code          : {code} (expected 10 = AX_ERR_BAD_STRUCT_SIZE)")
    out_lines.append(f"  error payload        : {msg!r}")
    out_lines.append(f"  error sha256         : {err_sha}")
    out_lines.append(f"  error golden         : {GOLDEN['det003_error_sha256']}")
    out_lines.append(f"  bytes == committed   : {msg == committed}")
    out_lines.append(f"  DET-003              : {'PASS' if ok else 'FAIL'}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True, type=Path)
    ap.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument("--emit-dir", type=Path, default=None)
    args = ap.parse_args()

    bundle = args.bundle.resolve()
    repo = args.repo.resolve()
    sys.path.insert(0, str(bundle / "bindings" / "python"))
    from ruledsl import RuleDSL

    out = []
    out.append("RuleDSL cross-machine determinism reproduction")
    out.append("=" * 62)
    out.append(f"platform             : {platform_label()}")
    out.append(f"python               : {platform.python_implementation()} "
               f"{platform.python_version()}")

    engine = RuleDSL(str(bundle / "bin" / dll_name()))
    out.append(f"engine               : {engine.version()}")
    out.append("")
    out.append("Integrity chain")
    integ_ok = verify_dll_integrity(bundle, engine, out)
    out.append("")

    d1_ok, dec, bc_sha = reproduce_det001(engine, repo, out)
    out.append("")
    d3_ok = reproduce_det003(engine, repo, out)
    out.append("")

    all_ok = integ_ok and d1_ok and d3_ok
    out.append("=" * 62)
    out.append("RESULT: " + ("PASS - golden hashes reproduced on this machine."
                             if all_ok else "FAIL - a hash diverged."))
    out.append("=" * 62)

    print("\n".join(out))

    if args.emit_dir is not None:
        args.emit_dir.mkdir(parents=True, exist_ok=True)
        compat = engine.check_compatibility(
            (repo / DET001_DIR / "inputs" / "bytecode.axbc").read_bytes())
        decision_payload = {
            "matched": dec.matched, "action_type": dec.action_type, "amount": dec.amount,
            "currency": dec.currency, "window_count": dec.window_count,
            "window_unit": dec.window_unit, "rule_name": dec.rule_name, "outputs": dec.outputs,
        }
        record = {
            "schema_version": "replay_proof_v1",
            "engine_version_string": engine.version(),
            "abi_level": compat["minimum_engine_abi"],
            "bytecode_hash": bc_sha,
            "decision_hash": sha256_hex(json.dumps(decision_payload, sort_keys=True,
                                                   separators=(",", ":")).encode("utf-8")),
            "input_hash": sha256_hex(json.dumps(DET001_FIELDS, sort_keys=True,
                                                separators=(",", ":")).encode("utf-8")),
            "input_descriptor": "DET-001 canonical input",
            "notes": "cross-machine reproduction; DET-001 decision path",
        }
        env = {
            "platform": platform_label(),
            "system": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "machine": platform.machine(),
            "python_impl": platform.python_implementation(),
            "python_version": platform.python_version(),
            "engine_version_string": engine.version(),
        }
        (args.emit_dir / "replay_proof.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8")
        (args.emit_dir / "environment.json").write_text(
            json.dumps(env, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    engine.close()
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
