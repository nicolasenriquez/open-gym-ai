// @vitest-environment happy-dom
/* JOB_ERRORS and BYOK_ERRORS are what a lifter reads when a Coach job fails, and they were English
 * literals that never went through t(): a German or Brazilian lifter read English in the middle of
 * an otherwise translated chat. They are getters over t() now. This reads every line in every
 * locale pack the way the app loads one (setLang), and pins that the text follows a language
 * picked after coach-api.js loaded, which a map translated once at load time would not.
 *
 * setLang sets the page's lang and dir (right-to-left for Arabic), so this runs with a DOM.
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ MOBILE: false, coachLocal: null }))
vi.mock('./demo.js', () => ({ DEMO: false, DEMO_SEEDED: 'gym_demo_seeded_v1', REPO: '' }))
vi.mock('./mobile.js', () => ({ get MOBILE() { return mocks.MOBILE } }))
vi.mock('./api.js', () => ({ api: vi.fn() }))
vi.mock('../store/useStore.js', () => ({ useStore: { getState: () => ({ S: {}, coachLocal: mocks.coachLocal }) } }))
vi.mock('../store/useUI.js', () => ({ useUI: { getState: () => ({ toast: vi.fn() }) } }))

const { JOB_ERRORS, BYOK_ERRORS, jobErrorText } = await import('./coach-api.js')
const { setLang, getLang, LANGS, DERIVED_LOCALES } = await import('./i18n.js')

const PACKS = Object.fromEntries(Object.entries(import.meta.glob('../locales/*.js', { eager: true }))
  .map(([path, mod]) => [path.match(/([^/]+)\.js$/)[1], mod.default]))
const MAPS = { JOB_ERRORS, BYOK_ERRORS }
// Read before any pack is loaded. English ships no pack, so these lines are the keys the packs
// translate, and what t() hands back in English.
const EN = Object.fromEntries(Object.entries(MAPS).map(([name, map]) =>
  [name, Object.fromEntries(Object.keys(map).map(cls => [cls, map[cls]]))]))
const LINES = Object.entries(EN).flatMap(([name, lines]) => Object.keys(lines).map(cls => [name, cls]))

afterEach(async () => {
  await setLang('en')
  mocks.MOBILE = false
  mocks.coachLocal = null
})

describe('every failure line, in every pack', () => {
  // Every language but English and a derived locale (de-CH) ships a pack. Counted from LANGS, so
  // a new language is read here without anyone remembering to bump a number.
  it('reads every pack', () => {
    const packLangs = Object.keys(LANGS).filter(l => l !== 'en' && !DERIVED_LOCALES[l]).sort()
    expect(Object.keys(PACKS).sort()).toEqual(packLangs)
  })

  it.each(Object.keys(PACKS).sort())('%s translates each one, and the map reads it from the pack', async lang => {
    const pack = PACKS[lang]
    await setLang(lang)
    expect(getLang()).toBe(lang)
    for (const [name, cls] of LINES) {
      const english = EN[name][cls]
      expect(pack[english], `${lang}: ${name}.${cls} has no entry for ${JSON.stringify(english)}`).toBeTruthy()
      expect(pack[english], `${lang}: ${name}.${cls} is still English`).not.toBe(english)
      expect(MAPS[name][cls], `${lang}: ${name}.${cls}`).toBe(pack[english])
    }
  })
})

describe('a language picked after coach-api.js loaded', () => {
  it('changes what the same map says, and switching back restores the English', async () => {
    expect(getLang()).toBe('en')
    expect(JOB_ERRORS.unprivileged).toBe(EN.JOB_ERRORS.unprivileged)

    await setLang('de')
    expect(JOB_ERRORS.unprivileged).toBe(PACKS.de[EN.JOB_ERRORS.unprivileged])
    expect(jobErrorText('timeout', 'gave up after 10 min')).toBe(PACKS.de[EN.JOB_ERRORS.timeout])

    await setLang('pt-BR')
    expect(JOB_ERRORS.unprivileged).toBe(PACKS['pt-BR'][EN.JOB_ERRORS.unprivileged])
    expect(jobErrorText('meteor')).toBe(PACKS['pt-BR'][EN.JOB_ERRORS.internal])
    expect(jobErrorText('meteor')).not.toBe(PACKS.pt[EN.JOB_ERRORS.internal])   // Brazil's own line, not Portugal's

    await setLang('en')
    expect(JOB_ERRORS.unprivileged).toBe(EN.JOB_ERRORS.unprivileged)
    expect(jobErrorText('timeout')).toBe(EN.JOB_ERRORS.timeout)
  })

  it('reaches the own-key phone lines, with the provider detail still attached', async () => {
    mocks.MOBILE = true
    mocks.coachLocal = { mode: 'byok' }
    await setLang('fr')
    expect(jobErrorText('provider', 'quota exceeded')).toBe(PACKS.fr[EN.BYOK_ERRORS.provider] + '\nquota exceeded')
    // A class the phone has no line of its own for falls back to the shared one, translated too.
    expect(jobErrorText('restart')).toBe(PACKS.fr[EN.JOB_ERRORS.restart])
    expect(jobErrorText(undefined)).toBe(PACKS.fr[EN.BYOK_ERRORS.internal])
  })
})

/* Contract classes stay explicit; the source inventory detects a new Python refusal.
 * Auth failures sign out; the shared-account message deliberately keeps server wording. */
describe('every Python Coach refusal has translated client wording', () => {
  const jobs = readFileSync(resolve(process.cwd(), '../backend/src/opengym_platform/coach/jobs.py'), 'utf8')
  const block = jobs.match(/ERRORS = \{([\s\S]*?)\n\}/)?.[1]
  const classes = [...(block || '').matchAll(/^    "(\w+)":/gm)].map(m => m[1]).sort()
  it('pins the server refusal inventory', () => {
    expect(classes).toEqual(['busy', 'cap', 'consent', 'off', 'shared', 'unauthorized'])
  })
  it.each(['off', 'busy', 'cap', 'consent'])('translates %s', cls => {
    expect(EN.JOB_ERRORS[cls]).toBeTruthy()
    expect(JOB_ERRORS[cls]).toBe(EN.JOB_ERRORS[cls])
  })
  it('still explains the unavailable-provider class to compatible clients', () => {
    expect(EN.JOB_ERRORS.off).toBe('The Coach isn’t set up on this instance.')
  })
})
