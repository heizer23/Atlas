# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

Delivered as a React/Vite web app (`02_Platform/Atlas_Shell`, served by nginx). The primary client is an Android wrapper that displays the website, optimized for phones. Laptop browser use is secondary. Mobile web remains `web`; there is no native design language.

## Users
Single primary user: the owner/developer, using Atlas daily, phone-first, for personal tracking and study (tasks, habits, food, workouts, storage, flashcards, reading, calendar, notes). Solo use; no multi-tenant or onboarding audience.

## Product Purpose
Atlas is a self-hosted personal system built to grow together with AI: the owner's primary interface to AI, making their data, behavior, and tools observable and structured. The UI is the daily surface over many small applications (03_Application) sharing a platform shell. Success: fast, low-friction daily capture and review on a phone.

## Positioning
A self-hosted, AI-legible personal system where architecture and contracts are first-class and applications can be regenerated from user stories, not a general consumer productivity suite.

## Operating Context
- Four layers: Blueprint, System, Platform, Application; UI renders from a shared `Dataset` contract (`02_Platform/Atlas_Shell/platform-ui/api/UI_Data_Contract.md`).
- Apps include Calendar, Chronicle, ClaudeConsole, EssayCards, FamilyAtlas, FoodTracker, HabitTracker, NumericSeries, PersonalDevelopment, StorageTracker, StoryReader, TaskTracker, WorkoutTracker.
- Frontend deploy: `npx vite build` then copy `dist/` into the `atlas-shell` container.

## Capabilities and Constraints
- Applications must not couple to UI implementation details; read endpoints return `Dataset`.
- LLM legibility favors idiomatic, explicit code over clever abstractions.
- Existing UI governance docs: `02_Platform/Atlas_Shell/UI_DesignLanguage.md`, `UI_AppPatterns.md`, `UI_Implementation.md`.

## Brand Commitments
None binding. The owner is open to redesign of the visual language; existing UI docs are incumbent evidence, not binding constraints. Any redesign must keep the `Dataset` UI contract and update Blueprint UI docs deliberately.

## Evidence on Hand
Real running apps and data; no external testimonials or marketing assets (none should be fabricated).

## Product Principles
1. Phone-first, one-handed daily use; laptop is a secondary adaptation.
2. Consistency across apps through shared patterns, since the apps are many and small.
3. Architecture-legible UI: explicit contracts and standard patterns over bespoke per-app design.
4. Operate mode: speed and scanability over expression.
