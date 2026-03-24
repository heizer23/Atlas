/**
 * File: 02_Platform/02_Atlas_Shell/src/navigation/Sidebar.tsx
 * Component: atlas_shell
 *
 * Role: Desktop and tablet left-sidebar navigation component.
 * - Desktop (≥1024px): always visible (persistent).
 * - Tablet (768–1023px): hidden by default; slides in via hamburger toggle.
 * Renders an AppLauncher button at the top, then desktopNav items from the
 * active AppConfig sorted by NavItem.order.
 *
 * Active state follows Blueprint DesignLanguage §8 (Selected state):
 *   primary-container background, on-primary-container text.
 */

import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useShell } from '../hooks/useShell';
import type { NavItem } from '../types';

/** True when the viewport is in the tablet range (768–1023px). */
function useIsTablet(): boolean {
  const [isTablet, setIsTablet] = useState<boolean>(
    () => window.innerWidth >= 768 && window.innerWidth < 1024,
  );

  useEffect(() => {
    const mq = window.matchMedia('(min-width: 768px) and (max-width: 1023px)');
    const handler = (e: MediaQueryListEvent) => setIsTablet(e.matches);
    mq.addEventListener('change', handler);
    setIsTablet(mq.matches);
    return () => mq.removeEventListener('change', handler);
  }, []);

  return isTablet;
}

interface SidebarNavItemProps {
  item: NavItem;
  isActive: boolean;
  onClick?: () => void;
}

function SidebarNavItem({ item, isActive, onClick }: SidebarNavItemProps): JSX.Element {
  const navigate = useNavigate();

  function handleClick() {
    navigate(item.path);
    onClick?.();
  }

  return (
    <button
      type="button"
      className={`shell-sidebar-nav-item${isActive ? ' shell-sidebar-nav-item--active' : ''}`}
      onClick={handleClick}
      aria-current={isActive ? 'page' : undefined}
    >
      {item.label}
    </button>
  );
}

export function Sidebar(): JSX.Element {
  const { activeApp } = useShell();
  const location = useLocation();
  const navigate = useNavigate();
  const isTablet = useIsTablet();
  const [isOpen, setIsOpen] = useState(false);

  // Close sidebar when navigating on tablet
  useEffect(() => {
    if (isTablet) {
      setIsOpen(false);
    }
  }, [location.pathname, isTablet]);

  // Close sidebar when switching from tablet to desktop
  useEffect(() => {
    if (!isTablet) {
      setIsOpen(false);
    }
  }, [isTablet]);

  const navItems = activeApp
    ? [...activeApp.desktopNav].sort((a, b) => a.order - b.order)
    : [];

  // Find the most-specific matching nav item to avoid false positives when a
  // short path (e.g. '/food') is a prefix of more specific paths ('/food/report').
  const activeItemId = navItems.reduce<string | null>((bestId, item) => {
    const matches =
      location.pathname === item.path ||
      location.pathname.startsWith(item.path + '/');
    if (!matches) return bestId;
    const bestItem = bestId ? navItems.find((i) => i.id === bestId) : null;
    if (!bestItem) return item.id;
    return item.path.length > bestItem.path.length ? item.id : bestId;
  }, null);

  function handleLauncherClick() {
    navigate('/');
    if (isTablet) setIsOpen(false);
  }

  return (
    <>
      {/* Hamburger toggle button — shown only on tablet */}
      {isTablet && (
        <button
          type="button"
          className="shell-hamburger"
          onClick={() => setIsOpen((prev) => !prev)}
          aria-label={isOpen ? 'Close navigation' : 'Open navigation'}
          aria-expanded={isOpen}
        >
          {/* Simple hamburger icon using text characters; no icon library dependency */}
          <span aria-hidden="true">{isOpen ? '✕' : '☰'}</span>
        </button>
      )}

      {/* Backdrop — tablet overlay dismiss */}
      {isTablet && (
        <div
          className={`shell-sidebar-backdrop${isOpen ? ' shell-sidebar-backdrop--visible' : ''}`}
          onClick={() => setIsOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar panel */}
      <nav
        className={`shell-sidebar${isTablet && isOpen ? ' shell-sidebar--open' : ''}`}
        aria-label="Application navigation"
      >
        <button
          type="button"
          className="shell-sidebar__launcher-btn"
          onClick={handleLauncherClick}
        >
          Atlas
        </button>

        <div className="shell-sidebar__nav">
          {navItems.map((item) => (
            <SidebarNavItem
              key={item.id}
              item={item}
              isActive={item.id === activeItemId}
              onClick={isTablet ? () => setIsOpen(false) : undefined}
            />
          ))}
        </div>
      </nav>
    </>
  );
}
