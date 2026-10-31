// Existing admin controls against Python; codes never leave this browser proof.
import assert from 'node:assert/strict';

export async function verifyAdminInvites({ browser, owner, control, until, report, errors }) {
  const context = await browser.newContext({ locale: 'es-ES', viewport: { width: 1280, height: 900 } });
  try {
    const page = await context.newPage();
    page.setDefaultTimeout(12000);
    page.on('pageerror', error => errors.push(error.name));
    await page.goto('http://localhost:8080/#/settings/account');
    await page.getByText('Iniciar sesión con contraseña', { exact: true }).click();
    await page.getByPlaceholder('Nombre o correo', { exact: true }).fill('Bob');
    await page.getByPlaceholder('Contraseña', { exact: true }).fill('Café Ａngstrom 42!');
    await page.locator('#modal-root').getByRole('button', { name: 'Iniciar sesión', exact: true }).click();
    await page.getByPlaceholder('Contraseña', { exact: true }).waitFor({ state: 'hidden' });
    await page.goto('http://localhost:8080/#/admin');
    await page.getByRole('button', { name: 'New code', exact: true }).click();
    const invite = page.getByRole('button', { name: /^copy [0-9A-F]{16}$/ });
    await invite.waitFor();
    assert.equal((await control('/admin-state')).invitations, 1);
    await page.reload();
    await invite.waitFor();
    await page.getByRole('button', { name: 'revoke', exact: true }).click();
    await page.locator('#modal-root').getByRole('button', { name: 'Revoke', exact: true }).click();
    await until(async () => (await control('/admin-state')).invitations === 0, 'Revoked invitation persisted');
    await page.reload();
    await page.getByText('No codes yet. "New code" makes one and copies it to your clipboard.', { exact: true }).waitFor();
    const before = await control('/admin-state');
    await page.locator('.item').filter({ has: page.getByText('Alice', { exact: true }) }).click();
    await page.getByRole('button', { name: 'Reset password', exact: true }).click();
    await page.locator('#modal-root').getByRole('button', { name: 'Create reset code', exact: true }).click();
    await page.getByRole('heading', { name: 'Reset code for Alice', exact: true }).waitFor();
    assert.match(await page.getByRole('button', { name: 'copy code', exact: true }).innerText(), /^[A-Z2-9]{4}(?:-[A-Z2-9]{4}){2}$/);
    await page.getByRole('button', { name: 'Done', exact: true }).click();
    const after = await control('/admin-state');
    assert.equal(after.version, before.version + 1);
    assert.equal(after.passwords, 0);
    assert.equal(after.reset, true);
    assert.equal(after.digestBytes, 32);
    assert.equal((await owner.request.get('http://localhost:8080/api/v1/me')).status(), 401);
    await page.reload();
    await page.locator('.item').filter({ has: page.getByText('Alice', { exact: true }) }).click();
    await page.getByText(/^reset code until /).waitFor();
    assert.equal(errors.length, 0);
    await report('admin-invites', page);
  } finally {
    await context.close();
  }
}
