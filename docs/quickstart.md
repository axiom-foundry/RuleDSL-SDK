# Quickstart (5-Min Customer Evaluation)

This guide assumes you are at the repository root.

## What is included in this public repo

- `include/axiom/`: public C SDK headers
- `docs/`: integration, ABI, ownership, replay, and operational docs
- `examples/c/minimal_eval.c`: compile-time and runtime integration example
- `MANIFEST.txt` and `VERSION.txt`: package inventory and SDK version marker

## How evaluation works

This repository publishes the SDK surface (headers + docs + sample code).

Redistributable binaries are not committed here by default. Binaries are delivered separately during evaluation engagement or through release artifacts when published.

## Prerequisites

### Windows

- Visual Studio 2022 Build Tools (or full Visual Studio)
- x64 Developer Command Prompt

### Linux

- `gcc` or `clang`
- standard C runtime/linker toolchain

## Build (when SDK binaries are provided under `lib/`)

### Windows (Developer Command Prompt)

```bat
cl /nologo /W4 /std:c11 /I include examples/c/minimal_eval.c /link /LIBPATH:lib axiom_ruledsl_c.lib /OUT:minimal_eval.exe
```

If runtime reports a missing DLL:
- SDK distribution may be static (`.lib`) or dynamic (`.dll` + import lib).
- When using dynamic linkage, ensure required DLLs are reachable at runtime.
- Typical local run setup from repo root: `set PATH=%CD%\bin;%PATH%`

### Linux (gcc)

```bash
gcc -std=c11 -O2 -Wall -Wextra -I include examples/c/minimal_eval.c -L lib -laxiom_ruledsl_c -o minimal_eval
```

### Linux (clang)

```bash
clang -std=c11 -O2 -Wall -Wextra -I include examples/c/minimal_eval.c -L lib -laxiom_ruledsl_c -o minimal_eval
```

## Run

Windows:

```text
minimal_eval.exe <bytecode.bc>
```

Linux:

```text
./minimal_eval <bytecode.bc>
```

## Expected output (sample)

```text
RuleDSL/1.0.0 (abi=1)
Decision: matched=1 action_type=0
DETERMINISTIC_OK
```

## Troubleshooting

- `lib/` missing: this public repo does not include binaries by default; request evaluation binaries or use published release assets.
- Bytecode path error: verify `<bytecode.bc>` exists and is readable.
- Architecture mismatch: use matching x64 toolchain and x64 libraries.
- Runtime loader errors: add SDK runtime directory to `PATH` (Windows) or `LD_LIBRARY_PATH` (Linux).
- Replay may be unavailable in some builds; this is expected for minimal runtime packages.
