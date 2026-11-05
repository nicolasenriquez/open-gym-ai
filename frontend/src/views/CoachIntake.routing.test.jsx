// @vitest-environment happy-dom
import React, { act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import CoachIntake from './CoachIntake.jsx'
import { setLang } from '../lib/i18n.js'

const state = vi.hoisted(() => ({ ready: true, user: null, config: null, S: {} }))
vi.mock('../store/useStore.js', () => ({ useStore: selector => selector(state) }))
vi.mock('../store/useUI.js', () => ({ useUI: selector => selector({ toast: vi.fn() }) }))
vi.mock('../lib/coach-api.js', () => ({
  disclosure: () => Promise.resolve(null), requestPlan: vi.fn(), JOB_ERRORS: {},
}))

let root, host
globalThis.IS_REACT_ACT_ENVIRONMENT = true
const render = () => act(async () => {
  root.render(<MemoryRouter initialEntries={['/coach/intake']}><Routes>
    <Route path="/coach/intake" element={<CoachIntake />} />
    <Route path="/home" element={<h1>Home destination</h1>} />
  </Routes></MemoryRouter>)
})
beforeEach(() => {
  setLang('en')
  Object.assign(state, { ready: true, user: null, config: null, S: { customEx: [], routines: [] } })
  host = document.createElement('div'); document.body.appendChild(host)
  root = createRoot(host)
})
afterEach(() => { act(() => root.unmount()); host.remove() })

it('redirects a cold guest visit through the real router', async () => {
  const warning = vi.spyOn(console, 'warn').mockImplementation(() => {})
  try {
    await render()
    expect(host.textContent).toContain('Home destination')
    expect(warning.mock.calls.flat().join(' ')).not.toContain('navigate()')
  } finally { warning.mockRestore() }
})

it('waits for boot before allowing a configured user into intake', async () => {
  state.ready = false
  await render()
  expect(host.textContent).toBe('')
  Object.assign(state, { ready: true, user: { id: 'test-user' }, config: { coach: { enabled: true } } })
  await render()
  expect(host.textContent).toContain('Before we start')
})

it('redirects a signed-in user when Coach is disabled', async () => {
  Object.assign(state, { user: { id: 'test-user' }, config: { coach: { enabled: false } } })
  await render()
  expect(host.textContent).toContain('Home destination')
})
