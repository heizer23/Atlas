/**
 * Kitchen — Atlas Shell registration.
 *
 * Imported as a side-effect by 02_Platform/Atlas_Shell/src/shell/main.tsx.
 * Do not import this file from anywhere else.
 */

import React from 'react';
import { AppRegistry } from '@atlas/shell';

const nav = [
  { id: 'kitchen-plan',     label: 'Plan',     path: '/kitchen',          order: 1 },
  { id: 'kitchen-shopping', label: 'Shopping', path: '/kitchen/shopping', order: 2 },
  { id: 'kitchen-recipes',  label: 'Recipes', path: '/kitchen/recipes',  order: 3 },
];

AppRegistry.register({
  appId: 'kitchen',
  label: 'Kitchen',
  basePath: '/kitchen',
  launcherIcon: 'restaurant',
  launcherTone: 'rose',
  component: React.lazy(() => import('./ShellEntry')),
  mobilePrimaryNav: nav,
  desktopNav: nav,
});
