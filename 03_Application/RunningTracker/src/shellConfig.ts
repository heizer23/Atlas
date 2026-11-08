/**
 * RunningTracker - Atlas Shell registration.
 *
 * Imported as a side-effect by 02_Platform/Atlas_Shell/src/shell/main.tsx.
 * Do not import this file from anywhere else.
 */

import React from 'react';
import { AppRegistry } from '@atlas/shell';

const nav = [
  { id: 'running-run',     label: 'Run',     path: '/running',          order: 1 },
  { id: 'running-history', label: 'History', path: '/running/history',  order: 2 },
  { id: 'running-routes',  label: 'Routes',  path: '/running/routes',   order: 3 },
  { id: 'running-devices', label: 'Devices', path: '/running/devices',  order: 4 },
];

AppRegistry.register({
  appId: 'running',
  label: 'Running',
  basePath: '/running',
  launcherIcon: 'directions_run',
  launcherTone: 'teal',
  component: React.lazy(() => import('./ShellEntry')),
  mobilePrimaryNav: nav,
  desktopNav: nav,
});
