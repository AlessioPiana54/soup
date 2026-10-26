// Shared by build-packages.mjs and pack.mjs: where the packages are and how
// to run the TypeScript compiler of the workspace.
import { spawnSync } from 'node:child_process';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
export const SDK_DIR = join(ROOT, 'sdk');
export const MANIFEST_FILE = 'soup-package.json';

const SKIPPED = new Set(['node_modules', 'sdk', 'dist']);

/** Every folder of soup-packages with an app/src/index.ts, `_template` included. */
export function packagesWithApp() {
  return readdirSync(ROOT, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && !entry.name.startsWith('.') && !SKIPPED.has(entry.name))
    .map((entry) => entry.name)
    .filter((name) => existsSync(join(ROOT, name, 'app', 'src', 'index.ts')))
    .sort();
}

export function readManifest(folder) {
  const path = join(ROOT, folder, MANIFEST_FILE);
  if (!existsSync(path)) {
    throw new Error(`${folder}: missing ${MANIFEST_FILE}`);
  }
  return JSON.parse(readFileSync(path, 'utf8'));
}

/** Run tsc with `args`; returns true on success (the output goes to the console). */
export function tsc(args) {
  const require = createRequire(join(ROOT, 'package.json'));
  const bin = require.resolve('typescript/bin/tsc');
  const result = spawnSync(process.execPath, [bin, ...args], { cwd: ROOT, stdio: 'inherit' });
  return result.status === 0;
}
