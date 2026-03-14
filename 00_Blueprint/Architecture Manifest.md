## Mission Statement

**Atlas is a self-hosted system built to grow together with AI.** It serves as my primary interface to AI by making my data, behavior, and tools observable, structured, and reason-able from within the system itself. I build the system in order to build better systems: architecture, contracts, and constraints are treated as first-class objects so both I and an LLM can understand, evolve, and reshape the system over time. The goal is not fixed functionality, but a durable human–AI feedback loop grounded in explicit structure rather than ad-hoc prompts or hidden state. Concretely: Blueprint is developed collaboratively and expressed primarily in language. Platform is designed together and implemented by AI. Applications are the most autonomous layer — the goal is for an application to emerge from a prompt written as a user story, made possible by the stability and explicitness of the layers beneath it.

---

## Architectural Rules

**0. The system is understood through four layers: Blueprint, System, Platform, and Application.** These layers define _what the system is and how it is governed_ (Blueprint), _how the system is accessed and rebuilt_ (System), _what shared capabilities exist_ (Platform), and _where behavior lives_ (Application). All design decisions must be expressible in this model.

**1. The system is designed to develop itself.** Architecture, contracts, and structure are organized so that an LLM — given only the system's own artifacts — can inspect, review, extend, and improve it without relying on implicit knowledge. Clarity is not cosmetic; it is what makes this loop possible.

**2. Architecture is the primary interface to AI.** Clear layering, explicit contracts, and durable objects matter more than code longevity.

**3. LLM legibility is a design constraint.** Standard libraries, idiomatic patterns, and explicit structure are preferred over clever or minimal implementations — because they provide stable semantic anchors an LLM can reliably reason about across contexts. Clarity is preferred over minimal code size or performance micro-optimizations. This principle does not prohibit custom code when necessary.

**4. Contracts are more durable than code.** Meaning, guarantees, and boundaries are preserved through contracts; application code is replaceable and may be regenerated. Applications declare how they consume, produce, or derive meaning from shared data objects. Contracts and data objects are changed deliberately and explicitly. Contracts live in 00.Blueprint and are enumerated as: shared database views, UI definitions, and API definitions (TBD). Application table schemas are not contracts — they are private to the application and live inside it. Only the views derived from those tables are contracts.

**5. No hidden state.** All durable state must be inspectable, versioned, and reachable through defined system or platform mechanisms.

**6. Stability lives at the edges, flexibility lives inside.** Blueprint and System change slowly; Applications are expected to change rapidly or disappear.

**7. Platform provides capabilities; Applications provide meaning.** Platform contains no domain logic. Applications never provide platform services.

**8. General capabilities beat predefined workflows.** The system provides composable primitives (objects, links, queries, views); processes emerge from recombination. Design decisions in this area are intentionally conservative and human-led, prioritizing long-term flexibility over short-term automation.

**9. Violations are surfaced, not silently tolerated.** If a proposed design conflicts with this manifest, it must be flagged before proceeding. Regular system audits compare all documentation and code against this manifest to surface drift.

---

## Layer Definitions

### 00.Blueprint

Blueprint is the **foundation of the system** — it defines the rules, structure, and agreements that everything else is built on.

A component belongs in Blueprint when it:

- defines **how the system is designed and governed** (the manifest, architectural rules),
- or specifies a **contract between layers** — an explicit, durable agreement about structure, shape, or behavior that multiple components depend on.

Blueprint components are the **most stable artifacts in the system**. They change rarely, deliberately, and with explicit justification.

**Classification Rule:** If something defines _how the system works_ rather than _doing something within the system_, it is Blueprint.

**Contract types currently defined:**

- **Schemas** — shared database views (cross-application data contracts; application tables are private and live in 03.Application)
- **UI** — design language, component contracts, and implementation standards
- **API** — endpoint and interface definitions (TBD)
  An API contract is promoted to Blueprint only when two or more apps need to consume or produce the same shape. Until then, it lives as the app's AppDefinition plus the router code.

Example: the Architecture Manifest, shared database views, UI contract

---

### 01.System

Defines how the system is accessed, controlled, and rebuilt.

Includes components that establish:

- trust boundaries (entry and authentication),
- operational rules (DevOps, configuration, rebuild),
- control surfaces (UI, ChatOps).

Excludes any component that adds domain or application capability.

**Classification Rule:** If a component determines how users or external clients interact with the system, or how the system is operated or rebuilt, it is System.

Example: the central configuration file

---

### 02.Platform

Platform is the **common backbone** used by all application services. A component belongs in Platform when it:

- provides a **generic technical capability**,
- is **shared** across multiple applications,
- contains **no domain logic**,
- and is **persistent** or long-lived.

Platform components do not care _why_ they are used. They only provide **storage, ingestion, transport, scheduling, messaging, or execution support** for applications.

**Rule:** If something adds a **reusable technical capability** that multiple apps can build on, and it contains **no domain-specific behavior**, it is **Platform**.

Example: the PostgreSQL database

---

### 03.Application

Application is where the **actual behavior** of the system lives. A component belongs here when it:

- implements **logic that transforms inputs into meaningful outputs**,
- has a **specific purpose or domain**,
- uses Platform services but does not provide services to the Platform.

Applications are replaceable, versionable, and contain all of the "what" and "why" behind system behavior. Each application owns its table schemas privately; these are not contracts and are not shared.

**Rule:** If something **does** something meaningful (parsing, monitoring, calculating, transforming, scoring, ingesting), and its behavior is not a generic capability, it is **Application**.

Example: the food tracker app