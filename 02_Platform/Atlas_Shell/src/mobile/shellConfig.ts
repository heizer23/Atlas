/**
 * Mobile Platform diagnostics — Atlas Shell registration.
 * Imported as a side-effect by src/shell/main.tsx. Platform-owned technical tool
 * (no domain logic); reachable at /mobile-test, mainly from AtlasPhone.
 */

import React from 'react';
import { AppRegistry } from '../registry/AppRegistry';

AppRegistry.register({
  appId: 'mobile-test',
  label: 'Mobile Platform',
  basePath: '/mobile-test',
  launcherIcon: 'smartphone',
  launcherTone: 'grey',
  component: React.lazy(() => import('./MobileTestScreen')),
  mobilePrimaryNav: [],
  desktopNav: [],
});
