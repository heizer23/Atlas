/**
 * PersonalDevelopment — Atlas Shell registration.
 *
 * Imported as a side-effect by 02_Platform/Atlas_Shell/src/shell/main.tsx.
 * Do not import this file from anywhere else.
 */

import React from 'react';
import { AppRegistry } from '@atlas/shell';

AppRegistry.register({
  appId: 'learning',
  label: 'Learning',
  basePath: '/learning',
  component: React.lazy(() => import('./ShellEntry')),

  mobilePrimaryNav: [
    { id: 'learning-units', label: 'Units', path: '/learning', order: 1 },
  ],

  desktopNav: [
    { id: 'learning-units', label: 'Units', path: '/learning', order: 1 },
  ],
});
