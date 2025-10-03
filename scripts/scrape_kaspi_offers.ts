import path from 'node:path';
import { performance } from 'node:perf_hooks';
import { setTimeout as sleep } from 'node:timers/promises';

import fs from 'fs-extra';
import { chromium, type Page } from 'playwright';
import yargs from 'yargs';
import { hideBin } from 'yargs/helpers';
import pLimit from 'p-limit';
import XLSX from 'xlsx';

import scrapeModule from '../apps/kaspi_offers_dashboard/server/scrape';
import type { FlatSellerRow } from '../apps/kaspi_offers_dashboard/server/scrape';

const navThrottle = createTokenBucket({ ratePerSec: 8, burst: 8 });

async function withNavThrottle<T>(fn: () => Promise<T>): Promise<T> {
  await navThrottle.take();
  return fn();
}

const MAX_ATTEMPTS = 4;

const { scrapeSellersFlat } = scrapeModule as {
  scrapeSellersFlat: (
    page: Page,
    productUrl: string,
    cityId: number
  ) => Promise<{
    rows: FlatSellerRow[];
    total: number;
    product_code: string;
    pages?: Array<{ page: number; got: number }>;
    dupFiltered?: number;
    reviewsQnt?: number;
  }>;
};

type CliArgs = {
  input: string;
  inCol?: string;
  urlsFile?: string;
  city: number;
  concurrency: number;
  headless: boolean;
  out: string;
  start: number;
  limit?: number;
  stateFile: string;
  debug: boolean;
};

type ProductTask = {
  originalUrl: string;
  normalizedUrl: string;
  fallbackCode: string | null;
  index: number;
  attempt: number;
};

type TaskResult = {
  index: number;
  url: string;
  productCode: string;
  total: number;
  zeroSellers: boolean;
  durationMs: number;
  attempt: number;
  pages: Array<{ page: number; got: number }>;
  dupFiltered: number;
  reviewsQnt: number;
};

type TaskError = Error & {
  index?: number;
  url?: string;
  isRateLimit?: boolean;
};

type FailureOutcome = {
  outcome: 'error';
  error: TaskError;
  task: ProductTask;
};

const RUN_TIMESTAMP = formatTimestamp(new Date());

async function main() {
  const argv = await parseCli();
  const inputUrls = argv.urlsFile
    ? await loadUrlsFromPlainFile(argv.urlsFile)
    : await loadProductUrls(argv.input, argv.inCol);
  if (!inputUrls.length) {
    console.error('No product URLs detected in input file.');
    process.exit(1);
  }

  const sliced = sliceProducts(inputUrls, argv.start, argv.limit);
  if (!sliced.length) {
    console.error('Requested start/limit range produced an empty set.');
    process.exit(1);
  }

  const cityIdStr = String(argv.city);
  const tasks: ProductTask[] = sliced.map((url, idx) => {
    const normalizedUrl = normalizeForMatching(url, cityIdStr);
    return {
      originalUrl: url,
      normalizedUrl,
      fallbackCode: extractProductCode(url),
      index: argv.start + idx,
      attempt: 1,
    };
  });

  const totalTasks = tasks.length;

  const outPath = path.resolve(argv.out);
  const outputDir = path.dirname(outPath);
  const logsDir = path.resolve('data_raw/perfumes/logs');
  const debugDir = path.resolve('data_raw/perfumes/debug');

  await fs.ensureDir(outputDir);
  await fs.ensureDir(logsDir);
  await fs.ensureDir(debugDir);

  const outExists = await fs.pathExists(outPath);
  const csvStream = fs.createWriteStream(outPath, { flags: outExists ? 'a' : 'w' });
  if (!outExists) {
    await writeLine(
      csvStream,
      'product_url,product_code,total_sellers_qnt,seller_name,price_kzt,ratings_qnt\n'
    );
  }

  const logStream = fs.createWriteStream(path.join(logsDir, `offers_${RUN_TIMESTAMP}.ndjson`), { flags: 'a' });
  const writeQueue = pLimit(1);

  const statePath = path.resolve(argv.stateFile);
  await fs.ensureDir(path.dirname(statePath));
  const resumeState = await loadResumeState(statePath);

  const urlToIndex = new Map<string, number>();
  const codeToIndex = new Map<string, number>();
  for (const task of tasks) {
    urlToIndex.set(task.normalizedUrl, task.index);
    if (task.fallbackCode) {
      // prefer first occurrence
      if (!codeToIndex.has(task.fallbackCode)) {
        codeToIndex.set(task.fallbackCode, task.index);
      }
    }
  }

  const csvCoveredIndices = await hydrateStateFromArtifacts({
    state: resumeState,
    outPath,
    logsDir,
    urlToIndex,
    codeToIndex,
    cityId: cityIdStr,
  });

  const completedIndices = new Set<number>(Object.keys(resumeState.completed).map((k) => Number(k)));
  let completionCount = completedIndices.size;

  const pending: ProductTask[] = tasks
    .filter((task) => {
      if (!completedIndices.has(task.index)) return true;
      const completedEntry = resumeState.completed[task.index];
      const wasZero = completedEntry?.total === 0;
      const hasCsvRow = csvCoveredIndices.has(task.index);
      return !(wasZero || hasCsvRow);
    })
    .map((task) => ({
      ...task,
      attempt: Math.min((resumeState.failures[task.index]?.attempts ?? 0) + 1, MAX_ATTEMPTS),
    }))
    .sort((a, b) => a.index - b.index);

  if (process.env.DEBUG_RESUME === '1') {
    console.log(
      'Pending queue snapshot',
      pending.map((task) => ({
        index: task.index,
        attempt: task.attempt,
        completed: completedIndices.has(task.index),
        total: resumeState.completed[task.index]?.total,
        hasCsv: csvCoveredIndices.has(task.index),
      }))
    );
  }

  const pendingPreviouslyCompleted = new Set<number>();
  let hadCompletedRemovals = false;
  for (const task of pending) {
    if (completedIndices.has(task.index)) pendingPreviouslyCompleted.add(task.index);
  }
  if (pendingPreviouslyCompleted.size > 0) {
    for (const idx of pendingPreviouslyCompleted) {
      delete resumeState.completed[idx];
      completedIndices.delete(idx);
    }
    hadCompletedRemovals = true;
  }
  completionCount -= pendingPreviouslyCompleted.size;
  if (completionCount < 0) completionCount = 0;

  if (!outExists && completionCount > 0) {
    console.log(`State indicates ${completionCount} items already completed; CSV will append new rows only.`);
  }

  const debugMode = argv.debug === true;
  const headless = debugMode ? false : argv.headless !== false;
  const slowMo = debugMode ? 250 : 0;
  const browser = await chromium.launch({ headless, slowMo });
  const context = await browser.newContext({
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    locale: 'ru-KZ',
    timezoneId: 'Asia/Almaty',
  });

  const hardCap = Math.min(Math.max(argv.concurrency, 1), 150);
  const stageTargets: number[] = [];
  stageTargets[0] = Math.max(1, Math.min(50, hardCap));
  stageTargets[1] = Math.max(stageTargets[0], Math.max(1, Math.min(100, hardCap)));
  stageTargets[2] = Math.max(stageTargets[1], Math.max(1, hardCap));
  let rampStage = 0;
  let backoffConcurrency: number | null = null;
  let backoffRemaining = 0;
  let backoffDelayUntil = 0;

  let processedAttempts = 0;
  let failureCount = Object.keys(resumeState.failures).length;
  let zeroSellerStreak = 0;
  let lastLoggedConcurrency = 0;
  const outcomeHistory: Array<{ ok: boolean; rateLimited: boolean }> = [];
  let stage1ActivatedAt: number | null = null;

  const concurrencyLimiter = pLimit(hardCap);
  const inFlight = new Set<Promise<{ outcome: 'ok'; result: TaskResult } | FailureOutcome>>();
  let stateDirty = false;
  let statePersist = Promise.resolve();
  let shouldStop = false;

  const persistState = () => {
    if (!stateDirty) return statePersist;
    stateDirty = false;
    statePersist = statePersist
      .catch(() => {})
      .then(() => saveResumeState(statePath, resumeState))
      .catch((err) => {
        console.error('Failed to persist state:', err);
        throw err;
      });
    return statePersist;
  };

  const markStateDirty = () => {
    stateDirty = true;
  };

  const pendingQueue: ProductTask[] = [...pending];

  const totalPending = pendingQueue.length;

  const signalHandler = (signal: NodeJS.Signals) => {
    if (shouldStop) return;
    shouldStop = true;
    console.warn(`Received ${signal}. Finishing in-flight tasks, no new pages will be scheduled.`);
  };
  process.on('SIGINT', signalHandler);
  process.on('SIGTERM', signalHandler);

  lastLoggedConcurrency = getCurrentConcurrency();
  console.log(
    `Loaded ${totalTasks} products, ${completionCount} already complete. Pending ${totalPending}. Starting with concurrency ${lastLoggedConcurrency} (max ${hardCap}).`
  );
  if (pendingQueue.length === 0) {
    console.log('Nothing pending – state indicates all selected products are already processed.');
  }

  if (hadCompletedRemovals) {
    markStateDirty();
    persistState();
  }

  try {
    await scheduleIfPossible();
    while ((pendingQueue.length > 0 && !shouldStop) || inFlight.size > 0) {
      if (inFlight.size === 0) {
        await scheduleIfPossible();
        if (inFlight.size === 0) break;
      }

      const finished = await Promise.race(inFlight);
      if (finished.outcome === 'ok') {
        await handleSuccess(finished.result);
      } else {
        const failure = finished as FailureOutcome;
        await handleFailure(failure.error, failure.task);
      }
      updateConcurrencyState();
      await scheduleIfPossible();
    }
  } finally {
    await persistState();
    await context.close().catch(() => {});
    await browser.close().catch(() => {});
    await closeStream(csvStream);
    await closeStream(logStream);
  }

  console.log(
    `Done. Completed ${completionCount}/${totalTasks} products. Failures logged: ${failureCount}. Output: ${outPath}`
  );

  async function scheduleIfPossible() {
    while (!shouldStop && pendingQueue.length > 0 && inFlight.size < getCurrentConcurrency()) {
      if (backoffDelayUntil > Date.now()) {
        const waitMs = backoffDelayUntil - Date.now();
        await sleep(waitMs);
        backoffDelayUntil = 0;
        if (shouldStop) break;
      }
      const task = pendingQueue.shift();
      if (!task) break;
      const promise = concurrencyLimiter(() => runTask(task));
      const wrapped = promise
        .then((result): { outcome: 'ok'; result: TaskResult } => ({ outcome: 'ok', result }))
        .catch((error: TaskError): FailureOutcome => ({ outcome: 'error', error, task }));
      inFlight.add(wrapped);
      wrapped.finally(() => {
        inFlight.delete(wrapped);
      });
    }
  }

  function getCurrentConcurrency(): number {
    const stageConcurrency = stageTargets[rampStage];
    const active = backoffConcurrency ?? stageConcurrency;
    return Math.max(1, Math.min(hardCap, active));
  }

  async function handleSuccess(result: TaskResult) {
    processedAttempts += 1;
    zeroSellerStreak = result.zeroSellers ? zeroSellerStreak + 1 : 0;
    recordOutcome(true, false);

    const firstCompletion = !completedIndices.has(result.index);
    if (firstCompletion) {
      completedIndices.add(result.index);
      completionCount += 1;
    }

    markCompleted(resumeState, result.index, {
      url: result.url,
      productCode: result.productCode,
      total: result.total,
    });
    markStateDirty();
    persistState();

    await writeLog({
      index: result.index,
      url: result.url,
      product_code: result.productCode || null,
      total: result.total,
      ms: result.durationMs,
      attempt: result.attempt,
      concurrency: getCurrentConcurrency(),
      pagesMeta: result.pages,
      dupFiltered: result.dupFiltered,
      zeroSellers: result.zeroSellers || undefined,
      reviewsQnt: result.reviewsQnt ?? 0,
    });
    logProgress(result.index, result.productCode, result.total);
  }

  async function handleFailure(err: TaskError, task: ProductTask) {
    processedAttempts += 1;
    failureCount += 1;
    zeroSellerStreak = 0;
    const rateLimited = !!err.isRateLimit;
    recordOutcome(false, rateLimited);
    await writeLog({
      index: task.index,
      url: err.url,
      err: err.message,
      ms: undefined,
      concurrency: getCurrentConcurrency(),
      rateLimit: rateLimited || undefined,
      attempt: task.attempt,
    });
    console.error(`Error on index ${err.index ?? task.index ?? '?'}: ${err.message}`);

    recordFailure(resumeState, task.index, {
      url: task.originalUrl,
      attempts: task.attempt,
      error: err.message,
    });
    markStateDirty();
    persistState();

    if (rateLimited) {
      await triggerBackoff('HTTP 429/503 or navigation timeout detected');
    }

    if (!shouldStop && task.attempt < MAX_ATTEMPTS) {
      const retryTask: ProductTask = { ...task, attempt: task.attempt + 1 };
      pendingQueue.push(retryTask);
    }
    if (!shouldStop) {
      await sleep(200 + Math.floor(Math.random() * 400));
    }
  }

  function updateConcurrencyState() {
    if (backoffRemaining > 0) {
      backoffRemaining -= 1;
      if (backoffRemaining <= 0) {
        backoffConcurrency = null;
      }
    }
    evaluateRamp();
    maybeLogConcurrencyChange();
  }

  async function triggerBackoff(reason: string) {
    const base = getCurrentConcurrency();
    const halved = Math.floor(base * 0.5) || base;
    const lowered = Math.max(50, halved);
    const target = Math.min(hardCap, Math.max(1, lowered));
    backoffConcurrency = target;
    backoffRemaining = Math.max(backoffRemaining, 100);
    backoffDelayUntil = Date.now() + 60_000;
    console.warn(
      `[backoff] ${reason}. Reducing concurrency to ${target} for the next ${backoffRemaining} items and pausing scheduling for 60s.`
    );
    await writeLog({ event: 'backoff', reason, concurrency: target, stage: rampStage });
    maybeLogConcurrencyChange();
  }

  function maybeLogConcurrencyChange() {
    const current = getCurrentConcurrency();
    if (current !== lastLoggedConcurrency) {
      console.log(`Adjusted concurrency -> ${current}`);
      lastLoggedConcurrency = current;
    }
  }

  function recordOutcome(ok: boolean, rateLimited: boolean) {
    outcomeHistory.push({ ok, rateLimited });
    if (outcomeHistory.length > 300) outcomeHistory.shift();
  }

  function evaluateRamp() {
    if (backoffRemaining > 0) return;

    if (rampStage === 0 && completionCount >= 50 && meetsStability(50)) {
      if (stageTargets[1] !== stageTargets[0]) {
        rampStage = 1;
        stage1ActivatedAt = completionCount;
      }
    }

    if (rampStage === 1) {
      const tasksSinceUpgrade = stage1ActivatedAt !== null ? completionCount - stage1ActivatedAt : 0;
      if (tasksSinceUpgrade >= 100 && completionCount >= (stage1ActivatedAt ?? 0) + 100 && meetsStability(100)) {
        if (stageTargets[2] !== stageTargets[1]) {
          rampStage = 2;
        }
      }
    }
  }

  function meetsStability(windowSize: number): boolean {
    const window = outcomeHistory.slice(-windowSize);
    if (window.length < windowSize) return false;
    const errors = window.filter((o) => !o.ok).length;
    const rateLimited = window.some((o) => o.rateLimited);
    return errors / window.length < 0.05 && !rateLimited;
  }

  async function runTask(task: ProductTask): Promise<TaskResult> {
    const startHr = performance.now();
    const page = await context.newPage();
    page.setDefaultNavigationTimeout(60_000);
    page.setDefaultTimeout(45_000);
    const cityId = argv.city;
    const requestUrl = task.originalUrl;
    try {
      const helperPromise = withNavThrottle(() => scrapeSellersFlat(page, requestUrl, cityId));
      helperPromise.catch(() => {});
      const TIMEOUT = Symbol('timeout');
      const timeoutPromise = sleep(120_000).then(() => TIMEOUT);
      const raceResult = await Promise.race([helperPromise, timeoutPromise]);
      if (raceResult === TIMEOUT) {
        const timeoutErr = new Error('per-product timeout') as TaskError;
        timeoutErr.index = task.index;
        timeoutErr.url = ensureCityParam(requestUrl, String(cityId));
        timeoutErr.isRateLimit = true;
        throw timeoutErr;
      }

      const result = raceResult as Awaited<ReturnType<typeof scrapeSellersFlat>>;
      const total = result.total;
      const zeroSellers = total === 0;
      const canonicalUrl = result.rows[0]?.product_url || ensureCityParam(requestUrl, String(cityId));

      if (result.rows.length) {
        const lines = buildCsvLines(result.rows, total, result.reviewsQnt ?? 0);
        for (const line of lines) {
          await writeQueue(() => writeLine(csvStream, line));
        }
      } else if (zeroSellers) {
        const safeCode = sanitizeForFilename(result.product_code || task.fallbackCode || `product_${task.index + 1}`);
        const debugPath = path.join(debugDir, `${safeCode}.png`);
        await page.screenshot({ path: debugPath, fullPage: true }).catch(() => {});
      }

      return {
        index: task.index,
        url: canonicalUrl,
        productCode: result.product_code,
        total,
        zeroSellers,
        durationMs: Math.round(performance.now() - startHr),
        attempt: task.attempt,
        pages: result.pages,
        dupFiltered: result.dupFiltered,
        reviewsQnt: result.reviewsQnt ?? 0,
      };
    } catch (error) {
      const err = error as TaskError;
      err.index = task.index;
      err.url = ensureCityParam(requestUrl, String(cityId));
      err.isRateLimit = isRateLimitError(err);
      throw err;
    } finally {
      await page.close().catch(() => {});
    }
  }

  async function writeLog(payload: Record<string, unknown>) {
    const line = `${JSON.stringify({ ...payload, ts: new Date().toISOString() })}\n`;
    await writeQueue(() => writeLine(logStream, line));
  }

  function logProgress(index: number, productCode: string, total: number) {
    const prefix = `${completionCount}/${totalTasks}`;
    const label = productCode || `idx${index + 1}`;
    console.log(`[${prefix}] ${label} sellers=${total}`);
  }
}

async function writeLine(stream: fs.WriteStream, line: string) {
  if (!stream.write(line)) {
    await new Promise<void>((resolve, reject) => {
      stream.once('drain', resolve);
      stream.once('error', reject);
    });
  }
}

async function closeStream(stream: fs.WriteStream) {
  await new Promise<void>((resolve, reject) => {
    stream.end((err) => (err ? reject(err) : resolve()));
  });
}

function buildCsvLines(rows: FlatSellerRow[], totalForProduct: number, ratingsQnt: number): string[] {
  return rows.map((row) =>
    [
      csvSafe(row.product_url),
      csvSafe(row.product_code),
      csvSafe(String(totalForProduct)),
      csvSafe(row.seller_name),
      csvSafe(String(row.price_kzt)),
      csvSafe(String(ratingsQnt)),
    ].join(',') + '\n'
  );
}

function csvSafe(value: string): string {
  const text = (value ?? '').toString().replace(/\r|\n|\t/g, ' ').replace(/\s+/g, ' ').trim();
  if (text === '') return '';
  if (/[",]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function splitCsvLine(line: string): string[] {
  const cols: string[] = [];
  let current = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (ch === ',' && !inQuotes) {
      cols.push(current);
      current = '';
      continue;
    }
    current += ch;
  }
  cols.push(current);
  return cols;
}

function ensureCityParam(url: string, cityId: string): string {
  try {
    const parsed = new URL(url);
    parsed.searchParams.set('c', cityId);
    return parsed.toString();
  } catch {
    const normalized = url.startsWith('http') ? url : `https://kaspi.kz${url.startsWith('/') ? '' : '/'}${url}`;
    return ensureCityParam(normalized, cityId);
  }
}

function extractProductCode(url: string): string | null {
  const match = url.match(/-(\d+)(?:[/?#]|$)/);
  if (match) return match[1];
  const fallback = url.match(/\/p\/(\d+)(?:[/?#]|$)/);
  return fallback ? fallback[1] : null;
}

function sanitizeForFilename(value: string): string {
  return value.replace(/[^A-Za-z0-9_-]+/g, '_').slice(0, 80) || 'product';
}

function isRateLimitError(err: TaskError): boolean {
  const msg = err.message || '';
  return /(\b429\b|Too Many Requests|TooManyRequests|\b503\b|Service Unavailable|per-product timeout)/i.test(msg);
}

type CompletedEntry = {
  url: string;
  productCode?: string | null;
  total?: number;
  ts: string;
};

type FailureEntry = {
  url: string;
  attempts: number;
  lastError?: string;
  ts: string;
};

type ResumeState = {
  completed: Record<number, CompletedEntry>;
  failures: Record<number, FailureEntry>;
};

async function loadResumeState(file: string): Promise<ResumeState> {
  try {
    const tmpPath = `${file}.tmp`;
    if (await fs.pathExists(tmpPath)) {
      await fs.remove(tmpPath).catch(() => {});
    }
    if (!(await fs.pathExists(file))) {
      return { completed: {}, failures: {} };
    }
    const data = (await fs.readJson(file)) as Partial<ResumeState>;
    return {
      completed: data.completed ?? {},
      failures: data.failures ?? {},
    };
  } catch (err) {
    console.warn(`Could not read state file ${file}:`, err);
    return { completed: {}, failures: {} };
  }
}

async function saveResumeState(file: string, state: ResumeState): Promise<void> {
  const tmpPath = `${file}.tmp`;
  await fs.writeJson(tmpPath, state, { spaces: 2 });
  await fs.move(tmpPath, file, { overwrite: true });
}

function markCompleted(state: ResumeState, index: number, payload: { url: string; productCode?: string; total: number }): void {
  state.completed[index] = {
    url: payload.url,
    productCode: payload.productCode,
    total: payload.total,
    ts: new Date().toISOString(),
  };
  delete state.failures[index];
}

function recordFailure(
  state: ResumeState,
  index: number,
  payload: { url: string; attempts: number; error?: string }
): void {
  state.failures[index] = {
    url: payload.url,
    attempts: payload.attempts,
    lastError: payload.error,
    ts: new Date().toISOString(),
  };
  delete state.completed[index];
}

type HydrateArgs = {
  state: ResumeState;
  outPath: string;
  logsDir: string;
  urlToIndex: Map<string, number>;
  codeToIndex: Map<string, number>;
  cityId: string;
};

async function hydrateStateFromArtifacts(args: HydrateArgs): Promise<Set<number>> {
  const { state, outPath, logsDir, urlToIndex, codeToIndex, cityId } = args;
  const csvCovered = new Set<number>();

  if (await fs.pathExists(outPath)) {
    try {
      const fileContent = await fs.readFile(outPath, 'utf8');
      const lines = fileContent.split(/\r?\n/).filter(Boolean);
      if (lines.length > 0 && lines[0].startsWith('product_url')) {
        lines.shift();
      }
      for (const line of lines) {
        const parts = splitCsvLine(line);
        if (parts.length < 3) continue;
        const productUrl = (parts[0] ?? '').trim();
        const productCode = (parts[1] ?? '').trim();
        const totalStr = (parts[2] ?? '0').trim();
        const idx = codeToIndex.get(productCode);
        if (idx === undefined) continue;
        csvCovered.add(idx);
        if (state.completed[idx]) continue;
        const total = Number(totalStr);
        state.completed[idx] = {
          url: productUrl,
          productCode,
          total: Number.isFinite(total) ? total : undefined,
          ts: new Date().toISOString(),
        };
        delete state.failures[idx];
      }
    } catch (err) {
      console.warn(`Failed to hydrate state from CSV ${outPath}:`, err);
    }
  }

  try {
    const entries = await fs.readdir(logsDir);
    const ndjsonFiles = entries.filter((name) => name.startsWith('offers_') && name.endsWith('.ndjson'));
    ndjsonFiles.sort();
    for (const file of ndjsonFiles) {
      const fullPath = path.join(logsDir, file);
      let content: string;
      try {
        content = await fs.readFile(fullPath, 'utf8');
      } catch (err) {
        console.warn(`Failed to read log ${fullPath}:`, err);
        continue;
      }
      const lines = content.split(/\r?\n/).filter(Boolean);
      for (const line of lines) {
        try {
          const entry = JSON.parse(line);
          if (entry.event) continue;
          if (!Object.prototype.hasOwnProperty.call(entry, 'total')) continue;
          const urlRaw: string | undefined = entry.url;
          const codeRaw: string | undefined = entry.product_code || entry.productCode;
          let idx: number | undefined;
          if (urlRaw) {
            const normalized = normalizeForMatching(urlRaw, cityId);
            idx = urlToIndex.get(normalized);
          }
          if (idx === undefined && codeRaw) {
            idx = codeToIndex.get(codeRaw);
          }
          if (idx === undefined) continue;
          if (state.completed[idx]) continue;
          const total = typeof entry.total === 'number' ? entry.total : undefined;
          state.completed[idx] = {
            url: urlRaw || '',
            productCode: codeRaw,
            total,
            ts: new Date().toISOString(),
          };
          delete state.failures[idx];
        } catch {
          continue;
        }
      }
    }
  } catch (err) {
    console.warn(`Failed to scan logs directory ${logsDir}:`, err);
  }

  return csvCovered;
}

function normalizeForMatching(url: string, cityId: string): string {
  try {
    const ensured = ensureCityParam(url, cityId);
    const parsed = new URL(ensured);
    parsed.hash = '';
    parsed.searchParams.sort();
    let pathname = parsed.pathname;
    if (pathname.length > 1) {
      pathname = pathname.replace(/\/+$/, '');
      if (!pathname.startsWith('/')) pathname = `/${pathname}`;
    }
    parsed.pathname = pathname || '/';
    return parsed.toString();
  } catch {
    return ensureCityParam(url, cityId);
  }
}

type TokenBucket = {
  take: () => Promise<void>;
};

function createTokenBucket({ ratePerSec, burst }: { ratePerSec: number; burst: number }): TokenBucket {
  const tokensMax = Math.max(1, burst);
  let tokens = tokensMax;
  const queue: Array<() => void> = [];
  const intervalMs = Math.max(10, Math.floor(1000 / Math.max(1, ratePerSec)));

  const replenish = () => {
    if (tokens < tokensMax) tokens += 1;
    flush();
  };

  const flush = () => {
    while (tokens > 0 && queue.length > 0) {
      tokens -= 1;
      const resolve = queue.shift();
      resolve?.();
    }
  };

  const timer = setInterval(replenish, intervalMs);
  if (typeof timer.unref === 'function') timer.unref();

  return {
    async take() {
      if (tokens > 0) {
        tokens -= 1;
        return;
      }
      await new Promise<void>((resolve) => {
        queue.push(resolve);
      });
    },
  };
}

function sliceProducts(urls: string[], start: number, limit?: number): string[] {
  const safeStart = Math.max(0, start || 0);
  if (limit === undefined || limit === null || limit <= 0) {
    return urls.slice(safeStart);
  }
  return urls.slice(safeStart, safeStart + limit);
}

async function parseCli(): Promise<CliArgs> {
  const defaultOutput = path.join('data_raw', 'perfumes', `offers_${RUN_TIMESTAMP}.csv`);
  const parsed = await yargs(hideBin(process.argv))
    .option('input', {
      type: 'string',
      describe: 'Path to XLSX or CSV file containing product URLs',
      default: '/Users/adil/Documents/Ideas/perfume_analysis_gpt_7.9.25_v1/Perfumes_V11_MC_V2.1_30.9.25.xlsx',
    })
    .option('in-col', {
      type: 'string',
      describe: 'Column name containing product URLs (auto-detected if omitted)',
    })
    .option('city', {
      type: 'number',
      describe: 'Kaspi cityId parameter to use',
      default: 710000000,
    })
    .option('concurrency', {
      type: 'number',
      describe: 'Maximum concurrent pages to run (capped at 150)',
      default: 150,
    })
    .option('urls-file', {
      type: 'string',
      describe: 'Optional newline-delimited list of product URLs (skips XLSX parsing)',
    })
    .option('out', {
      type: 'string',
      describe: 'Output CSV path',
      default: defaultOutput,
    })
    .option('headless', {
      type: 'boolean',
      describe: 'Run Playwright in headless mode',
      default: true,
    })
    .option('start', {
      type: 'number',
      describe: 'Start index within the input list',
      default: 0,
    })
    .option('limit', {
      type: 'number',
      describe: 'Optional limit of items to process',
    })
    .option('debug', {
      type: 'boolean',
      describe: 'Run Playwright in headed mode with slowMo for debugging',
      default: false,
    })
    .option('state', {
      type: 'string',
      describe: 'Path to resume state JSON file',
      default: path.join('data_raw', 'perfumes', 'offers_state.json'),
    })
    .strict()
    .help()
    .parseAsync();

  const pickLast = <T>(value: T | T[] | undefined): T => {
    if (Array.isArray(value)) {
      return value.length ? value[value.length - 1] : (undefined as unknown as T);
    }
    return value as T;
  };

  return {
    input: pickLast<string>(parsed.input),
    inCol: pickLast<string | undefined>(parsed['in-col']),
    urlsFile: pickLast<string | undefined>(parsed['urls-file']),
    city: Number(pickLast<number | string>(parsed.city)),
    concurrency: Number(pickLast<number | string>(parsed.concurrency)),
    headless: pickLast<boolean>(parsed.headless),
    out: pickLast<string>(parsed.out),
    start: Number(pickLast<number | string>(parsed.start)),
    limit: parsed.limit === undefined ? undefined : Number(pickLast<number | string>(parsed.limit)),
    stateFile: pickLast<string>(parsed.state),
    debug: Boolean(pickLast<boolean>(parsed.debug)),
  };
}

async function loadProductUrls(filePath: string, requestedColumn?: string): Promise<string[]> {
  const workbook = XLSX.readFile(filePath, { cellFormula: false });
  const sheetName = workbook.SheetNames[0];
  if (!sheetName) return [];
  const sheet = workbook.Sheets[sheetName];
  const rows = XLSX.utils.sheet_to_json<Record<string, unknown>>(sheet, { defval: null, raw: false });
  if (!rows.length) return [];

  const columnName = resolveColumnName(rows, requestedColumn);
  return rows
    .map((row) => normalizeProductUrl(row[columnName]))
    .filter((value): value is string => typeof value === 'string' && value.length > 0);
}

async function loadUrlsFromPlainFile(filePath: string): Promise<string[]> {
  try {
    const content = await fs.readFile(filePath, 'utf8');
    return content
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line.length > 0 && !line.startsWith('#'));
  } catch (err) {
    console.error(`Failed to read URLs from ${filePath}:`, err);
    return [];
  }
}

function resolveColumnName(rows: Record<string, unknown>[], requested?: string): string {
  const candidates = Array.from(
    rows.slice(0, 20).reduce((set, row) => {
      Object.keys(row || {}).forEach((key) => set.add(key));
      return set;
    }, new Set<string>())
  );

  if (requested) {
    const lower = requested.toLowerCase();
    const match = candidates.find((col) => col.toLowerCase() === lower);
    if (!match) {
      throw new Error(`Column "${requested}" not found in input file. Available: ${candidates.join(', ')}`);
    }
    return match;
  }

  const preferred = ['product_url', 'url', 'kaspi_url'];
  for (const p of preferred) {
    const match = candidates.find((col) => col.toLowerCase() === p);
    if (match) return match;
  }

  for (const col of candidates) {
    const hasKaspiLink = rows.some((row) => {
      const value = row[col];
      return typeof value === 'string' && /kaspi\.kz\/shop\/p\//i.test(value);
    });
    if (hasKaspiLink) return col;
  }

  throw new Error('Could not auto-detect a column containing Kaspi product URLs. Use --in-col to specify it explicitly.');
}

function normalizeProductUrl(value: unknown): string | undefined {
  if (value === null || value === undefined) return undefined;
  const raw = String(value).trim();
  if (!raw) return undefined;
  if (/^https?:\/\//i.test(raw)) return raw;
  if (raw.startsWith('kaspi.kz')) return `https://${raw}`;
  if (raw.startsWith('/shop/p/')) return `https://kaspi.kz${raw}`;
  if (raw.startsWith('shop/p/')) return `https://kaspi.kz/${raw}`;
  return raw.includes('kaspi.kz') ? `https://${raw.replace(/^https?:\/\//i, '')}` : raw;
}

function formatTimestamp(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}_${pad(date.getHours())}${pad(date.getMinutes())}`;
}

main().catch((err) => {
  console.error(err instanceof Error ? err.stack || err.message : err);
  process.exit(1);
});
