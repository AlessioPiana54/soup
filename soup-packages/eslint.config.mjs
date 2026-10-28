// Lint of the SDK and of the app/ sources of every package (npm run lint).
import eslint from '@eslint/js';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['**/dist/**', '**/node_modules/**', 'sdk/scripts/**', 'eslint.config.mjs', 'vitest.config.mjs'] },
  {
    files: ['**/*.ts'],
    extends: [eslint.configs.recommended, ...tseslint.configs.recommended],
    rules: {
      '@typescript-eslint/consistent-type-definitions': 'error',
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      'no-console': ['error', { allow: ['warn', 'error'] }],
      // Reported, not blocking: the limits of the code-quality review (commit 13).
      complexity: ['warn', 10],
      'max-lines-per-function': ['warn', { max: 60, skipBlankLines: true, skipComments: true }]
    }
  },
  {
    // A describe() holds many cases: the length limit is for the code under test.
    files: ['*/app/test/**/*.ts', 'sdk/test/**/*.ts'],
    rules: { 'max-lines-per-function': 'off' }
  }
);
