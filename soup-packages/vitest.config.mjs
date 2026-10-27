// Unit tests of the app/ part of the packages (npm test): DOM in jsdom.
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    include: ['*/app/test/**/*.test.ts', 'sdk/test/**/*.test.ts']
  }
});
