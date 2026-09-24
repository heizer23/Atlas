/**
 * StoryReader — Atlas Shell registration.
 *
 * Imported as a side-effect by 02_Platform/Atlas_Shell/src/shell/main.tsx.
 * Do not import this file from anywhere else.
 *
 * mobilePrimaryNav is the primary target — this app is designed to be used
 * one-handed, on a phone, while reading (00_draft.md §UI). desktopNav mirrors
 * it for consistency with every other app's shellConfig.ts.
 */

import React from 'react';
import { AppRegistry } from '@atlas/shell';

AppRegistry.register({
  appId: 'storyreader',
  label: 'Stories',
  basePath: '/storyreader',
  component: React.lazy(() => import('./ShellEntry')),

  mobilePrimaryNav: [
    { id: 'storyreader-stories', label: 'Stories', path: '/storyreader', order: 1 },
  ],

  desktopNav: [
    { id: 'storyreader-stories', label: 'Stories', path: '/storyreader', order: 1 },
  ],
});
