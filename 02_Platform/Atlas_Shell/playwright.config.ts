import { defineConfig } from '@playwright/test';

const BASE_URL = process.env.BASE_URL ?? 'http://atlas-shell-test';

// UI tests mutate data. The ordinary shell proxies to production backends, so refuse it.
if (/^https?:\/\/atlas-shell(:\d+)?\/?$/.test(BASE_URL)) {
  throw new Error(`Refusing BASE_URL=${BASE_URL}: that is the production shell. Use atlas-shell-test.`);
}

export default defineConfig({
  // Scan from repo root so explicit test paths in other layers are found.
  // Config lives at 02_Platform/Atlas_Shell/ — two levels up is repo root.
  testDir: '../..',
  // Only pick up Playwright spec files; ignore vitest/jest files in Shell/tests/
  testMatch: '**/tests/ui/**/*.spec.ts',
  // Write artifacts to a writable location (the /repo mount is read-only in the container)
  outputDir: '/tmp/playwright-results',
  use: {
    baseURL: BASE_URL,
    headless: true,
    // crypto.randomUUID() requires a secure context (HTTPS or localhost).
    // The atlas-shell container is plain HTTP — treat it as secure so apiFetch works.
    launchOptions: {
      args: [`--unsafely-treat-insecure-origin-as-secure=${BASE_URL}`],
    },
  },
});
