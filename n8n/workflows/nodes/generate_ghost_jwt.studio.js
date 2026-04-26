// =============================================================================
// Node: Generate Ghost Admin JWT  (Track B5.2)
// =============================================================================
// Mints a 5-minute Ghost Admin API JWT from $env.GHOST_ADMIN_KEY.
// Format expected for GHOST_ADMIN_KEY: "<24-hex-id>:<64-hex-secret>".
//
// Outputs:
//   - token : Ghost Admin JWT (string, valid 5 min, audience "/admin/")
//
// Usage downstream:
//   Authorization: Ghost {{ $('Generate Ghost JWT').first().json.token }}
//
// Notes:
// - This Code node uses pure JS via Node crypto (no extra deps), since N8N
//   Code nodes don't ship the `jsonwebtoken` module reliably across versions.
// - Secret is hex-decoded before HMAC, per Ghost's spec.
// =============================================================================

const crypto = require('crypto');

const raw = $env.GHOST_ADMIN_KEY || '';
if (!raw || !raw.includes(':')) {
  throw new Error('GHOST_ADMIN_KEY env var missing or malformed (expected "id:secret")');
}
const [keyId, secretHex] = raw.split(':');
const secret = Buffer.from(secretHex, 'hex');

const iat = Math.floor(Date.now() / 1000);
const header = { alg: 'HS256', typ: 'JWT', kid: keyId };
const payload = { iat, exp: iat + 5 * 60, aud: '/admin/' };

function b64url(buf) {
  return Buffer.from(buf)
    .toString('base64')
    .replace(/=+$/, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_');
}

const signingInput =
  b64url(JSON.stringify(header)) + '.' + b64url(JSON.stringify(payload));
const signature = b64url(
  crypto.createHmac('sha256', secret).update(signingInput).digest()
);

return [{ json: { token: signingInput + '.' + signature } }];
