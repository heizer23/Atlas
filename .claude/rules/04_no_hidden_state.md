# Rule: Durable State Must Be Explicit

State that affects system behavior or correctness must be explicit and owned.

Durable state must:
- have a clear owner (component or contract)
- have a defined storage location
- have a clear lifecycle

Examples:
- database tables
- persisted configuration
- contract schemas
- event logs
- durable queues

This state must not exist implicitly inside:
- undocumented files
- framework internals
- untracked services

## Allowed Operational State

Ephemeral implementation state is allowed and does not require architectural documentation.

Examples:
- caches
- temporary files
- retry buffers
- background worker queues
- framework session memory
- migration helpers
- build artifacts

These are acceptable if:
- they do not affect long-term correctness
- they can be safely recreated
- the system continues to function if they are cleared

## Guiding Question

If deleting the state would break correctness or lose important information, it must be explicit and owned.