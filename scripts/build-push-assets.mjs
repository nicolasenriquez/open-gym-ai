// Python notification copy from canonical UI strings; no runtime Node dependency.
import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { dayReminderPush, restTimerPush, testPush } from '../shared/notifications/push-messages.js';
import { NUDGE_COPY } from '../frontend/src/lib/nudge.js';

const nudges = { en: NUDGE_COPY };
for (const file of readdirSync(new URL('../frontend/src/locales/', import.meta.url)).filter(f => /^[a-zA-Z-]+\.js$/.test(f)).sort((a, b) => a.slice(0, -3).localeCompare(b.slice(0, -3)))) {
  const lang = file.slice(0, -3);
  const pack = (await import(new URL('../frontend/src/locales/' + file, import.meta.url))).default;
  const tr = text => pack[text] || text;
  nudges[lang] = Object.fromEntries(Object.entries(NUDGE_COPY).map(([tone, copy]) =>
    [tone, { title: tr(copy.title), lines: copy.lines.map(tr) }]));
}
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
