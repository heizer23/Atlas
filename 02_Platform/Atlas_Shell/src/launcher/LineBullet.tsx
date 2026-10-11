/**
 * File: 02_Platform/Atlas_Shell/src/launcher/LineBullet.tsx
 * Component: atlas_shell
 *
 * Role: The round "line" bullet identifying an application (letter on the primary colour). Decorative; the app label always sits beside it.
 */

import React from 'react';

interface LineBulletProps {
  appId?: string;
  label: string;
  size?: 'md' | 'lg';
}

export function LineBullet({ appId, label, size = 'md' }: LineBulletProps): JSX.Element {
  const code = (label.trim().charAt(0) || '?').toUpperCase();
  return (
    <span
      className={`shell-bullet shell-bullet--${size}`}
      aria-hidden="true"
    >
      {code}
    </span>
  );
}
