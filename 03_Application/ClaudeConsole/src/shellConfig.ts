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

// Terminal: xterm.js on a host tmux session via the tailnet-only bridge (01_System/ClaudeTerminal).
AppRegistry.register({
  appId: 'claudeterminal',
  label: 'Terminal',
  basePath: '/terminal',
  component: React.lazy(() => import('./TerminalEntry')),

  mobilePrimaryNav: [
    { id: 'terminal-main', label: 'Terminal', path: '/terminal', order: 2 },
  ],

  desktopNav: [
    { id: 'terminal-main', label: 'Terminal', path: '/terminal', order: 2 },
  ],
});
