/**
 * ClaudeConsole — Atlas Shell registration.
 *
 * Imported as a side-effect by 02_Platform/Atlas_Shell/src/shell/main.tsx.
 * Do not import this file from anywhere else.
 */

import React from 'react';
import { AppRegistry } from '@atlas/shell';

AppRegistry.register({
  appId: 'claudeconsole',
  label: 'Console',
  basePath: '/console',
  component: React.lazy(() => import('./ShellEntry')),

  mobilePrimaryNav: [
    { id: 'console-main', label: 'Console', path: '/console', order: 1 },
  ],

  desktopNav: [
    { id: 'console-main', label: 'Console', path: '/console', order: 1 },
  ],
});
