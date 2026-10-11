import React, { useEffect, useRef, useState } from 'react';
import { btnStyle, primaryBtnStyle } from '../styles';

// ── Action menu (Sprint12_FSRSAndUXOverhaul) ────────────────────────────────
//
// Generic primary-button + accessible dropdown, replacing a row of buttons
// at the essay header and at each section's end (10_architecture.json
// internal_flow steps 9-10; see button_nav_inventory for the full pre/post
// mapping). role=menu/menuitem, Escape + click-outside to close, operable by
// keyboard and touch. Reuses existing btnStyle/primaryBtnStyle tokens only —
// no new design tokens.

export interface ActionMenuItem {
  label: string;
  onClick: () => void;
  disabled?: boolean;
}

export const actionMenuWrapStyle: React.CSSProperties = {
  position: 'relative',
  display: 'inline-flex',
  gap: 8,
};

export const actionMenuDropdownStyle: React.CSSProperties = {
  position: 'absolute',
  top: '100%',
  left: 0,
  marginTop: 4,
  background: 'var(--md-sys-color-surface)',
  border: '1px solid var(--md-sys-color-outline-variant)',
  borderRadius: 8,
  boxShadow: 'var(--elevation-1)',
  padding: 4,
  minWidth: 180,
  zIndex: 50,
  display: 'flex',
  flexDirection: 'column',
};

export const actionMenuItemStyle: React.CSSProperties = {
  display: 'block',
  width: '100%',
  textAlign: 'left',
  padding: '0 12px',
  minHeight: 44,
  border: 'none',
  background: 'transparent',
  cursor: 'pointer',
  fontFamily: 'inherit',
  fontSize: 14,
  borderRadius: 6,
  color: 'var(--md-sys-color-on-surface)',
};

export function ActionMenu({
  primary,
  items,
  align = 'left',
}: {
  primary?: { label: string; onClick: () => void; disabled?: boolean; title?: string };
  items: ActionMenuItem[];
  align?: 'left' | 'right';
}) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  return (
    <div ref={wrapRef} style={actionMenuWrapStyle}>
      {primary && (
        <button
          style={primaryBtnStyle}
          disabled={primary.disabled}
          title={primary.title}
          onClick={primary.onClick}
        >
          {primary.label}
        </button>
      )}
      {items.length > 0 && (
        <>
          <button
            style={btnStyle}
            aria-haspopup="menu"
            aria-expanded={open}
            aria-label="More actions"
            onClick={() => setOpen(o => !o)}
          >
            More ▾
          </button>
          {open && (
            <div role="menu" style={align === 'right' ? { ...actionMenuDropdownStyle, left: 'auto', right: 0 } : actionMenuDropdownStyle}>
              {items.map((item, i) => (
                <button
                  key={i}
                  role="menuitem"
                  style={actionMenuItemStyle}
                  disabled={item.disabled}
                  onClick={() => {
                    setOpen(false);
                    item.onClick();
                  }}
                >
                  {item.label}
                </button>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
