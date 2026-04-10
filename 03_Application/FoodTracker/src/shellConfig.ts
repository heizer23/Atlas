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
    { id: 'log',       label: 'Log',       path: '/food',            order: 1 },
    { id: 'report',    label: 'Report',    path: '/food/report',     order: 2 },
    { id: 'entries',   label: 'Entries',   path: '/food/entries',    order: 3 },
    { id: 'day',       label: 'Day',       path: '/food/day',        order: 4 },
  ],

  desktopNav: [
    { id: 'log',       label: 'Log',       path: '/food',            order: 1 },
    { id: 'report',    label: 'Report',    path: '/food/report',     order: 2 },
    { id: 'entries',   label: 'Entries',   path: '/food/entries',    order: 3 },
    { id: 'day',       label: 'Day',       path: '/food/day',        order: 4 },
  ],

  secondaryMenu: [],
});
