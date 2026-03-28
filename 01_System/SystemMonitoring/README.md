# SystemMonitoring

Role: Host-level monitoring and health visibility for the Atlas runtime.

## Current classification
01_System component

## Purpose
SystemMonitoring provides visibility into the **physical host and runtime environment** of Atlas.

It ensures that resource constraints, failures, or degradations at the system level are detectable early and can be acted upon.

This component is strictly concerned with **infrastructure health**, not application behavior.

## Scope

SystemMonitoring covers:

- CPU usage
- Memory usage
- Disk usage and capacity
- Disk I/O
- Network activity
- System load
- Temperature (Pi-specific)
- Docker/container resource usage (CPU, memory, restarts)

## Non-scope

SystemMonitoring must not:

- implement or interpret business logic
- track application-level metrics (e.g. workouts, tasks, nutrition)
- replace application logging or error handling
- act as a data source for domain decisions

## Ownership

SystemMonitoring owns:

- host-level monitoring agent (e.g. Netdata)
- access to system metrics
- visualization of infrastructure health

Atlas owns:

- platform logging and error handling
- application-level metrics and KPIs
- business logic and interpretation

## Deployment model

- Installed directly on the host (not inside Docker)
- Runs as a background service
- Accessed locally or via Tailscale
- No dependency from other Atlas components

## Dependencies

- Reads system metrics from the host OS
- May observe Docker runtime (read-only)

SystemMonitoring must not:

- require Atlas services to function
- introduce dependencies into Platform or Application layers

## Design principles

- **Passive observation only** (no control over system behavior)
- **No hidden coupling** with Atlas components
- **Low resource overhead**
- **Local-first operation** (no required cloud dependency)

## Future extensions (optional)

- Basic alerting (e.g. disk > 80%, memory pressure)
- Historical metrics retention
- Integration with external alerting systems (explicit decision required)