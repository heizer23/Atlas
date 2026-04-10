/**
 * File: 02_Platform/Atlas_Shell/tests/Router.test.tsx
 * Component: atlas_shell
 *
 * Role: Component tests for Router covering:
 *   - root path '/' renders AppLauncher
 *   - known basePath renders the correct application outlet
 *   - unknown path renders ShellNotFound
 */

import React from 'react';
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Router } from '../src/shell/Router';
import { AppRegistry } from '../src/registry/AppRegistry';
import type { AppConfig } from '../src/types';

function FakeApp(): JSX.Element {
  return <div data-testid="fake-app">Fake App Content</div>;
}

function makeConfig(overrides: Partial<AppConfig> = {}): AppConfig {
  return {
    appId: 'fake-app',
    label: 'Fake App',
    basePath: '/fake',
    component: FakeApp,
    mobilePrimaryNav: [],
    desktopNav: [],
    ...overrides,
  };
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Router />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  AppRegistry.clear();
  // Suppress matchMedia not implemented warnings in jsdom
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  });
});

describe('Router — root path', () => {
  it('renders AppLauncher at "/"', () => {
    renderAt('/');
    // AppLauncher renders the Atlas heading
    expect(screen.getByRole('heading', { name: /atlas/i })).toBeInTheDocument();
  });
});

describe('Router — known basePath', () => {
  it('renders the registered application component at its basePath', () => {
    AppRegistry.register(makeConfig());
    renderAt('/fake');
    expect(screen.getByTestId('fake-app')).toBeInTheDocument();
  });

  it('renders the registered application component at a sub-path', () => {
    AppRegistry.register(makeConfig());
    renderAt('/fake/dashboard');
    expect(screen.getByTestId('fake-app')).toBeInTheDocument();
  });
});

describe('Router — unknown path', () => {
  it('renders ShellNotFound for an unmatched path', () => {
    renderAt('/does-not-exist');
    expect(screen.getByText('404')).toBeInTheDocument();
    expect(screen.getByText(/not registered/i)).toBeInTheDocument();
  });
});
