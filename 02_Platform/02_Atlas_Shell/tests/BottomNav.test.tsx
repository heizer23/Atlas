/**
 * File: 02_Platform/02_Atlas_Shell/tests/BottomNav.test.tsx
 * Component: atlas_shell
 *
 * Role: Component tests for BottomNav covering:
 *   - 5-item cap enforcement (SHELL_MOBILE_NAV_OVERFLOW)
 *   - console.warn on overflow with appId and count
 *   - More button visibility when secondaryMenu is non-empty / empty
 *   - MoreMenu opens on More button tap
 */

import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ShellContext } from '../src/shell/ShellContext';
import { BottomNav } from '../src/navigation/BottomNav';
import { AppRegistry } from '../src/registry/AppRegistry';
import type { AppConfig, NavItem } from '../src/types';

function makeNavItem(id: string, order: number): NavItem {
  return { id, label: id, path: `/${id}`, order };
}

function makeConfig(overrides: Partial<AppConfig> = {}): AppConfig {
  return {
    appId: 'test-app',
    label: 'Test App',
    basePath: '/test',
    component: () => React.createElement('div'),
    mobilePrimaryNav: [],
    desktopNav: [],
    ...overrides,
  };
}

function renderWithContext(activeApp: AppConfig | undefined, allApps: AppConfig[] = []) {
  return render(
    <MemoryRouter initialEntries={['/test']}>
      <ShellContext.Provider value={{ activeApp, allApps }}>
        <BottomNav />
      </ShellContext.Provider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  AppRegistry.clear();
});

describe('BottomNav — item rendering', () => {
  it('renders all 5 items when exactly 5 mobilePrimaryNav items are provided', () => {
    const config = makeConfig({
      mobilePrimaryNav: [1, 2, 3, 4, 5].map((n) => makeNavItem(`item${n}`, n)),
    });
    renderWithContext(config);
    expect(screen.getAllByRole('button').filter((b) => b.textContent?.includes('item'))).toHaveLength(5);
  });

  it('truncates to 5 and emits console.warn with appId and overflow count when 6 items provided', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const config = makeConfig({
      appId: 'overflow-app',
      mobilePrimaryNav: [1, 2, 3, 4, 5, 6].map((n) => makeNavItem(`item${n}`, n)),
    });
    renderWithContext(config);

    // Only 5 nav items (not counting More button)
    const navItems = screen.getAllByRole('button').filter((b) => b.textContent?.includes('item'));
    expect(navItems).toHaveLength(5);

    expect(warnSpy).toHaveBeenCalledOnce();
    const warnMsg = warnSpy.mock.calls[0][0] as string;
    expect(warnMsg).toContain('SHELL_MOBILE_NAV_OVERFLOW');
    expect(warnMsg).toContain('overflow-app');
    expect(warnMsg).toContain('1'); // overflow count

    warnSpy.mockRestore();
  });
});

describe('BottomNav — More button', () => {
  it('renders More button when secondaryMenu is non-empty', () => {
    const config = makeConfig({
      secondaryMenu: [makeNavItem('settings', 1)],
    });
    renderWithContext(config);
    expect(screen.getByText('More')).toBeInTheDocument();
  });

  it('does not render More button when secondaryMenu is empty', () => {
    const config = makeConfig({ secondaryMenu: [] });
    renderWithContext(config);
    expect(screen.queryByText('More')).not.toBeInTheDocument();
  });

  it('does not render More button when secondaryMenu is undefined', () => {
    const config = makeConfig({ secondaryMenu: undefined });
    renderWithContext(config);
    expect(screen.queryByText('More')).not.toBeInTheDocument();
  });

  it('opens MoreMenu when More button is tapped', () => {
    const config = makeConfig({
      secondaryMenu: [makeNavItem('settings', 1)],
    });
    renderWithContext(config);

    const moreBtn = screen.getByText('More');
    // Before click: MoreMenu dialog exists but not open (no --open class)
    const dialog = screen.getByRole('dialog', { name: /more options/i });
    expect(dialog).not.toHaveClass('shell-more-menu--open');

    fireEvent.click(moreBtn);

    // After click: dialog has the open class
    expect(dialog).toHaveClass('shell-more-menu--open');
  });
});
