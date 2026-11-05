// Real Settings → second browser passkey and mobile bearer transport. No fake API replies.
import assert from 'node:assert/strict';

export async function verifyLinks({ page, browser, control, until }) {
  const before = await control('/passkeys');
  const button = name => page.getByRole('button', { name, exact: true });
  await page.goto('http://localhost:8080/#/settings/account');
  await page.getByText('Añadir otro dispositivo', { exact: true }).click();
  await page.getByPlaceholder('Contraseña actual', { exact: true }).fill('Café Ａngstrom 42!');
  await button('Continuar').click();
  const shown = page.getByText(/^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{4}-[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{4}-[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{4}$/);
  await shown.waitFor();
  const code = await shown.innerText();
  assert.equal((await control('/links')).pending, 1);
  await button('Listo').click();

  const recipient = await browser.newContext({ locale: 'es-ES', viewport: { width: 1280, height: 900 } });
  const other = await recipient.newPage();
  const errors = [];
  other.on('pageerror', error => errors.push(error.name));
  other.setDefaultTimeout(12000);
  const cdp = await recipient.newCDPSession(other);
  await cdp.send('WebAuthn.enable');
  const { authenticatorId } = await cdp.send('WebAuthn.addVirtualAuthenticator', { options: {
    protocol: 'ctap2', transport: 'internal', hasResidentKey: true,
    hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true,
  } });
  try {
    await other.goto('http://localhost:8080/?link=' + encodeURIComponent(code));
    await other.getByText(/Crea en este dispositivo una passkey.*Alice/).waitFor();
    await other.getByRole('button', { name: 'Crear passkey', exact: true }).click();
    await until(async () => (await control('/passkeys')).own.length === before.own.length + 1, 'Device passkey not committed');
    await other.goto('http://localhost:8080/#/settings/account');
    await other.getByText('Sesión iniciada como Alice', { exact: true }).first().waitFor();
    await other.reload();
    await other.getByText('Sesión iniciada como Alice', { exact: true }).first().waitFor();
    assert.equal((await cdp.send('WebAuthn.getCredentials', { authenticatorId })).credentials.length, 1);
    const state = await control('/passkeys');
    assert.equal(state.foreign, before.foreign);
    assert.equal(state.sessionVersion, before.sessionVersion);
    assert.equal((await control('/links')).pending, 0);
    assert.equal(errors.length, 0, 'Second browser runtime errors');
  } finally {
    await cdp.send('WebAuthn.removeVirtualAuthenticator', { authenticatorId });
    await cdp.detach();
    await recipient.close();
  }

  await page.getByText('Emparejar la app móvil', { exact: true }).click();
  const pairText = page.getByText(/^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{8}$/);
  await pairText.waitFor();
  const pairCode = await pairText.innerText();
  const mobile = await browser.newContext();
  try {
    const response = await mobile.request.post('http://localhost:8080/api/v1/pair/redeem', {
      headers: { Origin: 'capacitor://localhost' }, data: { code: pairCode },
    });
    assert.equal(response.status(), 200);
    assert.equal(response.headers()['set-cookie'], undefined);
    const paired = await response.json();
    assert.equal(paired.user.id, 'A');
    const me = await mobile.request.get('http://localhost:8080/api/v1/me', { headers: { Authorization: 'Bearer ' + paired.token } });
    assert.equal((await me.json()).user.id, 'A');
    assert.equal((await mobile.request.post('http://localhost:8080/api/v1/pair/redeem', { data: { code: pairCode } })).status(), 400);
  } finally {
    await mobile.close();
  }
  await button('Listo').click();
  await page.reload();
  await page.getByText('Sesión iniciada como Alice', { exact: true }).first().waitFor();
}
