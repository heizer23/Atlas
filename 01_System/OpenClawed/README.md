# OpenClawed

Role: System control surface for Atlas AI access.

## Current classification
01_System component

## Purpose
OpenClawed is the operator-facing AI gateway into Atlas.
It is treated as a System component because it primarily defines access and control, not domain behavior.

## Current boundary
- Owns its own runtime and persistent state
- May call Atlas through explicit APIs/tools only
- Does not directly own Atlas application data
- Does not get blanket access to Atlas secrets

## Deployment model
- Definition lives in git
- Runtime lives on Pi
- Secrets live only on Pi