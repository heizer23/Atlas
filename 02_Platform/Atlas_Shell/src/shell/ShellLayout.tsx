/**
 * File: 02_Platform/Atlas_Shell/src/shell/ShellLayout.tsx
 * Component: atlas_shell
 *
 * Role: React layout component. Receives children from Router. Derives
 * activeApp via prefix-match on location.pathname against registered
 * basePaths. Provides ShellContext to the child tree. Renders Sidebar
 * (≥768px) or BottomNav (<768px) alongside children.
 *
 * Viewport selection is handled in CSS (shell.css); the JS side uses a
 * window.matchMedia hook to pass the breakpoint class to the layout wrapper
 * so Sidebar and BottomNav know whether to render.
 */

import React, { useMemo, useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ShellContext } from './ShellContext';
import { AppRegistry } from '../registry/AppRegistry';
import { Sidebar } from '../navigation/Sidebar';
import { LineBullet } from '../launcher/LineBullet';
import { markOpened } from './recency';
import { BottomNav } from '../navigation/BottomNav';
import './shell.css';

function MobileHeader({ appId, label }: { appId: string; label: string }): JSX.Element {
  const navigate = useNavigate();
  return (
    <button
      type="button"
      className="shell-mobile-header"
      onClick={() => navigate('/')}
      aria-label={`${label} — back to launcher`}
    >
      <svg className="shell-mobile-header__chevron" width="20" height="20" viewBox="0 0 20 20" aria-hidden="true">
        <path d="M12.5 4 6.5 10l6 6" fill="none" stroke="currentColor" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <LineBullet appId={appId} label={label} />
      <span className="shell-mobile-header__title">{label}</span>
    </button>
  );
}

/** Returns true when the viewport is mobile (<768px). */
function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState<boolean>(() => window.innerWidth < 768);

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 767px)');
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mq.addEventListener('change', handler);
    // Keep state in sync if the initial read was stale
    setIsMobile(mq.matches);
    return () => mq.removeEventListener('change', handler);
  }, []);

  return isMobile;
}

interface ShellLayoutProps {
  children: React.ReactNode;
}

export function ShellLayout({ children }: ShellLayoutProps): JSX.Element {
  const location = useLocation();
  const isMobile = useIsMobile();
  const allApps = AppRegistry.getAll();

  const activeApp = useMemo(
    () => AppRegistry.getByPath(location.pathname),
    [location.pathname, allApps.length], // re-derive when registry changes
  );

  // Record the open for launcher ordering (per-device, best effort).
  useEffect(() => {
    if (activeApp) markOpened(activeApp.appId);
  }, [activeApp?.appId]);

  const contextValue = useMemo(
    () => ({ activeApp, allApps }),
    [activeApp, allApps],
  );

  return (
    <ShellContext.Provider value={contextValue}>
      <div className="shell-root">
        {!isMobile && <Sidebar />}
        {isMobile && activeApp && <MobileHeader appId={activeApp.appId} label={activeApp.label} />}
        <main className="shell-content">
          {children}
        </main>
        {isMobile && <BottomNav />}
      </div>
    </ShellContext.Provider>
  );
}
