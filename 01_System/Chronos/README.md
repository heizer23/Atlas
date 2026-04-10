# Chronos

Role: System control surface for Atlas AI access.

## Current classification
01_System component

## Purpose
Chronos is the System-level AI gateway for Atlas.
It provides access and orchestration, not domain behavior.

## Ownership

Chronos owns:
- its runtime and internal state (workspace, cache, logs)
- Chronos-native agents and prompts

Atlas owns:
- Platform capabilities (APIs, DB, tools)
- Application logic and data

Chronos must not:
- directly own or mutate application data
- redefine platform capabilities

## Configuration

- Deployment config: central Atlas env (CHRONOS_*)
- Secrets: provided via Atlas secrets.env
- Internal config: treated as implementation detail (not Atlas contract)

## Deployment model
- Definition lives in git
- Runtime lives on Pi
- Secrets live only on Pi

## Dependencies

- Chronos may call Atlas via explicit, stable interfaces only

## State

- All Chronos state is stored under a single defined host path
- This state is treated as owned implementation state, not Atlas contract
