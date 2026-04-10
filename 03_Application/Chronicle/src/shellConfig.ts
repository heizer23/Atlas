/**
 * Chronicle — Atlas Shell registration.
 *
 * Imported as a side-effect by 02_Platform/Atlas_Shell/src/shell/main.tsx.
 * Do not import this file from anywhere else.
 */

import React from 'react';
import { AppRegistry } from '@atlas/shell';

AppRegistry.register({
  appId: 'chronicle',
  label: 'Chronicle',
  basePath: '/chronicle',
  component: React.lazy(() => import('./ShellEntry')),

  mobilePrimaryNav: [
    { id: 'calendar', label: 'Calendar', path: '/chronicle', order: 1 },
  ],

  desktopNav: [
    { id: 'calendar', label: 'Calendar', path: '/chronicle', order: 1 },
  ],

  secondaryMenu: [],
});
