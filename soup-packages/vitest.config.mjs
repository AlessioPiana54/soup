// Unit tests of the app/ part of the packages (npm test): DOM in jsdom.
// @soup/sdk is resolved to its sources: its package entry is the built
// sdk/dist, which a fresh checkout (CI) does not have before build:packages.
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  resolve: {
    alias: { '@soup/sdk': fileURLToPath(new URL('./sdk/src/index.ts', import.meta.url)) }
  },
  test: {
    environment: 'jsdom',
    include: ['*/app/test/**/*.test.ts', 'sdk/test/**/*.test.ts']
  }
});
