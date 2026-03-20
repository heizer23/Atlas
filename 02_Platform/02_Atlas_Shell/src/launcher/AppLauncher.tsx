/**
 * File: 02_Platform/02_Atlas_Shell/src/launcher/AppLauncher.tsx
 * Component: atlas_shell
 *
 * Role: Root-path view and launcher panel. Renders all registered
 * applications from AppRegistry.getAll() as selectable entries.
 * Handles empty registry with an explicit SHELL_NO_APPS_REGISTERED
 * empty state.
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import { AppRegistry } from '../registry/AppRegistry';
import type { AppConfig } from '../types';

interface AppEntryProps {
  config: AppConfig;
}

function AppEntry({ config }: AppEntryProps): JSX.Element {
  const navigate = useNavigate();

  return (
    <button
      type="button"
      className="shell-app-entry"
      onClick={() => navigate(config.basePath)}
    >
      <span className="shell-app-entry__label">{config.label}</span>
      <span className="shell-app-entry__path">{config.basePath}</span>
    </button>
  );
}

export function AppLauncher(): JSX.Element {
  const apps = AppRegistry.getAll();

  return (
    <div className="shell-launcher">
      <h1 className="shell-launcher__heading type-headline">Atlas</h1>

      {apps.length === 0 ? (
        // SHELL_NO_APPS_REGISTERED — explicit empty state
        <p className="shell-launcher__empty">
          No applications are registered. Register an application by calling{' '}
          <code>AppRegistry.register(config)</code> from its{' '}
          <code>shellConfig.ts</code>.
        </p>
      ) : (
        <div className="shell-launcher__grid">
          {apps.map((app) => (
            <AppEntry key={app.appId} config={app} />
          ))}
        </div>
      )}
    </div>
  );
}
