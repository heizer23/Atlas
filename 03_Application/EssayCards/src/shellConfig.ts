/**
 * EssayCards — Atlas Shell registration.
 *
 * Imported as a side-effect by 02_Platform/Atlas_Shell/src/shell/main.tsx.
 * Do not import this file from anywhere else.
 */

import React from 'react';
import { AppRegistry } from '@atlas/shell';

AppRegistry.register({
  appId: 'essaycards',
  label: 'EssayCards',
  basePath: '/essaycards',
  component: React.lazy(() => import('./ShellEntry')),

  // Sprint12_FSRSAndUXOverhaul (internal_flow step 14): trimmed to the
  // everyday-learning + stats items (well under the Shell's 5-item cap).
  // Content management (Add / Update Essay) moves to secondaryMenu — the
  // Shell's existing mobile "More" overlay. The Experiment entry is removed
  // entirely (the Sprint10 A/B experiment and its dashboard are retired).
  mobilePrimaryNav: [
    { id: 'essaycards-essays', label: 'Essays',           path: '/essaycards',        order: 1 },
    { id: 'essaycards-due',    label: 'Flashcards',       path: '/essaycards/review', order: 2 },
    { id: 'essaycards-recall', label: 'Oral Recall',      path: '/essaycards/recall', order: 3 },
    { id: 'essaycards-stats',  label: 'Stats',             path: '/essaycards/stats',  order: 4 },
  ],

  // The Shell's Sidebar renders desktopNav as a flat ordered list with no
  // grouping concept in the current AppConfig/NavItem contract (R-CON-BP-06)
  // — "grouping" on desktop is achieved only via adjacent `order` values,
  // keeping Add / Update Essay here even though it moved off mobile's
  // primary nav. A true visual desktop grouping would require a
  // Platform-layer Atlas_Shell change — out of scope this sprint.
  desktopNav: [
    { id: 'essaycards-essays', label: 'Essays',           path: '/essaycards',        order: 1 },
    { id: 'essaycards-due',    label: 'Flashcards',       path: '/essaycards/review', order: 2 },
    { id: 'essaycards-recall', label: 'Oral Recall',      path: '/essaycards/recall', order: 3 },
    { id: 'essaycards-ingest', label: 'Add / Update Essay', path: '/essaycards/ingest', order: 4 },
    { id: 'essaycards-stats',  label: 'Stats',             path: '/essaycards/stats',  order: 5 },
  ],

  // Reachable via the Shell's mobile "More" overlay.
  secondaryMenu: [
    { id: 'essaycards-ingest-secondary', label: 'Add / Update Essay', path: '/essaycards/ingest', order: 1 },
  ],
});
