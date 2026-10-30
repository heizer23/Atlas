/**
 * TaskTracker — Atlas Shell registration.
 *
 * Imported as a side-effect by 02_Platform/Atlas_Shell/src/shell/main.tsx.
 * Do not import this file from anywhere else.
 */

import React from 'react';
import { AppRegistry } from '@atlas/shell';

AppRegistry.register({
  appId: 'tasks',
  label: 'Tasks',
  basePath: '/tasks',
  component: React.lazy(() => import('./ShellEntry')),

  mobilePrimaryNav: [
    { id: 'tasks-today',      label: 'Today',      path: '/tasks',              order: 1 },
    { id: 'tasks-active',     label: 'Active',     path: '/tasks/active',       order: 2 },
    { id: 'tasks-scheduled',  label: 'Scheduled',  path: '/tasks/scheduled',    order: 3 },
    { id: 'tasks-pending',    label: 'Pending',    path: '/tasks/pending',      order: 4 },
    { id: 'tasks-done',       label: 'Done',       path: '/tasks/done',         order: 5 },
  ],

  desktopNav: [
    { id: 'tasks-today',      label: 'Today',      path: '/tasks',              order: 1 },
    { id: 'tasks-active',     label: 'Active',     path: '/tasks/active',       order: 2 },
    { id: 'tasks-scheduled',  label: 'Scheduled',  path: '/tasks/scheduled',    order: 3 },
    { id: 'tasks-pending',    label: 'Pending',    path: '/tasks/pending',      order: 4 },
    { id: 'tasks-done',       label: 'Done',       path: '/tasks/done',         order: 5 },
  ],
});
