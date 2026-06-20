# Pass fixture — legitimate non-goal / host-scope prose (MUST produce zero findings)

- RuleDSL MUST NOT be interpreted as a transport layer, API gateway, or network protocol.
- RuleDSL MUST NOT be interpreted as a persistence, workflow, scheduling, or orchestration system.
- RuleDSL MUST NOT be interpreted as a distributed consensus or multi-node state coordination system.
- RuleDSL is not a workflow engine, and it is not a database.
- RuleDSL assumes no implicit persistence guarantees and no distributed consensus semantics.
- The host SHALL manage integration lifecycle, retries, transport, persistence, and operational controls.
- Security controls for identity, authorization, and transport security remain host responsibilities.
- RuleDSL provides deterministic decision evaluation for the documented contract surface.
- The engine offers a stable public C ABI; networking and storage are out of scope.
