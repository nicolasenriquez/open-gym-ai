// @vitest-environment happy-dom
import { afterEach, expect, it, vi } from 'vitest'
import { nativeFetch } from './capacitor-fetch.js'

vi.mock('./mobile.js', () => ({ MOBILE: false }))
vi.mock('./app-base.js', () => ({ appBase: () => '/gym/' }))
vi.mock('./capacitor-fetch.js', () => ({ nativeFetch: vi.fn() }))

afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  vi.resetModules()
})

it.each([['', '/api'], ['/api/v1', '/api/v1']])('routes every transport with prefix %s', async (prefix, expected) => {
  vi.stubEnv('VITE_API_PREFIX', prefix)
  const { api, apiBlob, apiUpload, beacon, pairRedeem, setRemoteAuth } = await import('./api.js')
  const fetch = vi.fn(async () => new Response('{"ok":true}'))
  vi.stubGlobal('fetch', fetch)
  const sent = vi.fn(() => true)
  vi.stubGlobal('navigator', { userAgent: navigator.userAgent, sendBeacon: sent })

  await api('/api/data?rev=2')
  expect(fetch.mock.calls.at(-1)[0]).toBe('/gym' + expected + '/data?rev=2')
  beacon('/api/activity', { active: false })
  expect(sent.mock.calls.at(-1)[0]).toBe('/gym' + expected + '/activity')
  await apiBlob('/api/media/hash', { fetchImpl: fetch })
  expect(fetch.mock.calls.at(-1)[0]).toBe('/gym' + expected + '/media/hash')

  const opened = vi.fn()
  class Upload {
    open = opened
    setRequestHeader() {}
    send() {
      this.status = 200
      this.responseText = '{"ok":true}'
      this.onload()
    }
  }
  await apiUpload('/api/media/hash', new Blob(['image']), 'image/png', { XHR: Upload })
  expect(opened).toHaveBeenCalledWith('PUT', '/gym' + expected + '/media/hash')

  setRemoteAuth('https://gym.example/gym', 'token')
  await api('/api/me')
  expect(fetch.mock.calls.at(-1)[0]).toBe('https://gym.example/gym' + expected + '/me')
  expect(fetch.mock.calls.at(-1)[1].headers.Authorization).toBe('Bearer token')
  fetch.mockResolvedValueOnce(new Response('{"token":"paired","user":{"id":"A"}}'))
  await pairRedeem('https://gym.example/gym', '123456')
  expect(fetch.mock.calls.at(-1)[0]).toBe('https://gym.example/gym' + expected + '/pair/redeem')
})

it('uses v1 for both health probes after an unreachable pairing', async () => {
  vi.stubEnv('VITE_API_PREFIX', '/api/v1')
  const { pairRedeem } = await import('./api.js')
  const fetch = vi.fn()
    .mockRejectedValueOnce(new TypeError('network'))
    .mockResolvedValueOnce(new Response(''))
  vi.stubGlobal('fetch', fetch)
  nativeFetch.mockResolvedValueOnce(new Response('{"ok":true}'))
  await expect(pairRedeem('https://gym.example/gym', '123456')).rejects.toMatchObject({ code: 'cors' })
  expect(fetch.mock.calls.map(([url]) => url)).toEqual([
    'https://gym.example/gym/api/v1/pair/redeem',
    'https://gym.example/gym/api/v1/health'
  ])
  expect(nativeFetch.mock.calls.at(-1)[0]).toBe('https://gym.example/gym/api/v1/health')
})
