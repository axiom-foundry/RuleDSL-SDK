# RuleDSL – Integration & Operational Model

## Deployment Model
RuleDSL is integrated as an in-process library, either through dynamic linking or static linking, depending on the host build strategy.

Evaluation happens inside the host process. There is no daemon process, no RPC boundary, and no network hop in the core execution path.

The engine does not require external state services for evaluation. Inputs, bytecode, and output structures are provided and controlled by the host.

## Runtime Characteristics
- Deterministic evaluation per call for equivalent bytecode and input payload
- No hidden background threads unless explicitly documented by the API contract
- Caller-owned memory for input fields, options, and output containers
- Explicit cleanup requirements for SDK-owned allocations exposed through output structs
- No internal file or network I/O during evaluation

## Concurrency Model
Concurrent use is safe when each in-flight evaluation uses isolated input/output structures and the integration follows the documented ownership rules.

Concurrent reuse of non-thread-safe objects is not safe. In particular, shared mutable compiler state must be externally synchronized or separated per thread.

Compiler lifecycle is host-controlled: create, build, evaluate, and destroy under explicit caller control. Threading policy should be enforced by the host according to the published thread-safety contract.

## Failure Model
Errors are reported through stable numeric error codes in the C API.

The API is C-style and does not rely on exceptions for error signaling.

For documented misuse cases (for example invalid struct size, unsupported version, malformed replay payload), the expected behavior is an explicit error return rather than undefined behavior.

## Upgrade Model
ABI level signaling is exposed through the capability query API and version fingerprint string.

Feature availability is detected at runtime via capabilities, not by assumptions about build variants.

Forward-compatible struct design uses explicit `struct_size`, `version`, and reserved fields so newer SDK builds can coexist with older host integrations.

Bytecode compatibility depends on the documented bytecode schema and toolchain/version policy. Hosts should treat bytecode as versioned artifacts and validate compatibility during rollout.

## Operational Footprint
- No DB dependency in the core evaluation path
- No network dependency in the core evaluation path
- No service discovery requirement
- No required runtime configuration files unless defined by the host application
