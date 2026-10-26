import { defineConfig } from '@playwright/test';

/**
 * End-to-end tests of the host with the real backend: soup-server's
 * tests/e2e_server.py (in-memory tools, no Docker) on 8081 and `ng serve`
 * with the "e2e" configuration (environment.e2e.ts) on 4201. Own ports,
 * and servers already listening are never reused: the tests must not run
 * against (and change) a development stack on 8080/4200, e.g. docker
 * compose. Uses the installed Chrome (no browser download). Run: npm run e2e
 */

export const E2E_API_PORT = 8081;
export const E2E_APP_PORT = 4201;

export default defineConfig({
  testDir: 'e2e',
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: `http://localhost:${E2E_APP_PORT}`,
    channel: 'chrome',
    headless: true,
    trace: 'retain-on-failure'
  },
  webServer: [
    {
      command: 'python -m tests.e2e_server',
      cwd: '../soup-server',
      env: { SOUP_E2E_PORT: String(E2E_API_PORT) },
      url: `http://127.0.0.1:${E2E_API_PORT}/api/v3/health`,
      reuseExistingServer: false,
      timeout: 60_000
    },
    {
      command: `npx ng serve --configuration e2e --port ${E2E_APP_PORT}`,
      url: `http://localhost:${E2E_APP_PORT}`,
      reuseExistingServer: false,
      timeout: 240_000
    }
  ]
});
