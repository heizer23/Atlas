# CLAUDE.md

## Purpose

Python implementation of the Atlas UI Dataset contract.

## Classification

Platform. Contains no domain logic. Shared by all application routers that surface data through the Atlas UI.

## Source of truth

`R-CON-BP-04` (`.claude/rules/R-CON-BP-04_ui_data_contract.md`) defines the contract in language-neutral terms.
This package is its Python expression. When the contract changes, update both.

## Responsibilities

- Define `Dataset`, `DatasetMeta`, `ColumnSchema` — the response shape every app router must return.
- Define `ColumnType` and `RowAction` literal types.

## Rules

- Never add domain-specific fields or logic here.
- Never import from application code.
- Keep the types minimal and stable — this is a contract, not a utility library.

## Public API

- `Dataset`
- `DatasetMeta`
- `ColumnSchema`
- `ColumnType`
- `RowAction`
