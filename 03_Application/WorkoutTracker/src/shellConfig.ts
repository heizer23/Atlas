/**
 * WorkoutTracker — Atlas Shell registration.
 *
 * Imported as a side-effect by 02_Platform/Atlas_Shell/src/shell/main.tsx.
 * Do not import this file from anywhere else.
 */

import React from 'react';
import { AppRegistry } from '@atlas/shell';

AppRegistry.register({
  appId: 'workout',
  label: 'Workout',
  basePath: '/workout',
  component: React.lazy(() => import('./ShellEntry')),

  mobilePrimaryNav: [
    { id: 'session',     label: 'Session',      path: '/workout',             order: 1 },
    { id: 'log',         label: 'Log',          path: '/workout/log',         order: 2 },
    { id: 'performance', label: 'Performance',  path: '/workout/performance', order: 3 },
  ],

  desktopNav: [
    { id: 'session',     label: 'Session',      path: '/workout',             order: 1 },
    { id: 'log',         label: 'Log',          path: '/workout/log',         order: 2 },
    { id: 'performance', label: 'Performance',  path: '/workout/performance', order: 3 },
    { id: 'settings',    label: 'Settings',     path: '/workout/settings',    order: 4 },
  ],

  secondaryMenu: [
    { id: 'settings', label: 'Settings', path: '/workout/settings', order: 1 },
  ],
});
