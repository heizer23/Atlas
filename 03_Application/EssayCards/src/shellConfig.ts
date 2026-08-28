/**
 * EssayCards — Atlas Shell registration.
 *
 * Imported as a side-effect by 02_Platform/Atlas_Shell/src/shell/main.tsx.
 * Do not import this file from anywhere else.
 */

import React from 'react';
import { AppRegistry } from '@atlas/shell';

AppRegistry.register({
  appId: 'essaycards',
  label: 'EssayCards',
  basePath: '/essaycards',
  component: React.lazy(() => import('./ShellEntry')),

  mobilePrimaryNav: [
    { id: 'essaycards-essays', label: 'Essays',           path: '/essaycards',        order: 1 },
    { id: 'essaycards-due',    label: 'Due for review',   path: '/essaycards/review', order: 2 },
    { id: 'essaycards-ingest', label: 'Add / Update Essay', path: '/essaycards/ingest', order: 3 },
  ],

  desktopNav: [
    { id: 'essaycards-essays', label: 'Essays',           path: '/essaycards',        order: 1 },
    { id: 'essaycards-due',    label: 'Due for review',   path: '/essaycards/review', order: 2 },
    { id: 'essaycards-ingest', label: 'Add / Update Essay', path: '/essaycards/ingest', order: 3 },
  ],
});
