const path = require('path');
const fs = require('fs/promises');
const babel = require('@babel/core');

async function main() {
  const argv = process.argv.slice(2);
  if (argv.length === 0) {
    console.error('Usage: node transpile.js inputFile.js');
    process.exit(1);
  }
  const inputFile = path.resolve(argv[0]);
  let code;
  try {
    code = await fs.readFile(inputFile, 'utf8');
  } catch {
    console.error(`Error: File not found - ${inputFile}`);
    process.exit(1);
  }
  const babelOpts = {
    sourceMaps: false,
    babelrc: false,
    configFile: false,
    presets: [
      [
        require.resolve('@babel/preset-env'),
        {
          targets: { ie: '11' }, // ES5 level
          modules: 'commonjs',
          bugfixes: true,
          loose: true,
        },
      ],
    ],
    filename: inputFile,
  };

  try {
    const result = await babel.transformAsync(code, babelOpts);
    if (!result || !result.code) {
      console.error('Error: Babel produced no output');
      process.exit(1);
    }
    await fs.writeFile(inputFile, result.code, 'utf8');
  } catch (err) {
    console.error(`Babel error: ${err.message}`);
    process.exit(1);
  }
}

main();