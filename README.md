# RuleDSL SDK

Deterministic decision infrastructure for regulated and latency-sensitive C/C++ systems.

Note: This repository contains the public C SDK surface (headers, documentation, and examples).
The compiled runtime libraries are provided separately as evaluation artifacts
(or via official release downloads when available). See docs/distribution.md for details.

- Deterministic evaluation with repeatable outcomes
- Explicit ABI contract (`struct_size`, `version`, reserved fields)
- Optional replay support for reproducible validation
- No database dependency in core evaluation path
- No runtime service requirement (library integration only)

## Quickstart

The commands below assume you have received the evaluation runtime package
containing the compiled library for your platform (for example placed under a local "lib/" directory).
This repository includes headers and examples only.

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

Core:
- [docs/quickstart.md](docs/quickstart.md)
- [docs/technical_positioning.md](docs/technical_positioning.md)
- [docs/determinism_value_model.md](docs/determinism_value_model.md)
- [docs/sdk_struct_contract.md](docs/sdk_struct_contract.md)
- [docs/thread_safety_model.md](docs/thread_safety_model.md)

Advanced & Commercial Notes:
- [docs/distribution.md](docs/distribution.md)
- [docs/evaluation_engagement_model.md](docs/evaluation_engagement_model.md)
- [docs/integration_operational_model.md](docs/integration_operational_model.md)
- [docs/migration_and_lockin_model.md](docs/migration_and_lockin_model.md)
- [docs/ownership_contract.md](docs/ownership_contract.md)
- [docs/product_offer_definition.md](docs/product_offer_definition.md)
- [docs/replay_contract.md](docs/replay_contract.md)
- [docs/error_code_registry.md](docs/error_code_registry.md)
- [docs/capabilities.md](docs/capabilities.md)
- [docs/github_metadata.md](docs/github_metadata.md)

Engine implementation is private; this repository contains the SDK surface for evaluation.

License: Evaluation package; contact for commercial licensing.
