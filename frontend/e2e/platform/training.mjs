// Real compiled frontend → Python HTTP → restricted PostgreSQL. No store setters or fake API replies.
import assert from 'node:assert/strict';
import { createServer, request } from 'node:http';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { extname, resolve } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { chromium } from 'playwright';
import { verifyPasskeyManagement } from './passkeys.mjs';
import { verifyLinks } from './links.mjs';

const root = resolve('public');
const evidence = '/tmp/evidence';
await mkdir(evidence, { recursive: true });
const control = async (path, body) => {
  const response = await fetch('http://platform-test:3001' + path, { signal: AbortSignal.timeout(12000), ...(body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }) });
  assert.equal(response.status, 200, 'Fixture control failed');
  return response.json();
};
const until = async (fn, message, ms = 15000) => {
  const end = Date.now() + ms;
  do { if (await fn()) return; await delay(100); } while (Date.now() < end);
  throw new Error(message);
};

// Same-origin static/proxy transport only; this contains no application routes or data.
const web = createServer(async (req, res) => {
  if (req.url.startsWith('/api/')) {
    const upstream = request({ hostname: 'platform-test', port: 3000, path: req.url,
      method: req.method, headers: req.headers }, answer => {
      res.writeHead(answer.statusCode, answer.headers); answer.pipe(res);
    });
    upstream.on('error', () => { res.writeHead(502); res.end(); });
    req.pipe(upstream);
    return;
  }
  try {
    const path = resolve(root, '.' + new URL(req.url, 'http://localhost').pathname);
    if (!path.startsWith(root + '/') && path !== root) { res.writeHead(404); res.end(); return; }
    const file = path === root ? resolve(root, 'index.html') : path;
    const mime = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
      '.png': 'image/png', '.svg': 'image/svg+xml', '.woff2': 'font/woff2' }[extname(file)] || 'application/octet-stream';
    const content = await readFile(file);
    res.writeHead(200, { 'Content-Type': mime }); res.end(content);
  } catch { if (!res.headersSent) res.writeHead(404); res.end(); }
});
await new Promise(done => web.listen(8080, '127.0.0.1', done));
let browser, context, page;
let stage = 'setup';
const cases = [], errors = [], statuses = [];
const report = async id => {
  await page.screenshot({ path: `${evidence}/${id}.png`, fullPage: true, animations: 'disabled' });
  cases.push(id);
  console.log(JSON.stringify({ case: id, status: 'PASS' }));
};
const button = name => page.getByRole('button', { name, exact: true });
const local = () => page.evaluate(() => ({
  state: JSON.parse(localStorage.getItem('gym_state_v1') || 'null'),
  dirty: localStorage.getItem('gym_dirty'),
  base: JSON.parse(localStorage.getItem('gym_sync') || 'null'),
}));
const snapshot = () => control('/snapshot');
const clean = async () => until(async () => (await local()).dirty !== '1', 'Client changes never acknowledged');
const sync = async () => {
  await page.goto('http://localhost:8080/#/settings/account');
  await page.getByText('Sincronizar ahora', { exact: true }).click();
};
const theme = async name => {
  await page.goto('http://localhost:8080/#/settings/look');
  await button(name).click();
};
const login = async () => {
  await page.goto('http://localhost:8080/#/settings/account');
  await page.getByText('Iniciar sesión con contraseña', { exact: true }).click();
  await page.getByPlaceholder('Nombre o correo', { exact: true }).fill('Alice');
  await page.getByPlaceholder('Contraseña', { exact: true }).fill('Café Ａngstrom 42!');
  await page.locator('#modal-root').getByRole('button', { name: 'Iniciar sesión', exact: true }).click();
  await page.getByPlaceholder('Contraseña', { exact: true }).waitFor({ state: 'hidden' });
};

try {
  await until(async () => { try { return (await control('/ready')).ready; } catch { return false; } }, 'Python fixture never ready', 60000);
  browser = await chromium.launch();
  context = await browser.newContext({ locale: 'es-ES', viewport: { width: 1280, height: 900 } });
  page = await context.newPage();
  page.setDefaultTimeout(12000);
  page.on('pageerror', error => errors.push(error.name));
  page.on('response', response => {
    if (response.url().endsWith('/api/v1/data') && response.request().method() === 'PUT') statuses.push(response.status());
  });
  stage = 'login';
  await page.goto('http://localhost:8080');
  await button('Continuar sin cuenta').waitFor();
  assert.equal((await local()).state?.routines?.length || 0, 0, 'Browser must start empty');
  await login();
  stage = 'passkeys';
  await verifyPasskeyManagement({ page, context, control, until });
  await report(stage);
  stage = 'login';
  await page.goto('http://localhost:8080/#/');
  await button('Crear mi propio plan').waitFor();
  await page.getByRole('navigation').getByRole('button', { name: 'Plan', exact: true }).click();
  await button('Rutinas').click();
  await button('Nueva rutina').click();
  await page.getByRole('textbox').fill('Platform browser routine');
  await button('Añadir ejercicio').click();
  await page.locator('#modal-root').getByRole('textbox', { name: /Buscar entre/ }).fill('squat');
  await page.locator('#modal-root').getByRole('button', { name: 'Añadir «sentadilla (squat)»', exact: true }).click();
  await page.keyboard.press('Escape');
  await button('sentadilla (squat) 3 × 10').waitFor();
  await clean();
  await until(async () => (await snapshot()).A?.routines?.[0]?.name === 'Platform browser routine', 'Routine never reached PostgreSQL');
  await button('Inicio').click();
  await button('Elegir otro entrenamiento').click();
  await page.getByText('Platform browser routine', { exact: true }).click();
  await page.getByRole('checkbox', { name: 'Serie 1 hecha', exact: true }).waitFor();
  const activeId = (await local()).state.active.id;
  assert.ok(activeId, 'Workout did not start');
  await button('Minimizar').click();
  await theme('Oscuro');
  await clean();
  await report(stage);

  stage = 'offline';
  const beforeOffline = (await snapshot()).A;
  await context.setOffline(true);
  await button('Claro').click();
  await page.waitForFunction(() => localStorage.getItem('gym_dirty') === '1');
  assert.equal((await local()).state.active.id, activeId, 'Offline edit lost active workout');
  assert.equal((await local()).state.theme, 'light');
  assert.equal((await local()).dirty, '1');
  assert.deepEqual((await snapshot()).A, beforeOffline, 'Offline changes reached SQL');
  await report(stage);
  await context.setOffline(false);
  await page.reload();
  await sync();
  await clean();
  await until(async () => (await snapshot()).A.theme === 'light', 'Offline changes never synced');
  assert.ok(!(await snapshot()).A.active, 'Active workout leaked to server');

  stage = 'auth';
  await control('/revoke', {});
  const beforeAuth = (await snapshot()).A;
  await theme('Oscuro');
  await until(async () => statuses.includes(401), 'No real 401 observed');
  assert.equal((await local()).dirty, '1');
  assert.equal((await local()).state.active.id, activeId);
  assert.deepEqual((await snapshot()).A, beforeAuth, 'Revoked client wrote to PostgreSQL');
  await page.reload();
  await login();
  await sync();
  await clean();
  assert.equal((await local()).state.active.id, activeId, 'Sign-in lost active workout');
  assert.equal((await snapshot()).A.theme, 'dark');
  await report(stage);

  stage = 'conflicts';
  let competitors = 0;
  const start = statuses.length;
  await page.route('**/api/v1/data', async route => {
    if (route.request().method() === 'PUT' && competitors < 2) {
      competitors++;
      await control('/compete', { id: `concurrent-${competitors}` });
    }
    await route.continue();
  });
  await theme('Claro');
  await until(() => statuses.slice(start).filter(status => status === 409).length === 2, 'Expected two genuine SQL conflicts');
  await clean();
  assert.equal(competitors, 2);
  assert.equal(statuses.slice(start).filter(status => status === 200).length, 1);
  const merged = (await snapshot()).A;
  assert.equal(merged.theme, 'light');
  assert.ok(['concurrent-1', 'concurrent-2'].every(id => merged.workouts.some(w => w.id === id)));
  await page.unroute('**/api/v1/data');
  await report(stage);

  stage = 'lost-reply';
  let dropped = false;
  const previousRev = (await snapshot()).A._rev;
  await page.route('**/api/v1/data', async route => {
    if (route.request().method() !== 'PUT' || dropped) return route.continue();
    dropped = true;
    const response = await route.fetch();
    assert.equal(response.status(), 200, 'Save must commit before losing its answer');
    await route.abort('failed');
  });
  await theme('Oscuro');
  await until(() => dropped, 'Response was not dropped');
  await until(async () => (await snapshot()).A._rev > previousRev, 'Lost reply did not commit');
  await page.getByText(/Tus cambios.*dispositivo|Tus cambios.*aquí/).first().waitFor();
  assert.equal((await local()).dirty, '1');
  assert.equal((await snapshot()).A.theme, 'dark');
  assert.equal((await local()).base.rev, previousRev, 'Lost reply falsely acknowledged the commit');
  await page.unroute('**/api/v1/data');
  const retryStart = statuses.length;
  await sync();
  await clean();
  assert.ok(statuses.slice(retryStart).includes(200), 'Sync now must reconcile and confirm the saved copy');
  assert.equal((await local()).base.wid, (await snapshot()).A._wid);
  assert.equal((await local()).state.active.id, activeId);
  assert.deepEqual((await snapshot()).A.workouts.map(w => w.id).sort(), ['concurrent-1', 'concurrent-2']);
  await report(stage);

  stage = 'restore';
  await context.setOffline(true);
  await theme('Claro');
  await page.waitForFunction(() => localStorage.getItem('gym_dirty') === '1');
  const restored = await control('/restore', {});
  assert.equal((await local()).base.rev, restored.rev);
  await context.setOffline(false);
  await sync();
  await clean();
  const final = (await snapshot()).A;
  assert.equal(final.theme, 'light');
  assert.deepEqual(final.workouts.map(w => w.id).sort(), ['concurrent-1', 'concurrent-2', 'restored-workout']);
  assert.ok(final._wids.includes('synthetic-restored-branch'));
  assert.equal((await local()).state.active.id, activeId);
  await page.reload();
  assert.equal((await local()).state.active.id, activeId, 'Final reload lost active workout');
  assert.deepEqual((await local()).state.workouts.map(w => w.id).sort(), ['concurrent-1', 'concurrent-2', 'restored-workout']);
  assert.deepEqual((await snapshot()).B, { _rev: 2, workouts: [{ id: 'foreign-sentinel' }] });
  assert.ok(!final.active, 'Restored sync leaked the device-local workout');
  assert.equal(errors.length, 0, 'Browser runtime errors');
  await report(stage);
  stage = 'reset';
  await control('/reset-fixture', {});
  const beforeReset = await control('/reset-state');
  await page.reload();
  await page.goto('http://localhost:8080/#/settings/account');
  await page.getByText('Iniciar sesión con contraseña', { exact: true }).click();
  await button('¿Tienes un código de restablecimiento de tu administrador?').click();
  await page.getByPlaceholder('Nombre o correo', { exact: true }).fill('Alice');
  await page.getByPlaceholder('Código de restablecimiento', { exact: true }).fill('K7WQ-2MZP-4HXA');
  await page.getByPlaceholder('Contraseña nueva', { exact: true }).fill('Café Ａngstrom 42!');
  await page.getByPlaceholder('Repite la contraseña', { exact: true }).fill('Café Ａngstrom 42!');
  await button('Guardar contraseña e iniciar sesión').click();
  await page.getByPlaceholder('Código de restablecimiento', { exact: true }).waitFor({ state: 'hidden' });
  await page.reload();
  assert.equal((await control('/reset-state')).remaining, 0);
  assert.equal((await control('/reset-state')).password, 1);
  assert.equal((await control('/reset-state')).version, beforeReset.version + 1);
  assert.equal((await local()).state.active.id, activeId, 'Password reset lost active workout');
  assert.deepEqual((await snapshot()).B, { _rev: 2, workouts: [{ id: 'foreign-sentinel' }] });
  assert.equal(errors.length, 0, 'Browser runtime errors after reset');
  await report(stage);
  stage = 'links';
  await verifyLinks({ page, browser, control, until });
  assert.equal((await local()).state.active.id, activeId, 'Adding devices lost active workout');
  assert.equal(errors.length, 0, 'Browser runtime errors after adding devices');
  await report(stage);
  await page.goto('http://localhost:8080/#/settings/about');
  stage = 'media';
  const photo = await control('/media-fixture', { day: await page.evaluate(() => new Date().toLocaleDateString('en-CA')) });
  let downloads = 0;
  page.on('response', response => {
    if (response.url().endsWith('/api/v1/media/' + photo.hash) && response.status() === 200) downloads++;
  });
  await sync();
  await until(async () => (await local()).state.workouts.some(w => w.id === 'private-progress-photo'), 'Second-device photo never synchronized');
  await page.goto('http://localhost:8080/#/progress-photos');
  const tile = page.locator('.wmedia-item');
  await tile.waitFor();
  await tile.click();
  const viewer = page.getByRole('dialog', { name: 'Foto', exact: true });
  await viewer.waitFor();
  await until(async () => viewer.locator('img').evaluateAll(images => images.some(image => image.complete && image.naturalWidth === 1)), 'Photo viewer never decoded');
  assert.ok(downloads > 0, 'Browser never downloaded the private bytes');
  await context.setOffline(true);
  assert.ok(await viewer.locator('img').evaluate(image => image.complete && image.naturalWidth === 1), 'Verified local photo lost offline');
  await context.setOffline(false);
  assert.equal((await local()).state.active.id, activeId, 'Media sync lost active workout');
  assert.equal(errors.length, 0, 'Browser runtime errors after media');
  await report(stage);
  await viewer.getByRole('button', { name: 'Cerrar', exact: true }).click();
  stage = 'media-queue';
  let blocked = 0;
  await page.route('**/api/v1/media/*', async route => {
    if (route.request().method() === 'PUT') { blocked++; return route.abort('failed'); }
    return route.continue();
  });
  // Real picker and ingest create the pending bytes; only transport failure is injected.
  await page.locator('input[type=file]').setInputFiles({ name: 'private-queued.png', mimeType: 'image/png',
    buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=', 'base64') });
  await until(async () => blocked > 0 && (await local()).state.workouts.find(w => w.id === 'private-progress-photo').media.length === 2, 'Picker never queued a photo');
  await clean();
  const queued = (await local()).state.workouts.find(w => w.id === 'private-progress-photo').media[1];
  const owedHashes = [...new Set([queued.hash, queued.poster?.hash].filter(Boolean))];
  const records = () => page.evaluate(() => new Promise((resolve, reject) => {
    const open = indexedDB.open('opengym-media', 1);
    open.onerror = () => reject(open.error);
    open.onsuccess = () => {
      const db = open.result, tx = db.transaction('blobs', 'readonly'), get = tx.objectStore('blobs').getAll();
      get.onsuccess = () => resolve(get.result.map(({ hash, size, pending }) => ({ hash, size, pending })));
      get.onerror = () => reject(get.error);
      tx.oncomplete = () => db.close();
    };
  }));
  const pendingRecords = await records();
  assert.ok(owedHashes.every(hash => pendingRecords.some(r => r.hash === hash && r.pending)), 'Failed upload was falsely marked synced');
  assert.ok((await control('/media-queue')).files.every(f => !owedHashes.includes(f.hash)), 'Aborted upload reached disk');
  await page.goto('http://localhost:8080/#/settings/data');
  await page.getByText(/1 pendientes de subir/).waitFor();
  await page.reload();
  await page.getByText(/1 pendientes de subir/).waitFor();
  assert.ok(owedHashes.every(hash => pendingRecords.some(r => r.hash === hash && r.size > 0)));
  await page.unroute('**/api/v1/media/*');
  const uploadStatuses = [];
  const uploaded = response => { if (response.request().method() === 'PUT' && response.url().includes('/api/v1/media/')) uploadStatuses.push(response.status()); };
  page.on('response', uploaded);
  await page.getByText('Fotos y vídeos', { exact: true }).click();
  await until(async () => { const current = await records(); return owedHashes.every(hash => current.some(r => r.hash === hash && !r.pending)); }, 'Manual retry never confirmed the queued files');
  const persistedMedia = await control('/media-queue');
  assert.ok(owedHashes.every(hash => persistedMedia.files.some(f => f.hash === hash && f.size > 0)), 'Independent server bytes missing after retry');
  assert.ok(uploadStatuses.includes(201), 'Retry did not publish real media');
  const beforeRepeat = uploadStatuses.length;
  const repeatedMissing = page.waitForResponse(response => response.url().endsWith('/api/v1/media/missing') && response.request().method() === 'POST');
  await page.getByText('Fotos y vídeos', { exact: true }).click();
  const repeatedAnswer = await repeatedMissing;
  assert.equal(repeatedAnswer.status(), 200);
  assert.deepEqual((await repeatedAnswer.json()).missing, []);
  await delay(250);
  assert.equal(uploadStatuses.length, beforeRepeat, 'Missing handshake reuploaded intact media');
  assert.equal((await local()).state.active.id, activeId);
  assert.equal(errors.length, 0);
  await report(stage);
  page.off('response', uploaded);
  await page.goto('http://localhost:8080/#/settings/about');
  const frontend = await page.getByText(/^v\d.*\+platform-browser-proof$/).innerText();
  assert.equal(process.versions.node, '22.23.2');
  await writeFile(`${evidence}/result.json`, JSON.stringify({ completed: true, cases, errors: errors.length,
    node: process.versions.node, browser: browser.version(), frontend,
    faults: { unauthorized: statuses.filter(s => s === 401).length, conflicts: competitors, lostResponses: Number(dropped) } }));
  await control('/done', { completed: true, cases, errors: errors.length });
} catch (error) {
  console.error(JSON.stringify({ stage, error: error.name, message: error.message.split('\n')[0] }));
  if (page) await page.screenshot({ path: `${evidence}/FAIL.png`, fullPage: true, animations: 'disabled' }).catch(() => {});
  await writeFile(`${evidence}/result.json`, JSON.stringify({ completed: false, stage, cases, errors: errors.length }));
  await control('/done', { completed: false, stage, cases, errors: errors.length }).catch(() => {});
  process.exitCode = 1;
} finally {
  if (context) await context.close();
  if (browser) await browser.close();
  // Keep tmpfs evidence mounted until the harness copies it and removes this owned container.
}
