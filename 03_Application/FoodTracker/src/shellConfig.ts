/**
 * FoodTracker — Atlas Shell registration.
 *
 * Imported as a side-effect by 02_Platform/Atlas_Shell/src/shell/main.tsx.
 * Do not import this file from anywhere else.
 */

import React from 'react';
import { AppRegistry } from '@atlas/shell';

AppRegistry.register({
  appId: 'food',
  label: 'Food',
  basePath: '/food',
  component: React.lazy(() => import('./ShellEntry')),

  mobilePrimaryNav: [
    { id: 'day',       label: 'Day',       path: '/food/day',        order: 1 },
    { id: 'log',       label: 'Log',       path: '/food/log',        order: 2 },
    { id: 'report',    label: 'Report',    path: '/food/report',     order: 3 },
    { id: 'entries',   label: 'Entries',   path: '/food/entries',    order: 4 },
  ],

  desktopNav: [
    { id: 'day',       label: 'Day',       path: '/food/day',        order: 1 },
    { id: 'log',       label: 'Log',       path: '/food/log',        order: 2 },
    { id: 'report',    label: 'Report',    path: '/food/report',     order: 3 },
    { id: 'entries',   label: 'Entries',   path: '/food/entries',    order: 4 },
  ],

  secondaryMenu: [],
});
