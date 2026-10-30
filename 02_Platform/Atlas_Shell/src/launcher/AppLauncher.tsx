/**
 * File: 02_Platform/Atlas_Shell/src/launcher/AppLauncher.tsx
 * Component: atlas_shell
 *
 * Role: Root-path view and launcher panel. Renders all registered
 * applications from AppRegistry.getAll() as selectable rows under a hero
 * header. Each row shows an icon, the label, and — when the app registers a
 * launcherSummary provider — a live status block (line, activity dots, short
 * list). The shell renders the returned structure only; it never interprets it.
 * Handles empty registry with an explicit SHELL_NO_APPS_REGISTERED empty state.
 */

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppRegistry } from '../registry/AppRegistry';
import type { AppConfig, LauncherDot, LauncherSummary } from '../types';
import { LineBullet } from './LineBullet';
import { sortByRecency } from '../shell/recency';

function DotStrip({ groups }: { groups: LauncherDot[][] }): JSX.Element {
  return (
    <div className="shell-dots" aria-hidden="true">
      {groups.map((group, g) => (
        <span key={g} className="shell-dots__group">
          {group.map((dot, i) => (
            <span
              key={i}
              className={
                'shell-dots__dot' +
                (dot.filled ? ' shell-dots__dot--filled' : '') +
                (dot.ring ? ' shell-dots__dot--ring' : '') +
                (dot.today ? ' shell-dots__dot--today' : '')
              }
            />
          ))}
        </span>
      ))}
    </div>
  );
}

function SummaryBlock({ summary }: { summary: LauncherSummary }): JSX.Element {
  const items = (summary.items ?? []).slice(0, 3);
  return (
    <>
      <span className="shell-app-entry__line">
        {summary.line}
        {summary.meta ? <span className="shell-app-entry__meta"> · {summary.meta}</span> : null}
      </span>
      {summary.dots && summary.dots.length > 0 ? <DotStrip groups={summary.dots} /> : null}
      {items.length > 0 ? (
        <ul className="shell-app-entry__items">
          {items.map((item, i) => (
            <li key={i} className="shell-app-entry__item">
              <span className="shell-app-entry__item-box" aria-hidden="true" />
              <span className="shell-app-entry__item-label">{item.label}</span>
              {item.when ? <span className="shell-app-entry__item-when">{item.when}</span> : null}
            </li>
          ))}
        </ul>
      ) : null}
      {summary.more ? <span className="shell-app-entry__more">{summary.more}</span> : null}
    </>
  );
}

function AppEntry({ config }: { config: AppConfig }): JSX.Element {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<LauncherSummary | null>(null);

  useEffect(() => {
    if (!config.launcherSummary) return;
    let cancelled = false;
    config
      .launcherSummary()
      .then((s) => { if (!cancelled) setSummary(s); })
      .catch(() => { /* label-only row on failure */ });
    return () => { cancelled = true; };
  }, [config]);

  const tone = config.launcherTone ?? 'blue';

  return (
    <button
      type="button"
      className="shell-app-entry"
      onClick={() => navigate(config.basePath)}
    >
      {config.launcherIcon ? (
        <span className={`shell-app-icon shell-app-icon--${tone}`} aria-hidden="true">
          <span className="material-symbols-rounded">{config.launcherIcon}</span>
        </span>
      ) : (
        <LineBullet appId={config.appId} label={config.label} size="lg" />
      )}
      <span className="shell-app-entry__body">
        <span className="shell-app-entry__label">{config.label}</span>
        {summary ? <SummaryBlock summary={summary} /> : null}
      </span>
    </button>
  );
}

export function AppLauncher(): JSX.Element {
  const apps = sortByRecency(AppRegistry.getAll());

  return (
    <div className="shell-launcher">
      <header className="shell-launcher__hero">
        <h1 className="shell-launcher__heading">Atlas</h1>
      </header>

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
