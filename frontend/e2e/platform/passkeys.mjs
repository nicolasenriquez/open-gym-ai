// Real Settings UI and WebAuthn transport; Chromium's authenticator is synthetic.
import assert from 'node:assert/strict';

export async function verifyPasskeyManagement({ page, context, control, until }) {
  const cdp = await context.newCDPSession(page);
  await cdp.send('WebAuthn.enable');
  const { authenticatorId } = await cdp.send('WebAuthn.addVirtualAuthenticator', { options: {
    protocol: 'ctap2', transport: 'internal', hasResidentKey: true,
    hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true,
  } });
  const button = name => page.getByRole('button', { name, exact: true });
  const name = page.getByPlaceholder('Nombre, p. ej. Portátil del trabajo', { exact: true });
  try {
    await page.getByText('Passkeys', { exact: true }).click();
    await button('Añadir una passkey').click();
    await name.fill('Browser synthetic key');
    await page.getByPlaceholder('Contraseña actual', { exact: true }).fill('Café Ａngstrom 42!');
    await button('Continuar').click();
    await button('Crear passkey').click();
    await page.getByText('Browser synthetic key', { exact: true }).waitFor();
    await until(async () => (await control('/passkeys')).own.length === 1, 'Passkey not committed');
    const added = (await control('/passkeys')).own[0];
    assert.equal(added.label, 'Browser synthetic key');
    assert.equal((await cdp.send('WebAuthn.getCredentials', { authenticatorId })).credentials.length, 1);
    await page.getByText('Browser synthetic key', { exact: true }).click();
    await name.fill('Renamed browser key');
    await button('Guardar').click();
    await until(async () => (await control('/passkeys')).own[0]?.label === 'Renamed browser key', 'Rename not committed');
    await page.reload();
    await page.getByText('Passkeys', { exact: true }).click();
    await page.getByText('Renamed browser key', { exact: true }).click();
    await button('Quitar passkey').click();
    // Confirm with the actual synthetic assertion, not a mocked verification reply.
    await button('Confirmar con una passkey').click();
    await until(async () => (await control('/passkeys')).own.length === 0, 'Removal not committed');
    await page.reload();
    await page.getByText('Passkeys', { exact: true }).click();
    await button('Añadir una passkey').waitFor();
    assert.equal(await page.getByText('Renamed browser key', { exact: true }).count(), 0);
    const final = await control('/passkeys');
    assert.equal(final.foreign, 1, 'Foreign passkey changed');
    assert.equal(final.sessionVersion, 0, 'Management revoked existing session');
    await page.keyboard.press('Escape');
  } finally {
    await cdp.send('WebAuthn.removeVirtualAuthenticator', { authenticatorId });
    await cdp.detach();
  }
}
