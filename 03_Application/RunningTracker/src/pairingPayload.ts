/**
 * RunningTracker pairing payload (text / QR).
 *
 * Format: "ATLASRUN1|<base_url>|<code>", or the bare code when the server URL is not configured.
 * The prefix literal is repeated in backend/config.py (PAIRING_QR_PREFIX) and in Kotlin
 * (running/auth/PairingPayload.kt): keep all three in sync; each parser has a test.
 */

export const PAIRING_QR_PREFIX = 'ATLASRUN1';

export function buildPairingPayload(baseUrl: string | null, code: string): string {
  return baseUrl ? `${PAIRING_QR_PREFIX}|${baseUrl}|${code}` : code;
}
