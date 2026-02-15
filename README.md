# RuleDSL SDK

Deterministic in-process decision evaluation via an ABI-stable C SDK.

- Determinism-first evaluation for repeatable outcomes
- Explicit ABI contract (`struct_size`, `version`, reserved fields)
- Optional replay support for reproducible validation
- No database dependency in core evaluation path
- No runtime service requirement (library integration only)

## Quickstart

Windows (Developer Command Prompt):

```bat
cl /nologo /W4 /std:c11 /I include examples/c/minimal_eval.c /link /LIBPATH:lib axiom_ruledsl_c.lib /OUT:minimal_eval.exe
minimal_eval.exe <bytecode.bc>
```

Linux (gcc):

```bash
gcc -std=c11 -O2 -Wall -Wextra -I include examples/c/minimal_eval.c -L lib -laxiom_ruledsl_c -o minimal_eval
./minimal_eval <bytecode.bc>
```

## Documentation

- [Technical positioning](docs/technical_positioning.md)
- [Integration and operational model](docs/integration_operational_model.md)
- [Migration and lock-in model](docs/migration_and_lockin_model.md)
- [Determinism value model](docs/determinism_value_model.md)
- [Quickstart guide](docs/quickstart.md)
- [Distribution model](docs/distribution.md)
- [Evaluation terms](EVALUATION_TERMS.md)

Engine implementation is private; this repository contains the SDK surface for evaluation.

License: Evaluation package; contact for commercial licensing.
