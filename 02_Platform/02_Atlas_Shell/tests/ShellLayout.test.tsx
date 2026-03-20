/**
 * File: 02_Platform/02_Atlas_Shell/tests/ShellLayout.test.tsx
 * Component: atlas_shell
 *
 * Role: Component tests for ShellLayout covering:
 *   - desktop viewport (≥1024px): Sidebar rendered, BottomNav not rendered
 *   - mobile viewport (<768px): BottomNav rendered, Sidebar not rendered
 *   - tablet viewport (768–1023px): collapsible Sidebar with hamburger toggle
 *
 * Viewport breakpoints are driven by window.matchMedia in ShellLayout/Sidebar.
 * Tests mock matchMedia to control the effective breakpoint.
 */

import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ShellLayout } from '../src/shell/ShellLayout';
import { AppRegistry } from '../src/registry/AppRegistry';
import type { AppConfig } from '../src/types';

function makeConfig(overrides: Partial<AppConfig> = {}): AppConfig {
  return {
    appId: 'test-app',
    label: 'Test',
    basePath: '/test',
    component: () => React.createElement('div'),
    mobilePrimaryNav: [],
    desktopNav: [{ id: 'home', label: 'Home', path: '/test', order: 1 }],
    secondaryMenu: [],
    ...overrides,
  };
}

/**
 * Mock window.matchMedia to simulate a given viewport width.
 * ShellLayout uses (max-width: 767px) for mobile detection.
 * Sidebar uses (min-width: 768px) and (max-width: 1023px) for tablet detection.
 */
function mockMatchMedia(width: number) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => {
      // Evaluate the query against the given width
      let matches = false;
      if (query === '(max-width: 767px)') matches = width < 768;
      if (query === '(min-width: 768px) and (max-width: 1023px)') matches = width >= 768 && width < 1024;
      return {
        matches,
        media: query,
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      };
    },
  });
  // Also set innerWidth for the useState initializer
  Object.defineProperty(window, 'innerWidth', { writable: true, value: width });
}

function renderShellLayout(path = '/test') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ShellLayout>
        <div data-testid="content">Content</div>
      </ShellLayout>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  AppRegistry.clear();
  AppRegistry.register(makeConfig());
});

describe('ShellLayout — desktop viewport (≥1024px)', () => {
  it('renders Sidebar and not BottomNav', () => {
    mockMatchMedia(1440);
    renderShellLayout();

    expect(screen.getByRole('navigation', { name: /application navigation/i })).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: /mobile navigation/i })).not.toBeInTheDocument();
  });
});

describe('ShellLayout — mobile viewport (<768px)', () => {
  it('renders BottomNav and not Sidebar', () => {
    mockMatchMedia(375);
    renderShellLayout();

    expect(screen.getByRole('navigation', { name: /mobile navigation/i })).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: /application navigation/i })).not.toBeInTheDocument();
  });
});

describe('ShellLayout — tablet viewport (768–1023px)', () => {
  it('renders Sidebar in collapsed state with a hamburger toggle button', () => {
    mockMatchMedia(800);
    renderShellLayout();

    // Sidebar should be present but collapsed (no shell-sidebar--open class initially)
    const sidebar = screen.getByRole('navigation', { name: /application navigation/i });
    expect(sidebar).toBeInTheDocument();
    expect(sidebar).not.toHaveClass('shell-sidebar--open');

    // Hamburger button should be present
    const hamburger = screen.getByRole('button', { name: /open navigation/i });
    expect(hamburger).toBeInTheDocument();
  });

  it('opens Sidebar when hamburger is clicked', () => {
    mockMatchMedia(800);
    renderShellLayout();

    const hamburger = screen.getByRole('button', { name: /open navigation/i });
    fireEvent.click(hamburger);

    const sidebar = screen.getByRole('navigation', { name: /application navigation/i });
    expect(sidebar).toHaveClass('shell-sidebar--open');
  });

  it('closes Sidebar when hamburger is clicked again', () => {
    mockMatchMedia(800);
    renderShellLayout();

    const hamburger = screen.getByRole('button', { name: /open navigation/i });
    fireEvent.click(hamburger);
    // Now close
    const closeBtn = screen.getByRole('button', { name: /close navigation/i });
    fireEvent.click(closeBtn);

    const sidebar = screen.getByRole('navigation', { name: /application navigation/i });
    expect(sidebar).not.toHaveClass('shell-sidebar--open');
  });
});

describe('ShellLayout — context provision', () => {
  it('renders children', () => {
    mockMatchMedia(1440);
    renderShellLayout();
    expect(screen.getByTestId('content')).toBeInTheDocument();
  });
});
