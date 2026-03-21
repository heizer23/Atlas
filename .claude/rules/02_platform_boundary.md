# Rule: Platform Boundary

A Platform component provides reusable technical capability.

It:
- is primarily generic
- is intended for reuse
- does not own domain meaning or business rules
- is persistent or long-lived
- supports applications without determining their workflow behavior

Platform provides capability.
Applications provide meaning.

Platform may:
- expose reusable primitives influenced by application needs
- standardize technical patterns, adapters, and integration surfaces
- carry domain-shaped data without interpreting its business meaning

Platform should not:
- encode application-specific workflow decisions
- become the owner of business rules
- absorb behavior that is meaningful only within one application

When designing a platform component:
- define what capability is provided
- define who may consume it
- define what it explicitly does not do
- state any domain-shaped assumptions that exist only for technical interoperability
- keep ownership of meaning and workflow in the application layer