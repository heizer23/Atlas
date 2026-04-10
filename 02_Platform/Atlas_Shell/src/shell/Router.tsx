/**
 * File: 02_Platform/Atlas_Shell/src/shell/Router.tsx
 * Component: atlas_shell
 *
 * Role: Routing component. Does NOT own BrowserRouter — that is mounted in
 * main.tsx. Renders <Routes> with three cases:
 *   1. path='/'           → <AppLauncher />
 *   2. path='{basePath}/*' → <ShellLayout><Suspense><app.component /></Suspense></ShellLayout>
 *   3. path='*'           → <ShellNotFound />
 *
 * Failure mode: SHELL_ROUTE_NOT_FOUND — ShellNotFound view.
 */

import React, { Suspense } from 'react';
import { Routes, Route, Link } from 'react-router-dom';
import { AppRegistry } from '../registry/AppRegistry';
import { ShellLayout } from './ShellLayout';
import { AppLauncher } from '../launcher/AppLauncher';

function LoadingFallback(): JSX.Element {
  return <div className="shell-loading">Loading…</div>;
}

/** Rendered when no registered app matches the current path (SHELL_ROUTE_NOT_FOUND). */
function ShellNotFound(): JSX.Element {
  return (
    <div className="shell-not-found">
      <p className="shell-not-found__code">404</p>
      <p className="shell-not-found__message">
        This path is not registered with the Atlas Shell.
      </p>
      <Link to="/" className="shell-not-found__link">
        Go to launcher
      </Link>
    </div>
  );
}

export function Router(): JSX.Element {
  const apps = AppRegistry.getAll();

  return (
    <Routes>
      {/* Root path — AppLauncher */}
      <Route path="/" element={<AppLauncher />} />

      {/* One route per registered application */}
      {apps.map((app) => {
        const AppComponent = app.component;
        return (
          <Route
            key={app.appId}
            path={`${app.basePath}/*`}
            element={
              <ShellLayout>
                <Suspense fallback={<LoadingFallback />}>
                  <AppComponent />
                </Suspense>
              </ShellLayout>
            }
          />
        );
      })}

      {/* Catch-all — SHELL_ROUTE_NOT_FOUND */}
      <Route path="*" element={<ShellNotFound />} />
    </Routes>
  );
}
