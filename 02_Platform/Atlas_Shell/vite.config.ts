/// <reference types="vitest" />
/**
 * File: 02_Platform/Atlas_Shell/vite.config.ts
 * Component: atlas_shell
 *
 * Role: Vite configuration for the standalone shell application.
 * Defines two module aliases:
 *   @atlas/shell   → ./src/index.ts                   (self-reference)
 *   @platform-ui   → ./platform-ui/                    (platform UI primitives, owned by shell)
 */

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@atlas/shell':    path.resolve(__dirname, './src/index.ts'),
      '@platform-ui':   path.resolve(__dirname, './platform-ui'),
      // App source files live outside the shell root so Vite can't find their
      // dependencies via normal node_modules traversal. Pin shared packages to
      // the shell's own node_modules to guarantee a single copy and correct resolution.
      'react':          path.resolve(__dirname, 'node_modules/react'),
      'react-dom':      path.resolve(__dirname, 'node_modules/react-dom'),
      'react-router-dom': path.resolve(__dirname, 'node_modules/react-router-dom'),
      'recharts':       path.resolve(__dirname, 'node_modules/recharts'),
      '@fullcalendar/react':        path.resolve(__dirname, 'node_modules/@fullcalendar/react'),
      '@fullcalendar/core':         path.resolve(__dirname, 'node_modules/@fullcalendar/core'),
      '@fullcalendar/daygrid':      path.resolve(__dirname, 'node_modules/@fullcalendar/daygrid'),
      '@fullcalendar/timegrid':     path.resolve(__dirname, 'node_modules/@fullcalendar/timegrid'),
      '@fullcalendar/interaction':  path.resolve(__dirname, 'node_modules/@fullcalendar/interaction'),
      'react-markdown':  path.resolve(__dirname, 'node_modules/react-markdown'),
    },
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      // Each backend runs on its own port locally (matches compose.yml port mappings).
      // Add a new entry here when a new application backend is integrated.
      '/api/workout':        { target: 'http://localhost:8011', changeOrigin: true },
      '/api/tasks':          { target: 'http://localhost:8010', changeOrigin: true },
      '/api/food':           { target: 'http://localhost:8012', changeOrigin: true },
      '/api/chronicle':      { target: 'http://localhost:8013', changeOrigin: true },
      '/api/notifications':  { target: 'http://localhost:8020', changeOrigin: true },
      '/api/devices':        { target: 'http://localhost:8020', changeOrigin: true },
      '/api/linking':        { target: 'http://localhost:8040', changeOrigin: true },
      '/api/series':         { target: 'http://localhost:8014', changeOrigin: true },
      '/api/batch/series':   { target: 'http://localhost:8014', changeOrigin: true },
      '/api/cal':            { target: 'http://localhost:8023', changeOrigin: true },
      '/api/essaycards':     { target: 'http://localhost:8024', changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    alias: {
      '@atlas/shell': path.resolve(__dirname, './src/index.ts'),
      '@platform-ui': path.resolve(__dirname, './platform-ui'),
    },
  },
});
