/**
 * File: 02_Platform/Atlas_Shell/src/navigation/MoreMenu.tsx
 * Component: atlas_shell
 *
 * Role: Mobile secondary menu overlay. Renders the active application's
 * secondaryMenu entries as navigation targets. Triggered by the More button
 * in BottomNav. Uses elevation level 2 per Blueprint DesignLanguage §5.
 * Closes on item selection or backdrop tap.
 */

import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useShell } from '../hooks/useShell';
import type { NavItem } from '../types';

interface MoreMenuProps {
  open: boolean;
  onClose: () => void;
}

export function MoreMenu({ open, onClose }: MoreMenuProps): JSX.Element {
  const { activeApp } = useShell();
  const navigate = useNavigate();
  const location = useLocation();

  const secondaryItems: NavItem[] = activeApp?.secondaryMenu
    ? [...activeApp.secondaryMenu].sort((a, b) => a.order - b.order)
    : [];

  function handleItemClick(path: string) {
    navigate(path);
    onClose();
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className={`shell-more-menu-backdrop${open ? ' shell-more-menu-backdrop--visible' : ''}`}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Menu panel — elevation 2 */}
      <div
        className={`shell-more-menu${open ? ' shell-more-menu--open' : ''}`}
        role="dialog"
        aria-label="More options"
        aria-modal="true"
      >
        {secondaryItems.map((item) => {
          const isActive =
            location.pathname === item.path ||
            location.pathname.startsWith(item.path + '/');
          return (
            <button
              key={item.id}
              type="button"
              className="shell-more-menu__item"
              onClick={() => handleItemClick(item.path)}
              aria-current={isActive ? 'page' : undefined}
            >
              {item.label}
            </button>
          );
        })}
      </div>
    </>
  );
}
