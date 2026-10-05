/**
 * HabitTracker — Atlas Shell registration.
 *
 * Imported as a side-effect by 02_Platform/Atlas_Shell/src/shell/main.tsx.
 * Do not import this file from anywhere else.
 *
 * mobilePrimaryNav is the primary target — this app is built around one
 * evening ritual, fast and comfortable on mobile (00_draft.md §Goal), same
 * rationale as StoryReader/StorageTracker. desktopNav mirrors it.
 */

import React from 'react';
import { AppRegistry } from '@atlas/shell';

AppRegistry.register({
  appId: 'habittracker',
  label: 'Habits',
  basePath: '/habittracker',
  component: React.lazy(() => import('./ShellEntry')),

  mobilePrimaryNav: [
    { id: 'habittracker-review',  label: 'Today',   path: '/habittracker',         order: 1 },
    { id: 'habittracker-habits',  label: 'Habits',  path: '/habittracker/habits',  order: 2 },
    { id: 'habittracker-reports', label: 'Reports', path: '/habittracker/reports', order: 3 },
  ],

  desktopNav: [
    { id: 'habittracker-review',  label: 'Today',   path: '/habittracker',         order: 1 },
    { id: 'habittracker-habits',  label: 'Habits',  path: '/habittracker/habits',  order: 2 },
    { id: 'habittracker-reports', label: 'Reports', path: '/habittracker/reports', order: 3 },
  ],
});
