/**
 * Calendar — Atlas Shell registration.
 *
 * Imported as a side-effect by 02_Platform/Atlas_Shell/src/shell/main.tsx.
 * Do not import this file from anywhere else.
 */

import React from 'react';
import { AppRegistry } from '@atlas/shell';

AppRegistry.register({
  appId: 'calendar',
  label: 'Calendar',
  basePath: '/calendar',
  component: React.lazy(() => import('./ShellEntry')),

  mobilePrimaryNav: [
    { id: 'calendar-week', label: 'Week', path: '/calendar', order: 1 },
  ],

  desktopNav: [
    { id: 'calendar-week', label: 'Week', path: '/calendar', order: 1 },
  ],
});
