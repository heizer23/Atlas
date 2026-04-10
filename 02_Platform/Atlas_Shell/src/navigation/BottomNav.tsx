/**
 * File: 02_Platform/Atlas_Shell/src/navigation/BottomNav.tsx
 * Component: atlas_shell
 *
 * Role: Mobile bottom navigation bar. Renders mobilePrimaryNav items from
 * the active AppConfig. Enforces a hard maximum of 5 items — truncates and
 * emits console.warn with appId and overflow count on violation. Renders a
 * More button when the active AppConfig.secondaryMenu is non-empty.
 *
 * Active state follows Blueprint DesignLanguage §10 Navigation Bar:
 *   primary-container indicator pill behind the active icon/label.
 *
 * Failure mode: SHELL_MOBILE_NAV_OVERFLOW — console.warn + truncate to 5.
 */

import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useShell } from '../hooks/useShell';
import { MoreMenu } from './MoreMenu';
import type { NavItem } from '../types';

const MAX_BOTTOM_NAV_ITEMS = 5;

interface BottomNavItemProps {
  item: NavItem;
  isActive: boolean;
}

function BottomNavItem({ item, isActive }: BottomNavItemProps): JSX.Element {
  const navigate = useNavigate();

  return (
    <button
      type="button"
      className={`shell-bottom-nav-item${isActive ? ' shell-bottom-nav-item--active' : ''}`}
      onClick={() => navigate(item.path)}
      aria-current={isActive ? 'page' : undefined}
    >
      <span className="type-label">{item.label}</span>
      <span className="shell-bottom-nav-item__indicator" aria-hidden="true" />
    </button>
  );
}

export function BottomNav(): JSX.Element {
  const { activeApp } = useShell();
  const location = useLocation();
  const [moreOpen, setMoreOpen] = useState(false);

  const hasSecondaryMenu =
    Array.isArray(activeApp?.secondaryMenu) && (activeApp!.secondaryMenu!.length > 0);

  let primaryItems: NavItem[] = activeApp
    ? [...activeApp.mobilePrimaryNav].sort((a, b) => a.order - b.order)
    : [];

  // Enforce 5-item hard cap — SHELL_MOBILE_NAV_OVERFLOW
  if (primaryItems.length > MAX_BOTTOM_NAV_ITEMS) {
    const overflowCount = primaryItems.length - MAX_BOTTOM_NAV_ITEMS;
    console.warn(
      `SHELL_MOBILE_NAV_OVERFLOW: appId "${activeApp!.appId}" declared ${primaryItems.length} mobilePrimaryNav items; truncating to ${MAX_BOTTOM_NAV_ITEMS} (overflow count: ${overflowCount}).`,
    );
    primaryItems = primaryItems.slice(0, MAX_BOTTOM_NAV_ITEMS);
  }

  // Find the most-specific matching nav item to avoid false positives when a
  // short path (e.g. '/food') is a prefix of more specific paths ('/food/report').
  const activeItemId = primaryItems.reduce<string | null>((bestId, item) => {
    const matches =
      location.pathname === item.path ||
      location.pathname.startsWith(item.path + '/');
    if (!matches) return bestId;
    const bestItem = bestId ? primaryItems.find((i) => i.id === bestId) : null;
    if (!bestItem) return item.id;
    return item.path.length > bestItem.path.length ? item.id : bestId;
  }, null);

  return (
    <>
      <nav className="shell-bottom-nav" aria-label="Mobile navigation">
        {primaryItems.map((item) => (
          <BottomNavItem
            key={item.id}
            item={item}
            isActive={item.id === activeItemId}
          />
        ))}

        {hasSecondaryMenu && (
          <button
            type="button"
            className="shell-bottom-nav-item"
            onClick={() => setMoreOpen(true)}
            aria-haspopup="dialog"
            aria-expanded={moreOpen}
          >
            <span className="type-label">More</span>
            <span className="shell-bottom-nav-item__indicator" aria-hidden="true" />
          </button>
        )}
      </nav>

      {hasSecondaryMenu && (
        <MoreMenu open={moreOpen} onClose={() => setMoreOpen(false)} />
      )}
    </>
  );
}
