# OpenClawed

Role: System control surface for Atlas AI access.

## Current classification
01_System component

## Purpose
OpenClawed is the System-level AI gateway for Atlas.
It provides access and orchestration, not domain behavior.

## Ownership

OpenClawed owns:
- its runtime and internal state (workspace, cache, logs)
- OpenClawed-native agents and prompts

Atlas owns:
- Platform capabilities (APIs, DB, tools)
- Application logic and data

OpenClawed must not:
- directly own or mutate application data
- redefine platform capabilities

## Configuration

- Deployment config: central Atlas env (OPENCLAW_*)
- Secrets: provided via Atlas secrets.env
- Internal config: treated as implementation detail (not Atlas contract)

## Deployment model
- Definition lives in git
- Runtime lives on Pi
- Secrets live only on Pi

## Dependencies

- OpenClawed may call Atlas via explicit, stable interfaces only

## State

- All OpenClawed state is stored under a single defined host path
- This state is treated as owned implementation state, not Atlas contract