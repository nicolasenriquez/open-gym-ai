// Python push copy from the existing canonical frontend/Node generators, no runtime Node.
import { readFileSync, writeFileSync } from 'node:fs';
import { buildNudgeCopy } from '../api/scripts/build-nudge-copy.mjs';
import { dayReminderPush, restTimerPush, testPush } from '../api/push-messages.js';

const generated = await buildNudgeCopy();
const nudges = JSON.parse(generated.slice(generated.indexOf('export const NUDGE_COPY = ') + 26).trim().replace(/;$/, ''));
const reminders = Object.fromEntries(['en', 'pt-BR'].map(lang => [lang, {
  named: dayReminderPush(lang, { emoji: '{emoji}', name: '{name}' }),
  fallback: dayReminderPush(lang),
}]));
const output = new URL('../backend/src/opengym_platform/notifications/copy.json', import.meta.url);
const alerts = Object.fromEntries(['en', 'pt-BR'].map(lang => [lang, {
  rest: restTimerPush(lang), test: testPush(lang),
}]));
const text = JSON.stringify({ reminders, nudges, alerts }) + '\n';
if (process.argv.includes('--check')) {
  if (readFileSync(output, 'utf8') !== text) throw new Error('Push assets out of date; run node scripts/build-push-assets.mjs');
} else writeFileSync(output, text);
