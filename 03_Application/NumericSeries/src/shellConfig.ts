/**
 * NumericSeries — Atlas Shell registration.
 *
 * Imported as a side-effect by 02_Platform/02_Atlas_Shell/src/shell/main.tsx.
 * Do not import this file from anywhere else.
 */

import React from 'react';
import { AppRegistry } from '@atlas/shell';

AppRegistry.register({
  appId: 'numeric-series',
  label: 'Series',
  basePath: '/series',
  component: React.lazy(() => import('./ShellEntry')),

  mobilePrimaryNav: [
    { id: 'series', label: 'Series', path: '/series', order: 1 },
  ],

  desktopNav: [
    { id: 'series', label: 'Series', path: '/series', order: 1 },
  ],
});
