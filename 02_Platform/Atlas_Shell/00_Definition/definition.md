# Atlas Shell – Requirements Specification

## 1. Purpose

Component name: atlas_shell
Layer: 02_Platform

The **Atlas Shell** is a Platform-level UI component that provides the shared user interface framework for all Atlas applications.
It defines the global navigation structure, responsive layout behavior, and cross-application interaction patterns.

The shell ensures that all applications within Atlas:

* share a consistent navigation model
* integrate into a common UI structure
* remain modular and independently developed
* behave consistently across desktop and mobile devices

The shell **does not contain domain logic**.
All domain-specific functionality remains inside individual applications.

---

# 2. Interface Ownership

Atlas Shell owns:

- global navigation rendering
- layout structure
- application switching
- mobile/desktop navigation adaptation

Applications own:

- internal routes
- page content
- dataset endpoints
- application-specific navigation entries


# 3. Responsibilities of the Atlas Shell

The shell provides:

### Global UI Framework

* responsive layout
* navigation framework
* consistent application chrome
* cross-application switching

### Navigation System

* desktop sidebar navigation
* mobile bottom navigation
* application launcher
* contextual app menus

### Application Integration

Applications register themselves with the shell via a **navigation configuration contract**.

The shell renders navigation elements based on these declarations.

### Cross-App UX Consistency

The shell guarantees consistent behavior for:

* menus
* navigation layout
* mobile interactions
* settings access

---

# 4. Non-Responsibilities

The shell must not contain:

* domain logic
* business rules
* data access
* application-specific UI logic

These belong exclusively to Applications.

---

# 5. High-Level UI Structure

## Desktop Layout

```
-----------------------------------------
| Sidebar |            Content          |
|         |                             |
|         |                             |
-----------------------------------------
```

Sidebar contains:

* Atlas launcher
* registered applications
* optional nested app navigation

Content area renders the active application route.

---

## Mobile Layout

```
---------------------------------
|                               |
|           Content             |
|                               |
---------------------------------
| Launcher | App | Context | ⋯ |
---------------------------------
```

Mobile uses **Bottom Navigation** following Material Design guidelines.

Maximum items: **5**

Recommended default structure:

Launcher
Primary App
Secondary App Section
More / Menu

---

# 6. Application Launcher

The launcher acts as the root entry point of Atlas.

URL:

```
linspad.net
```

Responsibilities:

* list all registered applications
* allow switching between apps
* provide system overview

Example layout:

Atlas

Workout
Tasks
Future Apps

---

# 7. Navigation System

## Navigation Levels

Atlas navigation has two levels:

### Level 1 — Global Navigation

Switch between applications.

Examples:

Launcher
Workout
Tasks

Rendered by the shell.

---

### Level 2 — Local Application Navigation

Pages within the active application.

Examples:

Workout App

Log
Performance
History

Task App

Inbox
Projects
Documents

Local navigation entries are defined by the application.

---

# 8. Responsive Navigation Behavior

Navigation adapts based on screen size.

### Desktop

Left sidebar navigation.

Persistent and visible.

### Tablet

Collapsible sidebar with hamburger toggle.

### Mobile

Bottom navigation replaces sidebar.

The navigation items depend on the active application.

---

# 9. Contextual Navigation

Applications define which routes are promoted to **primary mobile navigation**.

Example:

Workout App

Primary Mobile Navigation:

Log
Performance

Secondary Menu:

History
Settings

---

# 10. Navigation Registration Contract

This contract is consumed by the Atlas Shell to render navigation.
Applications must expose this configuration.

Example structure:

```
{
  appId: "workout",
  label: "Workout",
  basePath: "/workout",

  mobilePrimaryNav: [
    { id: "log", label: "Log", path: "/workout" },
    { id: "performance", label: "Performance", path: "/workout/performance" }
  ],

  desktopNav: [
    { id: "log", label: "Log", path: "/workout" },
    { id: "performance", label: "Performance", path: "/workout/performance" },
    { id: "history", label: "History", path: "/workout/history" }
  ],

  secondaryMenu: [
    { id: "settings", label: "Settings", path: "/workout/settings" }
  ]
}
```

The shell consumes this configuration and renders navigation accordingly.

---

# 11. Global Menu / More Menu

A shared **More** or **Menu** button exists on mobile navigation.

Behavior is defined by the shell.

The contents of the menu are provided by the active application.

Examples:

Workout

History
Settings

Tasks

Projects
Documents
Settings

---

# 12. Settings Pattern

Settings follow a unified UX pattern.

Rules:

* settings always accessible via menu
* settings UI pattern consistent across apps
* settings content owned by the application

The shell only controls **menu behavior**, not settings content.

---

# 13. Routing Responsibilities

The shell manages:

* top-level routing
* app base routes
* navigation rendering

Applications manage:

* internal routes
* route content
* route guards if needed

---

# 14. Design System Alignment

Atlas Shell follows **Material Design navigation guidelines**.

Key principles:

* bottom navigation for mobile
* sidebar navigation for desktop
* maximum 5 bottom navigation items
* consistent interaction patterns

Future design tokens may include:

spacing
colors
typography
icons

---

# 15. Extensibility

The shell must support:

* adding new applications without modifying shell code
* reordering navigation entries
* promoting/demoting navigation items

Applications control their navigation priorities via configuration.

---


---

# 16. Architectural Decisions

These decisions have been made and must not be re-opened during design or implementation.

## Deployment model
The shell is a **standalone Vite application** — its own build, its own `package.json`, its own compose entry.
It is not a publishable npm package.

## Platform UI primitives
The platform UI primitives (`components/`, `api/`, `hooks/`, `index.css`) live at `02_Platform/Atlas_Shell/platform-ui/` and are consumed via the `@platform-ui` Vite alias.
The shell is the sole owner and consumer. `02_Platform/UI` no longer exists.

## Application hosting model
The shell is the UI host for all Atlas applications.
Applications register into the shell via `AppConfig` and run inside it.
This is the intended architecture — it is not a dependency direction violation.
The shell does not import application source directly; applications expose a root component that the shell loads.

## AppConfig ownership
`AppConfig` and `NavItem` are owned by the shell and exported from it.
They are **not** promoted to `00_Blueprint`.
Applications import these types from the shell.

## URL routing
The shell is served at `linspad.net` via the Cloudflare Tunnel configured in `01_System/Access`.
The shell has no dependency to declare on this — it is an ops concern, not a shell concern.

## Mobile navigation
Bottom Navigation is permitted for mobile viewports.
`02_Platform/Atlas_Shell/UI_DesignLanguage.md` defines this as a permitted deviation from stock M3.
Maximum 5 items in mobile bottom navigation — this is a hard constraint, not a guideline.

---

# 17. Open Questions for Implementer

These are deferred to the implementer and do not require architectural input:

- AppConfig registration mechanism: module import side-effect, explicit runtime call, or build-time manifest — choose the pattern most consistent with the React/Vite toolchain in use.
- `useShell()` state primitive: React Context, Zustand, or other — hook interface is fixed, backing store is not.
- CSS strategy: CSS modules, plain CSS — must use Blueprint tokens exclusively; mechanism is deferred.

---

# 18. Design Principles

The Atlas Shell follows these principles:

Consistency
All applications share the same navigation patterns.

Separation of concerns
Shell provides structure. Applications provide content.

Extensibility
New applications can integrate without modifying the shell.

Responsiveness
Navigation adapts to screen size.

Minimalism
The shell remains lightweight and avoids domain logic.

---

# 19. Summary

The Atlas Shell is the **Platform UI framework** for Atlas.

It provides:

* navigation
* layout
* application switching
* responsive design

Applications plug into the shell via configuration and remain fully modular.

The shell ensures Atlas behaves like a **cohesive multi-tool workspace rather than a collection of independent apps**.
