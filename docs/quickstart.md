# Quickstart (5-Min Customer Evaluation)

## Why RuleDSL?

- Deterministic decision evaluation (same input -> same output)
- ABI-stable C SDK (versioned contract)
- Optional buffer-based replay (audit and debugging)
- No database dependency
- No runtime service required (in-process library)

This guide uses the packaged SDK layout under `dist/sdk` and gets the sample running fast.

## What is in this package

- `include/axiom/`: public C headers
- `lib/`: SDK libraries for linking
- `examples/c/minimal_eval.c`: deterministic C demo
- `docs/`: API contract and behavior docs

## Prerequisites

### Windows

- Visual Studio 2022 Build Tools (or full VS) with C/C++ toolchain
- x64 Native Tools / Developer Command Prompt

### Linux

- `gcc` or `clang`
- standard C runtime and linker toolchain (`libc`, `ld`)

## Build (copy-paste)

Run commands from the package root (`dist/sdk`).

### Windows (Developer Command Prompt)

```bat
cd dist\sdk
cl /nologo /W4 /std:c11 /I include examples/c/minimal_eval.c /link /LIBPATH:lib axiom_ruledsl_c.lib /OUT:minimal_eval.exe
```

If you get a missing DLL at runtime:
- The package may include either a DLL + import lib or a static library.
- If a DLL is shipped, it must be reachable at runtime (same folder as `minimal_eval.exe` or in `PATH`).
- From `dist\sdk`, you can run `set PATH=%CD%\bin;%PATH%` before executing the demo.

If you are in a plain Command Prompt first:

```bat
call "%ProgramFiles%/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat"
```

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
RuleDSL/1.0.0 (abi=1; ex2=1; replay_schema=1)
Capabilities: abi_level=1 replay_schema=1 has_ex2=1
Decision: matched=1 action_type=0
Replay: code=0 bytes=...
DETERMINISTIC_OK
```

`DETERMINISTIC_OK` is the success marker for customer evaluation runs.

## Troubleshooting

- **Bytecode path error**: verify `<bytecode.bc>` exists and is readable from your current shell directory.
- **Architecture mismatch**: use x64 toolchain and x64 libraries together (avoid mixing x86 and x64).
- **Runtime/CRT load issues**: on Windows, run from the VS Developer shell or install the matching MSVC redistributable.
- **Linker cannot find SDK lib**: confirm library file exists in `lib/` and library name matches your platform build.
- **`Replay: not supported in this build`**: this is valid; replay is capability-dependent and not always enabled.
