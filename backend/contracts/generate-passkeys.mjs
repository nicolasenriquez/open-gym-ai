// Independent synthetic authenticator: private keys exist only in this process.
import assert from 'node:assert/strict';
import { createHash, generateKeyPairSync, randomBytes, sign } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { verifyRegistrationResponse, verifyAuthenticationResponse } from '../../api/node_modules/@simplewebauthn/server/esm/index.js';
import { isoCBOR } from '../../api/node_modules/@simplewebauthn/server/esm/helpers/iso/index.js';

const b64 = value => Buffer.from(value).toString('base64url');
const hash = value => createHash('sha256').update(value).digest();
const challenge = b64(Buffer.from(Array.from({ length: 32 }, (_, i) => i)));
const origin = 'http://localhost:8080';
const rpId = 'localhost';
const check = process.argv.includes('--check');
const fixture = new URL('./identity-passkeys.v1.json', import.meta.url);
const cases = check ? JSON.parse(readFileSync(fixture, 'utf8')).cases : [];
for (const algorithm of check ? [] : ['ES256', 'RS256', 'Ed25519']) {
  const { privateKey, publicKey } = algorithm === 'ES256'
    ? generateKeyPairSync('ec', { namedCurve: 'prime256v1' })
    : algorithm === 'RS256' ? generateKeyPairSync('rsa', { modulusLength: 2048 }) : generateKeyPairSync('ed25519');
  const jwk = publicKey.export({ format: 'jwk' });
  const bytes = key => new Uint8Array(Buffer.from(jwk[key], 'base64url'));
  const cose = algorithm === 'ES256' ? new Map([[1, 2], [3, -7], [-1, 1], [-2, bytes('x')], [-3, bytes('y')]])
    : algorithm === 'RS256' ? new Map([[1, 3], [3, -257], [-1, bytes('n')], [-2, bytes('e')]])
      : new Map([[1, 1], [3, -8], [-1, 6], [-2, bytes('x')]]);
  const encodedKey = Buffer.from(isoCBOR.encode(cose));
  const id = randomBytes(24);
  const clientData = (type, changes = {}) => Buffer.from(JSON.stringify({ type, challenge, origin, crossOrigin: false, ...changes }));
  const authData = (flags, counter, rp = rpId) => {
    const tail = Buffer.alloc(5); tail[0] = flags; tail.writeUInt32BE(counter, 1);
    return Buffer.concat([hash(rp), tail]);
  };
  const register = (flags = 65, changes = {}, rp = rpId) => {
    const length = Buffer.alloc(2); length.writeUInt16BE(id.length);
    const data = Buffer.concat([authData(flags, 0, rp), Buffer.alloc(16), length, id, encodedKey]);
    return { id: b64(id), rawId: b64(id), type: 'public-key', response: {
      clientDataJSON: b64(clientData('webauthn.create', changes)),
      attestationObject: b64(isoCBOR.encode(new Map([['fmt', 'none'], ['attStmt', new Map()], ['authData', new Uint8Array(data)]]))),
      transports: ['internal', 'hybrid'],
    }, clientExtensionResults: {} };
  };
  const assertion = (counter = 1, flags = 1, changes = {}, rp = rpId, tamper = false) => {
    const data = authData(flags, counter, rp);
    const client = clientData('webauthn.get', changes);
    const signature = sign(algorithm === 'Ed25519' ? null : 'sha256', Buffer.concat([data, hash(client)]), privateKey);
    if (tamper) signature[signature.length - 1] ^= 1;
    return { id: b64(id), rawId: b64(id), type: 'public-key', response: {
      clientDataJSON: b64(client), authenticatorData: b64(data), signature: b64(signature),
      userHandle: null,
    }, clientExtensionResults: {} };
  };
  const add = (name, kind, credential, expected, observedCounter = 0, newCounter = 0) => {
    cases.push({ name: `${algorithm}/${name}`, algorithm, kind, credential, publicKey: b64(encodedKey),
      credentialId: b64(id), expected, observedCounter, newCounter });
  };
  add('register', 'register', register(), true);
  add('register-backed-up', 'register', register(89), true);
  add('register-origin', 'register', register(65, { origin: 'https://foreign.test' }), false);
  add('register-rp', 'register', register(65, {}, 'foreign.test'), false);
  add('register-challenge', 'register', register(65, { challenge: 'wrong' }), false);
  add('register-presence', 'register', register(64), false);
  add('assertion', 'login', assertion(), true, 0, 1);
  add('uv', 'login', assertion(1, 5), true, 0, 1);
  add('zero', 'login', assertion(0), true, 0, 0);
  add('backup', 'login', assertion(1, 25), true, 0, 1);
  add('replay', 'login', assertion(1), false, 1);
  add('origin', 'login', assertion(1, 1, { origin: 'https://foreign.test' }), false);
  add('rp', 'login', assertion(1, 1, {}, 'foreign.test'), false);
  add('challenge', 'login', assertion(1, 1, { challenge: 'wrong' }), false);
  add('signature', 'login', assertion(1, 1, {}, rpId, true), false);
  add('presence', 'login', assertion(1, 0), false);
  add('invalid-backup', 'login', assertion(1, 17), false);
}
for (const vector of cases) {
  let accepted = false;
  try {
    const common = { response: vector.credential, expectedChallenge: challenge, expectedOrigin: origin,
      expectedRPID: rpId, requireUserVerification: false };
    const result = vector.kind === 'register' ? await verifyRegistrationResponse(common)
      : await verifyAuthenticationResponse({ ...common, credential: { id: vector.credentialId,
        publicKey: Buffer.from(vector.publicKey, 'base64url'), counter: vector.observedCounter } });
    accepted = result.verified;
    if (accepted && vector.kind === 'register') {
      assert.equal(result.registrationInfo.credential.id, vector.credentialId);
      assert.equal(b64(result.registrationInfo.credential.publicKey), vector.publicKey);
      assert.equal(result.registrationInfo.credential.counter, vector.newCounter);
    }
    if (accepted && vector.kind === 'login') assert.equal(result.authenticationInfo.newCounter, vector.newCounter);
  } catch (error) {
    if (error.code === 'ERR_ASSERTION') throw error;
  }
  assert.equal(accepted, vector.expected, vector.name);
}
if (!check) writeFileSync(fixture, `${JSON.stringify({
  source: '@simplewebauthn/server independent synthetic authenticator; no private keys exported',
  challenge, origin, rpId, cases,
}, null, 2)}\n`);
console.log(`Node WebAuthn vectors PASS ${cases.length}/${cases.length}`);
