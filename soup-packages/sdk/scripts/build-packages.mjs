// npm run build:packages [-- <folder> ...]
//
// Builds the SDK (sdk/dist, with the .d.ts the packages type-check
// against), then, for every package with an app/ part (or only the folders
// given), type-checks app/ and bundles app/src/index.ts with esbuild into a
// single ES module, app/dist/index.js, dependencies included, with its
// source map. A failing package does not stop the others; the exit code is
// non-zero if any failed.
import { join } from 'node:path';

import { build } from 'esbuild';

import { packagesWithApp, ROOT, tsc } from './packages.mjs';

async function buildPackage(folder) {
  const app = join(ROOT, folder, 'app');
  if (!tsc(['-p', join(app, 'tsconfig.json'), '--noEmit'])) {
    throw new Error('type check failed');
  }
  await build({
    entryPoints: [join(app, 'src', 'index.ts')],
    outfile: join(app, 'dist', 'index.js'),
    bundle: true,
    format: 'esm',
    platform: 'browser',
    target: 'es2022',
    sourcemap: true,
    minify: true,
    legalComments: 'none',
    logLevel: 'warning'
  });
}

async function main() {
  const requested = process.argv.slice(2);
  const available = packagesWithApp();
  const unknown = requested.filter((folder) => !available.includes(folder));
  if (unknown.length) {
    console.error(`No app/src/index.ts in: ${unknown.join(', ')}`);
    process.exit(2);
  }

  console.warn('[build] @soup/sdk');
  if (!tsc(['-p', 'sdk'])) {
    console.error('[build] @soup/sdk failed: no package can be built');
    process.exit(1);
  }

  const failed = [];
  for (const folder of requested.length ? requested : available) {
    try {
      await buildPackage(folder);
      console.warn(`[build] ${folder}: app/dist/index.js`);
    } catch (error) {
      failed.push(folder);
      console.error(`[build] ${folder} failed: ${error instanceof Error ? error.message : error}`);
    }
  }
  if (failed.length) {
    console.error(`[build] failed packages: ${failed.join(', ')}`);
    process.exit(1);
  }
}

await main();
