// @vitest-environment happy-dom
import React, { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import Toast from './Toast.jsx'
import { useUI } from '../store/useUI.js'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
let root, host, one, two
beforeEach(() => {
  vi.useFakeTimers()
  useUI.setState({ sheets: [], toastMsg: '', toastAction: null })
  host = document.createElement('div'); document.body.appendChild(host)
  one = document.createElement('dialog'); one.id = 'sheet-one'; document.body.appendChild(one)
  two = document.createElement('dialog'); two.id = 'sheet-two'; document.body.appendChild(two)
  root = createRoot(host)
  act(() => root.render(<Toast />))
})
afterEach(() => {
  act(() => root.unmount())
  host.remove(); one.remove(); two.remove()
  useUI.setState({ sheets: [], toastMsg: '', toastAction: null })
  vi.clearAllTimers(); vi.useRealTimers()
})

it('moves the same pending action to the upper dialog, then back out as sheets close', () => {
  const undo = vi.fn()
  act(() => useUI.getState().toast('Removed', {action:'Undo', onAction:undo}))
  expect(host.querySelector('#toast')).not.toBeNull()
  act(() => useUI.setState({sheets:[{id:'one'}]}))
  expect(one.querySelector('#toast')).not.toBeNull()
  expect(host.querySelector('#toast')).toBeNull()
  act(() => useUI.setState({sheets:[{id:'one'}, {id:'two'}]}))
  expect(two.querySelector('#toast')).not.toBeNull()
  expect(one.querySelector('#toast')).toBeNull()
  act(() => useUI.setState({sheets:[{id:'one'}]}))
  expect(one.querySelector('#toast')).not.toBeNull()
  act(() => one.querySelector('.toast-act').click())
  expect(undo).toHaveBeenCalledTimes(1)
  expect(useUI.getState().toastAction).toBeNull()
  act(() => useUI.setState({sheets:[]}))
  expect(host.querySelector('#toast')).not.toBeNull()
  expect(document.querySelectorAll('#toast')).toHaveLength(1)
})
