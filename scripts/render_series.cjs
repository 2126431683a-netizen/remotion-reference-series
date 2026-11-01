#!/usr/bin/env node
'use strict';

// Run from any working directory. Dependencies come from the configured project.
// projectRoot is relative to the JSON file; entryPoint/outputDir are relative to
// projectRoot. outputDir is the caller-chosen version directory, never "latest".
const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');
const {randomUUID} = require('node:crypto');

const usage = 'node render_series.cjs --config <file.json> --mode stills|preview|render [--part <composition-id>] [--overwrite]';
const fail = (message) => {throw new Error(message);};
const readJson = (file) => {
  try {return JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''));}
  catch (error) {fail(`Cannot read JSON ${file}: ${error.message}`);}
};
const samePath = (a, b) => process.platform === 'win32' ? a.toLowerCase() === b.toLowerCase() : a === b;
const within = (root, candidate) => {
  const relative = path.relative(root, candidate);
  return relative !== '' && relative !== '..' && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative);
};
const positive = (value, label) => {
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) fail(`${label} must be a positive number.`);
  return value;
};

function parseArgs(argv) {
  const args = {overwrite: false};
  for (let i = 0; i < argv.length; i++) {
    const match = /^(--[^=]+)(?:=(.*))?$/.exec(argv[i]);
    if (!match) fail(`Unexpected argument ${argv[i]}.\n${usage}`);
    const [, key, inline] = match;
    if (key === '--help') return {help: true};
    if (key === '--overwrite') {
      if (inline !== undefined || args.overwrite) fail('--overwrite is a flag and must appear once.');
      args.overwrite = true;
      continue;
    }
    if (!['--config', '--mode', '--part'].includes(key)) fail(`Unknown option ${key}.\n${usage}`);
    const name = key.slice(2);
    if (args[name] !== undefined) fail(`Duplicate option ${key}.`);
    const value = inline === undefined ? argv[++i] : inline;
    if (!value || value.startsWith('--')) fail(`Missing value for ${key}.`);
    args[name] = value;
  }
  if (!args.config || !['stills', 'preview', 'render'].includes(args.mode)) fail(usage);
  return args;
}

function loadConfig(file) {
  const configPath = path.resolve(file);
  const raw = readJson(configPath);
  for (const key of ['projectRoot', 'entryPoint', 'outputDir']) {
    if (typeof raw[key] !== 'string' || !raw[key].trim()) fail(`config.${key} must be a nonempty path.`);
  }
  const projectRoot = fs.realpathSync(path.resolve(path.dirname(configPath), raw.projectRoot));
  const entryPoint = fs.realpathSync(path.resolve(projectRoot, raw.entryPoint));
  if (!fs.statSync(entryPoint).isFile()) fail('entryPoint must be a file.');
  const outputDir = path.resolve(projectRoot, raw.outputDir);
  const concurrency = raw.concurrency ?? 2;
  if (!Number.isInteger(concurrency) || concurrency < 1) fail('concurrency must be a positive integer.');
  const crf = raw.crf ?? 18;
  if (!Number.isInteger(crf) || crf < 0 || crf > 51) fail('crf must be an integer from 0 to 51.');
  const scale = positive(raw.scale ?? 1, 'scale');
  const enableCaching = raw.enableCaching ?? false;
  if (typeof enableCaching !== 'boolean' || raw.enableCaching === null) fail('enableCaching must be a boolean.');
  let browserExecutable;
  if (raw.browserExecutable !== undefined) {
    if (typeof raw.browserExecutable !== 'string' || !raw.browserExecutable.trim()) fail('browserExecutable must be a nonempty file path.');
    const candidate = path.resolve(projectRoot, raw.browserExecutable);
    if (!fs.existsSync(candidate) || !fs.statSync(candidate).isFile()) fail(`browserExecutable must exist and be a file: ${candidate}`);
    browserExecutable = fs.realpathSync(candidate);
  }
  if (raw.tempRoot !== undefined && (typeof raw.tempRoot !== 'string' || !raw.tempRoot.trim())) fail('tempRoot must be a nonempty directory path.');
  const tempRoot = raw.tempRoot === undefined ? path.join(outputDir, '.render-work') : path.resolve(projectRoot, raw.tempRoot);
  if (!Array.isArray(raw.episodes) || raw.episodes.length === 0) fail('episodes must be a nonempty array.');
  const ids = new Set(), names = new Set();
  const episodes = raw.episodes.map((episode, index) => {
    const label = `episodes[${index}]`;
    if (!episode || typeof episode.id !== 'string' || !episode.id.trim()) fail(`${label}.id must name a composition.`);
    if (ids.has(episode.id)) fail(`Duplicate composition id: ${episode.id}`);
    ids.add(episode.id);
    const name = episode.filename;
    if (typeof name !== 'string' || !/\.mp4$/i.test(name) || /[\\/:*?"<>|\x00-\x1f]/.test(name) || name !== path.basename(name)) {
      fail(`${label}.filename must be a plain .mp4 filename without directory separators.`);
    }
    if (names.has(name.toLowerCase())) fail(`Duplicate output filename: ${name}`);
    names.add(name.toLowerCase());
    if (episode.checkSeconds !== undefined && (!Array.isArray(episode.checkSeconds) || episode.checkSeconds.length === 0 || episode.checkSeconds.some(s => typeof s !== 'number' || !Number.isFinite(s) || s < 0))) {
      fail(`${label}.checkSeconds must be a nonempty array of nonnegative seconds.`);
    }
    if (episode.previewSeconds !== undefined) positive(episode.previewSeconds, `${label}.previewSeconds`);
    if (episode.audioExpected !== undefined && typeof episode.audioExpected !== 'boolean') fail(`${label}.audioExpected must be a boolean.`);
    return {...episode, previewSeconds: episode.previewSeconds ?? 10, audioExpected: episode.audioExpected ?? true};
  });
  return {projectRoot, entryPoint, outputDir, concurrency, crf, scale, enableCaching, browserExecutable, tempRoot, episodes};
}

function loadReport(file, config, mode) {
  const empty = {version: 1, mode, projectRoot: config.projectRoot, entryPoint: config.entryPoint, episodes: []};
  if (!fs.existsSync(file)) return empty;
  const report = readJson(file);
  if (report.version !== 1 || report.mode !== mode || typeof report.projectRoot !== 'string' || typeof report.entryPoint !== 'string' || !samePath(report.projectRoot, config.projectRoot) || !samePath(report.entryPoint, config.entryPoint)) {
    fail(`Existing report has a different mode or project/entry point. Choose a new version in config.outputDir: ${file}`);
  }
  if (!Array.isArray(report.episodes)) fail(`Invalid episodes in report ${file}.`);
  const seen = new Set();
  for (const episode of report.episodes) {
    if (typeof episode.id !== 'string' || seen.has(episode.id)) fail(`Invalid/duplicate episode in ${file}.`);
    seen.add(episode.id);
    const artifacts = mode === 'stills' ? episode.stills : [{path: episode.path}];
    if (!Array.isArray(artifacts) || artifacts.length === 0) fail(`No artifacts for ${episode.id} in ${file}.`);
    for (const artifact of artifacts) {
      if (typeof artifact.path !== 'string' || !path.isAbsolute(artifact.path) || !within(config.outputDir, artifact.path) || !fs.existsSync(artifact.path) || !fs.statSync(artifact.path).isFile() || fs.statSync(artifact.path).size === 0) {
        fail(`Report artifact missing, empty or outside outputDir: ${artifact.path}. Choose a new version directory.`);
      }
    }
  }
  return report;
}

function writeReport(file, report) {
  const temporary = `${file}.${randomUUID()}.tmp`;
  try {
    fs.writeFileSync(temporary, `${JSON.stringify(report, null, 2)}\n`, {flag: 'wx'});
    fs.renameSync(temporary, file);
  } finally {
    if (fs.existsSync(temporary)) fs.unlinkSync(temporary);
  }
}

function saveEpisode(file, report, episode) {
  const index = report.episodes.findIndex(item => item.id === episode.id);
  const next = {...report, episodes: [...report.episodes]};
  if (index < 0) next.episodes.push(episode);
  else next.episodes[index] = episode;
  writeReport(file, next);
  report.episodes = next.episodes;
}

async function atomicRender(target, overwrite, render) {
  if (!overwrite && fs.existsSync(target)) fail(`Output exists: ${target}. Use a new version directory or explicit --overwrite.`);
  const temporary = path.join(path.dirname(target), `.partial-${randomUUID()}-${path.basename(target)}`);
  try {
    await render(temporary);
    if (!fs.existsSync(temporary) || fs.statSync(temporary).size === 0) fail(`Renderer did not create a nonempty artifact: ${target}`);
    if (overwrite) fs.renameSync(temporary, target);
    else {
      // COPYFILE_EXCL also prevents an unexpected writer from being overwritten.
      fs.copyFileSync(temporary, target, fs.constants.COPYFILE_EXCL);
      fs.unlinkSync(temporary);
    }
  } finally {
    if (fs.existsSync(temporary)) fs.unlinkSync(temporary);
  }
}

function makePlan(spec, composition, config, mode) {
  const {fps, durationInFrames, width, height} = composition;
  if (!Number.isFinite(fps) || fps <= 0 || !Number.isInteger(durationInFrames) || durationInFrames < 1 || !Number.isInteger(width) || !Number.isInteger(height)) fail(`Invalid composition metadata: ${spec.id}`);
  const duration = durationInFrames / fps;
  const frames = mode === 'preview' ? Math.min(durationInFrames, Math.max(1, Math.floor(spec.previewSeconds * fps))) : durationInFrames;
  const renderedDuration = frames / fps;
  const seconds = spec.checkSeconds ?? [Math.min(1, duration / 4), duration / 2, Math.max(0, duration - .5)];
  if (seconds.some(second => second >= duration)) fail(`${spec.id}: checkSeconds must be less than composition duration ${duration}s.`);
  const requestedFrames = [...new Set(seconds.filter(second => mode !== 'preview' || second < renderedDuration).map(second => Math.min(frames - 1, Math.round(second * fps))))];
  const checkFrames = requestedFrames.length ? requestedFrames : [Math.min(frames - 1, Math.floor(frames / 2))];
  const scaledWidth = Math.round(width * config.scale), scaledHeight = Math.round(height * config.scale);
  if (scaledWidth < 1 || scaledHeight < 1 || (mode !== 'stills' && (scaledWidth % 2 || scaledHeight % 2))) fail(`${spec.id}: scale must produce positive, even video dimensions; got ${scaledWidth}x${scaledHeight}.`);
  const output = path.join(config.outputDir, spec.filename);
  const stills = checkFrames.map(frame => ({frame, second: frame / fps, path: path.join(config.outputDir, `${path.parse(spec.filename).name}-frame-${frame}.png`)}));
  return {spec, composition, output, stills, metadata: {id: spec.id, path: output, width: scaledWidth, height: scaledHeight, fps, frames, durationSeconds: renderedDuration, audioExpected: spec.audioExpected, checkSeconds: checkFrames.map(frame => frame / fps)}};
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {console.log(usage); return;}
  const config = loadConfig(args.config);
  // Remotion locates browser caches relative to cwd, independently of require().
  // Keep both cache discovery and project configuration inside the project.
  process.chdir(config.projectRoot);
  const chosen = config.episodes.filter(episode => !args.part || episode.id === args.part);
  if (!chosen.length) fail(`Unknown --part ${args.part}. Expected a configured composition id.`);
  fs.mkdirSync(config.outputDir, {recursive: true});
  // A real output path keeps report-source checks stable when parents are symlinks.
  config.outputDir = fs.realpathSync(config.outputDir);
  fs.mkdirSync(config.tempRoot, {recursive: true});
  const tempRoot = fs.realpathSync(config.tempRoot);
  // This changes only this Node process and its children, not machine/user env.
  // Set before loading Remotion so browser/media helpers discover this location.
  for (const variable of ['TEMP', 'TMP', 'TMPDIR']) process.env[variable] = tempRoot;
  const reportFile = path.join(config.outputDir, args.mode === 'stills' ? 'still-report.json' : 'render-report.json');
  const lockFile = path.join(config.outputDir, '.render-series.lock');
  let lock, browser, buildDir;
  try {
    try {lock = fs.openSync(lockFile, 'wx');}
    catch (error) {if (error.code === 'EEXIST') fail(`Output directory is locked by another or interrupted run: ${lockFile}.`); throw error;}
    fs.writeFileSync(lock, `${JSON.stringify({pid: process.pid, mode: args.mode})}\n`);
    const report = loadReport(reportFile, config, args.mode);
    if (args.mode !== 'stills' && !args.overwrite) {
      const existing = chosen.map(episode => path.join(config.outputDir, episode.filename)).filter(file => fs.existsSync(file));
      if (existing.length) fail(`Some selected outputs already exist (${existing.length}): ${existing[0]}. No rendering started; use --overwrite or a new outputDir.`);
    }
    const projectRequire = createRequire(path.join(config.projectRoot, 'package.json'));
    let renderer, bundler;
    try {renderer = projectRequire('@remotion/renderer'); bundler = projectRequire('@remotion/bundler');}
    catch {fail(`Install @remotion/renderer and @remotion/bundler in the configured project: ${config.projectRoot}`);}
    buildDir = fs.mkdtempSync(path.join(tempRoot, 'remotion-series-'));
    console.log(`Bundle: ${config.entryPoint}`);
    const serveUrl = await bundler.bundle({entryPoint: config.entryPoint, rootDir: config.projectRoot, outDir: buildDir, enableCaching: config.enableCaching, onProgress: () => {}});
    browser = await renderer.openBrowser('chrome', {logLevel: 'error', ...(config.browserExecutable ? {browserExecutable: config.browserExecutable} : {})});
    const compositions = await renderer.getCompositions(serveUrl, {puppeteerInstance: browser, logLevel: 'error'});
    const plans = chosen.map(spec => {
      const composition = compositions.find(item => item.id === spec.id);
      if (!composition) fail(`Composition ${spec.id} not found. Available: ${compositions.map(item => item.id).join(', ')}`);
      return makePlan(spec, composition, config, args.mode);
    });
    const targets = plans.flatMap(plan => args.mode === 'stills' ? plan.stills.map(still => still.path) : [plan.output]);
    if (!args.overwrite && targets.some(file => fs.existsSync(file))) fail(`Some selected outputs already exist: ${targets.find(file => fs.existsSync(file))}. No rendering started; use --overwrite or a new outputDir.`);
    const selectedIds = new Set(chosen.map(episode => episode.id));
    for (const old of report.episodes.filter(episode => !selectedIds.has(episode.id))) {
      const oldPaths = args.mode === 'stills' ? old.stills.map(still => still.path) : [old.path];
      if (targets.some(target => oldPaths.some(oldPath => samePath(target, oldPath)))) fail(`A target belongs to another reported episode (${old.id}); choose a new filename.`);
    }
    // Episodes and stills are deliberately sequential. concurrency only controls
    // the frame workers inside a single video, keeping peak memory predictable.
    for (const plan of plans) {
      const {spec, composition, metadata} = plan;
      console.log(`${args.mode}: ${spec.id} (${metadata.frames} frames, ${metadata.width}x${metadata.height}, ${metadata.fps} fps)`);
      if (args.mode === 'stills') {
        const old = report.episodes.find(episode => episode.id === spec.id);
        const metadataChanged = old && ['width', 'height', 'fps', 'frames'].some(key => old[key] !== metadata[key]);
        if (metadataChanged && !args.overwrite) fail(`Still metadata changed for ${spec.id}; use --overwrite or a new version directory.`);
        // Do not attribute older, differently sized stills to the new metadata.
        const completed = [...(!metadataChanged ? old?.stills ?? [] : [])];
        for (const still of plan.stills) {
          await atomicRender(still.path, args.overwrite, temporary => renderer.renderStill({serveUrl, composition, puppeteerInstance: browser, frame: still.frame, output: temporary, imageFormat: 'png', scale: config.scale, overwrite: args.overwrite, logLevel: 'error'}));
          const index = completed.findIndex(item => samePath(item.path, still.path));
          if (index < 0) completed.push(still); else completed[index] = still;
          completed.sort((a, b) => a.frame - b.frame);
          const {path: unusedPath, audioExpected: unusedAudio, ...stillMetadata} = metadata;
          void unusedPath; void unusedAudio;
          saveEpisode(reportFile, report, {...stillMetadata, checkSeconds: completed.map(item => item.second), stills: completed});
          console.log(`OK ${still.path}`);
        }
      } else {
        let lastProgress = Date.now();
        await atomicRender(plan.output, args.overwrite, temporary => renderer.renderMedia({
          serveUrl, composition, puppeteerInstance: browser, outputLocation: temporary,
          codec: 'h264', pixelFormat: 'yuv420p', crf: config.crf, scale: config.scale,
          audioCodec: 'aac', audioBitrate: '192k', concurrency: config.concurrency,
          overwrite: args.overwrite, logLevel: 'error',
          ...(args.mode === 'preview' ? {frameRange: [0, metadata.frames - 1]} : {}),
          onProgress: progress => {if (Date.now() - lastProgress > 15000) {lastProgress = Date.now(); console.log(`${spec.id}: ${Math.round(progress.progress * 100)}%`);}},
        }));
        saveEpisode(reportFile, report, metadata);
        console.log(`OK ${plan.output}`);
      }
    }
    console.log(`Report: ${reportFile}`);
  } finally {
    if (browser) await browser.close({silent: true}).catch(() => {});
    try {
      if (buildDir && fs.existsSync(buildDir)) {
        const resolvedBuild = fs.realpathSync(buildDir);
        if (!within(tempRoot, resolvedBuild) || !path.basename(resolvedBuild).startsWith('remotion-series-')) fail(`Refusing to clean an unexpected build path: ${resolvedBuild}`);
        fs.rmSync(resolvedBuild, {recursive: true, force: true});
      }
    } finally {
      if (lock !== undefined) {fs.closeSync(lock); fs.unlinkSync(lockFile);}
    }
  }
}

main().catch(error => {
  console.error(`render_series: ${String(error.message ?? error).replace(/\u001b\[[0-9;]*m/g, '').slice(0, 1800)}`);
  process.exitCode = 1;
});
