/**
 * File: 02_Platform/Atlas_Shell/src/shell/main.tsx
 * Component: atlas_shell
 *
 * Role: Composition root. The ONLY shell file permitted to import from
 * 03_Application. Each application's shellConfig.ts is imported as a
 * side-effect — it calls AppRegistry.register() internally. main.tsx never
 * calls AppRegistry.register() directly.
 *
 * After all side-effect imports, mounts <BrowserRouter><Router /></BrowserRouter>.
 * BrowserRouter is owned here; Router does not own its own BrowserRouter.
 *
 * HOW TO ADD AN APPLICATION
 * --------------------------
 * 1. In the application's own src/, create shellConfig.ts that calls:
 *      import { AppRegistry } from '@atlas/shell';
 *      import React from 'react';
 *      AppRegistry.register({
 *        appId: 'my-app',
 *        label: 'My App',
 *        basePath: '/my-app',
 *        component: React.lazy(() => import('./App')),
 *        mobilePrimaryNav: [...],
 *        desktopNav: [...],
 *      });
 * 2. Add a side-effect import below (marked REGISTER APPLICATION SHELLS).
 * 3. In the application's vite.config.ts, add the @atlas/shell alias:
 *      '@atlas/shell': path.resolve(__dirname, '../../02_Platform/Atlas_Shell/src/index.ts')
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { Router } from './Router';

// ─── REGISTER APPLICATION SHELLS ─────────────────────────────────────────────
// Each shellConfig.ts calls AppRegistry.register() as a side-effect.
// To add a new app: create shellConfig.ts in its src/, then add it here.

import '../../../../03_Application/WorkoutTracker/src/shellConfig';
import '../../../../03_Application/TaskTracker/src/shellConfig';
import '../../../../03_Application/FoodTracker/src/shellConfig';
import '../../../../03_Application/Chronicle/src/shellConfig';
import '../../../../03_Application/NumericSeries/src/shellConfig';
import '../../../../03_Application/StorageTracker/src/shellConfig';

// ─────────────────────────────────────────────────────────────────────────────

const rootEl = document.getElementById('root');
if (!rootEl) {
  throw new Error('Shell mount failed: no element with id="root" found in index.html.');
}

ReactDOM.createRoot(rootEl).render(
  <React.StrictMode>
    <BrowserRouter>
      <Router />
    </BrowserRouter>
  </React.StrictMode>,
);
