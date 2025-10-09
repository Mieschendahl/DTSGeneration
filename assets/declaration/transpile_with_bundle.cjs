#!/usr/bin/env node
/* transpile-inplace-esbuild.cjs
 * Bundles a single file (and deps) into an IIFE and downlevels to ES5.
 * Overwrites the given file in place.
 *
 * Usage:
 *   node transpile-inplace-esbuild.cjs /path/to/file.js
 */

const path = require('path');
const fs = require('fs/promises');
const babel = require('@babel/core');
const esbuild = require('esbuild');

async function main() {
  const argv = process.argv.slice(2);
  if (!argv[0]) {
    console.error('Usage: node transpile-inplace-esbuild.cjs <file.js>');
    process.exit(1);
  }

  const entryFile = path.resolve(argv[0]);

  let stat;
  try {
    stat = await fs.stat(entryFile);
  } catch {
    console.error(`Path does not exist: ${entryFile}`);
    process.exit(1);
  }
  if (!stat.isFile() || !/\.(mjs|cjs|js)$/i.test(entryFile)) {
    console.error(`Not a JS-like file: ${entryFile}`);
    process.exit(1);
  }

  // console.log(`Transpiling in place:\n  ${entryFile}\n`);

  // 1) Bundle with esbuild to memory (IIFE, ES2015)
  const bundle = await esbuild.build({
    entryPoints: [entryFile],
    bundle: true,
    format: 'iife',      // still outputs a single self-executing file (no require/import)
    platform: 'node',    // <-- Node-like resolution for packages
    target: ['es2015'],
    write: false,
    sourcemap: false,
    logLevel: 'info',
    // (optional) if you ever need to mark Node built-ins external:
    // external: ['fs','path','crypto']
  });


  const bundledCode = bundle.outputFiles[0].text;

  // 2) Downlevel with Babel to ES5
  const babelResult = await babel.transformAsync(bundledCode, {
    babelrc: false,
    configFile: false,
    sourceMaps: false,
    presets: [
      [require.resolve('@babel/preset-env'), {
        targets: { ie: '11' },
        modules: false,
        bugfixes: true,
        loose: true,
      }]
    ],
  });

  if (!babelResult || !babelResult.code) {
    console.error('Babel produced no output.');
    process.exit(1);
  }

  // 3) Overwrite original file
  await fs.writeFile(entryFile, babelResult.code, 'utf8');
  // console.log(`✔ Overwritten with ES5: ${entryFile}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
