/**
 * File: 02_Platform/Atlas_Shell/tests/AppRegistry.test.ts
 * Component: atlas_shell
 *
 * Role: Unit tests for AppRegistry covering all named failure modes and
 * happy-path contract guarantees as listed in component_architecture.json
 * deferrals.test_writer.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AppRegistry } from '../src/registry/AppRegistry';
import type { AppConfig } from '../src/types';
import React from 'react';

// Minimal valid AppConfig factory — avoids repetition in each test.
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

beforeEach(() => {
  AppRegistry.clear();
});

describe('AppRegistry.register — happy path', () => {
  it('registers a valid config and returns it from getAll()', () => {
    const config = makeConfig();
    AppRegistry.register(config);
    expect(AppRegistry.getAll()).toHaveLength(1);
    expect(AppRegistry.getAll()[0]).toEqual(config);
  });

  it('returns config from getByPath() when path equals basePath', () => {
    const config = makeConfig({ basePath: '/workout' });
    AppRegistry.register(config);
    expect(AppRegistry.getByPath('/workout')).toEqual(config);
  });

  it('returns config from getByPath() when path is a sub-path of basePath', () => {
    const config = makeConfig({ basePath: '/workout' });
    AppRegistry.register(config);
    expect(AppRegistry.getByPath('/workout/log')).toEqual(config);
    expect(AppRegistry.getByPath('/workout/log/123')).toEqual(config);
  });
});

describe('AppRegistry.register — SHELL_DUPLICATE_APP_ID', () => {
  it('skips second registration and logs console.error', () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const first = makeConfig({ appId: 'my-app', label: 'First' });
    const second = makeConfig({ appId: 'my-app', label: 'Second' });

    AppRegistry.register(first);
    AppRegistry.register(second);

    expect(AppRegistry.getAll()).toHaveLength(1);
    expect(AppRegistry.getAll()[0].label).toBe('First');
    expect(errorSpy).toHaveBeenCalledOnce();
    expect(errorSpy.mock.calls[0][0]).toContain('SHELL_DUPLICATE_APP_ID');

    errorSpy.mockRestore();
  });

  it('does not throw on duplicate registration', () => {
    const config = makeConfig();
    AppRegistry.register(config);
    expect(() => AppRegistry.register(config)).not.toThrow();
  });
});

describe('AppRegistry.register — SHELL_INVALID_APP_CONFIG', () => {
  it('skips config with missing appId and logs console.error', () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const bad = { label: 'No ID', basePath: '/x', component: () => null, mobilePrimaryNav: [], desktopNav: [] };

    AppRegistry.register(bad as unknown as AppConfig);

    expect(AppRegistry.getAll()).toHaveLength(0);
    expect(errorSpy).toHaveBeenCalledOnce();
    expect(errorSpy.mock.calls[0][0]).toContain('SHELL_INVALID_APP_CONFIG');
    errorSpy.mockRestore();
  });

  it('skips config with missing label and logs console.error', () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    AppRegistry.register({ appId: 'a', basePath: '/a', component: () => null, mobilePrimaryNav: [], desktopNav: [] } as unknown as AppConfig);
    expect(AppRegistry.getAll()).toHaveLength(0);
    expect(errorSpy.mock.calls[0][0]).toContain('SHELL_INVALID_APP_CONFIG');
    errorSpy.mockRestore();
  });

  it('skips config with missing component and logs console.error', () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const bad = { appId: 'a', label: 'A', basePath: '/a', mobilePrimaryNav: [], desktopNav: [] };
    AppRegistry.register(bad as unknown as AppConfig);
    expect(AppRegistry.getAll()).toHaveLength(0);
    expect(errorSpy.mock.calls[0][0]).toContain('SHELL_INVALID_APP_CONFIG');
    errorSpy.mockRestore();
  });

  it('does not throw on invalid config', () => {
    expect(() => AppRegistry.register(null as unknown as AppConfig)).not.toThrow();
    expect(() => AppRegistry.register({} as AppConfig)).not.toThrow();
  });
});

describe('AppRegistry.getByPath', () => {
  it('returns undefined for an unknown path', () => {
    const config = makeConfig({ basePath: '/workout' });
    AppRegistry.register(config);
    expect(AppRegistry.getByPath('/tasks')).toBeUndefined();
    expect(AppRegistry.getByPath('/workoutextra')).toBeUndefined(); // prefix but no slash
    expect(AppRegistry.getByPath('/')).toBeUndefined();
  });
});

describe('AppRegistry.clear', () => {
  it('resets registry to empty', () => {
    AppRegistry.register(makeConfig({ appId: 'a', basePath: '/a' }));
    AppRegistry.register(makeConfig({ appId: 'b', basePath: '/b' }));
    expect(AppRegistry.getAll()).toHaveLength(2);

    AppRegistry.clear();

    expect(AppRegistry.getAll()).toHaveLength(0);
  });
});

describe('AppRegistry.getAll', () => {
  it('returns apps in registration order', () => {
    AppRegistry.register(makeConfig({ appId: 'first', basePath: '/first' }));
    AppRegistry.register(makeConfig({ appId: 'second', basePath: '/second' }));
    const all = AppRegistry.getAll();
    expect(all[0].appId).toBe('first');
    expect(all[1].appId).toBe('second');
  });

  it('returns a copy — external mutation does not affect registry', () => {
    AppRegistry.register(makeConfig());
    const all = AppRegistry.getAll();
    all.splice(0, 1);
    expect(AppRegistry.getAll()).toHaveLength(1);
  });
});
