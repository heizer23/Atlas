# CLAUDE.md

This file contains app-local guidance only.
Global architecture and development rules are defined in the repository root CLAUDE.md.

## App
StorageTracker is a household item tracking application. Users track consumables (with quantity), objects (with location), and pending_action items.

## Sprint scope
- Sprint 1: Core CRUD, item history, views (low_stock, recycling, important, search), React UI
- Sprint 2: Shopping tasks
- Sprint 3: Notifications and geofencing

## Pattern references
Follow the same patterns as TaskTracker (03_Application/TaskTracker):
- FastAPI backend, psycopg2 connection pool, RealDictCursor
- platform_contracts for Dataset responses
- platform_errorhandling for api_error and middleware
- Atlas Shell registration via src/shellConfig.ts

## Port
StorageTracker backend runs on host port 8022 (container port 8000).

## Schema
storagetracker schema in the shared Atlas Postgres instance.
Tables: storagetracker.items, storagetracker.item_history
Schema initialized idempotently at startup from schema.sql.
