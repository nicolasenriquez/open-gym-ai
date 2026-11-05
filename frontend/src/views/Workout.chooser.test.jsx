// @vitest-environment happy-dom
import React, { act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import Workout from './Workout.jsx'
import { DEF, useStore } from '../store/useStore.js'
import { setLang } from '../lib/i18n.js'
import { startFlow } from '../sheets.jsx'

vi.mock('../sheets.jsx', async importOriginal => ({ ...await importOriginal(), startFlow: vi.fn() }))
vi.mock('../lib/api.js', () => ({ api: vi.fn(() => Promise.resolve({})), appBase: () => '/' }))
globalThis.IS_REACT_ACT_ENVIRONMENT = true
let root, host
afterEach(() => { act(() => root.unmount()); host.remove() })

it('exposes each alternative routine as a native non-submit button with its own start action', () => {
  setLang('en')
  const S = JSON.parse(JSON.stringify(DEF))
  S.routines = [{id:'one', name:'Routine One', ex:[]}, {id:'two', name:'Routine Two', ex:[]}]
  S.week = {}; S.dayPlan = {}; S.active = null
  useStore.setState({ S, user: null })
  host = document.createElement('div'); document.body.appendChild(host); root = createRoot(host)
  act(() => root.render(<MemoryRouter><Workout /></MemoryRouter>))
  const rows = [...host.querySelectorAll('.list .item')]
  expect(rows).toHaveLength(2)
  rows.forEach((row, i) => {
    expect(row.tagName).toBe('BUTTON')
    expect(row.type).toBe('button')
    expect(row.textContent).toContain(i ? 'Routine Two' : 'Routine One')
    act(() => row.click())
    expect(startFlow).toHaveBeenLastCalledWith([i ? 'two' : 'one'])
  })
  expect(startFlow).toHaveBeenCalledTimes(2)
})
