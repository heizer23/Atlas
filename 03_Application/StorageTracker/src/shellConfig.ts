/**
 * StorageTracker — Atlas Shell registration.
 *
 * Imported as a side-effect by 02_Platform/Atlas_Shell/src/shell/main.tsx.
 * Do not import this file from anywhere else.
 */

import React from 'react';
import { AppRegistry } from '@atlas/shell';

AppRegistry.register({
  appId: 'storage',
  label: 'Storage',
  basePath: '/items',
  component: React.lazy(() => import('./ShellEntry')),

  mobilePrimaryNav: [
    { id: 'storage-all',       label: 'All Items',  path: '/items',            order: 1 },
    { id: 'storage-lowstock',  label: 'Low Stock',  path: '/items/low-stock',  order: 2 },
    { id: 'storage-important', label: 'Important',  path: '/items/important',  order: 3 },
    { id: 'storage-recycling', label: 'Recycling',  path: '/items/recycling',  order: 4 },
  ],

  desktopNav: [
    { id: 'storage-all',       label: 'All Items',  path: '/items',            order: 1 },
    { id: 'storage-lowstock',  label: 'Low Stock',  path: '/items/low-stock',  order: 2 },
    { id: 'storage-important', label: 'Important',  path: '/items/important',  order: 3 },
    { id: 'storage-recycling', label: 'Recycling',  path: '/items/recycling',  order: 4 },
  ],
});
