##  Purpose

Extract the current real state of an application and produce a structured, machine-legible definition.md.

The skill must:

reflect implemented reality only

make boundaries explicit

surface gaps and inconsistencies

It must NOT:

speculate

invent future features

blur contracts and implementation

Invocation

Use when:

an application exists (code, DB, or partial implementation)

you want a clean, current definition

you want to validate architecture consistency

Inputs (required)

The agent must actively inspect:

Codebase

routes / controllers

services

models / schemas

Database

tables

columns

relations

Existing docs (optional)

previous definition.md

notes

If something is missing:
→ explicitly state it under Known Gaps

Output (strict schema)

Always output exactly this structure:

# <App Name> – Definition

## 1. Purpose
Short statement of what the app currently does (not aspirational).

## 2. Current Concept
How the app currently models the problem (based on implementation).

## 3. Current Capabilities
Bullet list of what the app can actually do today.
Only include things that are implemented and reachable.

## 4. Current Data Model
List of private application tables / objects:
- table name
- key fields
- purpose

No UI shapes. No contracts.

## 5. Contracts Consumed
External contracts the app depends on:
- name of contract
- where used

Do NOT redefine the contract.

## 6. Interfaces Exposed

### 6.1 API Endpoints
- method + path
- purpose
- input (high level)
- output (high level, reference contract if applicable)

### 6.2 UI Datasets
- dataset name
- source endpoint
- shape type (must reference UI Data Contract if applicable)

### 6.3 Events Emitted
- event name
- trigger
- payload (high level)

### 6.4 Events Consumed
- event name
- usage

### 6.5 External / Platform Dependencies
- service
- purpose

## 7. Known Gaps
- missing features implied by structure
- incomplete implementations
- inconsistencies
- unclear areas due to missing input

## 8. Non-Scope
Explicitly list things that are NOT part of the app right now.
Hard Rules
1. No speculation

If not clearly implemented → goes to Known Gaps

2. No mixed states

Capabilities = real

Gaps = missing

Never mix

3. Contracts are references only

Do not restate UI or platform contracts

4. Strict boundary discipline

Data Model = private only

Interfaces = boundary only

5. No hidden assumptions

If uncertain:
→ write it explicitly in Known Gaps

Validation Step (mandatory)

After generating the document, perform a validation pass and append:

## Validation Warnings

Check for:

Endpoint without clear purpose

Endpoint without corresponding data model usage

Table not used by any endpoint

Capability without visible implementation support

UI dataset without contract alignment

Missing contracts where expected

Behavior Constraints

Do NOT overwrite files silently

Do NOT assume naming conventions

Do NOT infer business logic without evidence

Prefer “unknown” over guessing

Example Invocation

“Run app-definition-generator on FoodTracker using current code and DB”

Expected Outcome

One clean definition.md

One validation section

Clear separation of:

internal state

exposed interfaces

missing pieces