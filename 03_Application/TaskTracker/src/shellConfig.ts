/**
 * TaskTracker — Atlas Shell registration.
 *
 * Imported as a side-effect by 02_Platform/02_Atlas_Shell/src/shell/main.tsx.
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
    { id: 'tasks', label: 'Tasks', path: '/tasks', order: 1 },
  ],

  desktopNav: [
    { id: 'tasks', label: 'Tasks', path: '/tasks', order: 1 },
  ],
});
