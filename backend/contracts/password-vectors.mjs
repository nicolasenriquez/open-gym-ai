// Independent Node reference; regenerate only when deliberately extending coverage.
import { scryptSync } from 'node:crypto';
import { writeFileSync } from 'node:fs';
import { nameKey, verifyPassword } from '../../api/password.js';

const vectors = [];
for (const [password, ln, r, p, length] of [
  ['Café Ａngstrom 42!', 15, 8, 1, 32],
  [' legacy key length ', 10, 1, 1, 64],
]) {
  const salt = Buffer.from('independent-salt');
  const key = scryptSync(password.normalize('NFKC'), salt, length, {
    N: 2 ** ln, r, p, maxmem: 128 * 2 ** ln * r * p + 16 * 1024 * 1024,
  });
  const hash = `$scrypt$v=1$ln=${ln},r=${r},p=${p}$${salt.toString('base64')}$${key.toString('base64')}`;
  for (const candidate of [password, password.normalize('NFD'), password.trim(), password.toLowerCase(), 'wrong']) {
    vectors.push({ password: candidate, hash, matches: await verifyPassword(candidate, hash) });
  }
}
const aliases = [' ＡＬＩＣＥ ', 'İ', 'ΟΣ', '\uFEFFAna\uFEFF', '\u0085Ana\u0085', 'Straße', 'Kelvin'];
writeFileSync(new URL('./identity-passwords.v1.json', import.meta.url), JSON.stringify({
  source: 'Node api/password.js; deterministic synthetic salts, no user credentials',
  vectors, aliases: aliases.map(input => ({ input, key: nameKey(input) })),
  identifiers: [0, -0, 1.0, 0.000001, 1e-7, 1e20, 1e21, 9007199254740993].map(input => ({ input, text: String(input) })),
}, null, 2) + '\n');
