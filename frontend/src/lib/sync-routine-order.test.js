/* RC review 2026-10-07: the order of the routines was not stamped. A reorder on one device was lost
   to the other device's copy whenever that one was newer as a whole (a weigh-in logged later), so
   the list jumped back. The order is now a choice of its own (`edited.routineOrder`), merged like
   a setting; a routine only one copy has still goes next to its neighbour there. The server stamps
   it for a writer that does not (api/sync-stamps.js), and keeps a newer order from an older copy. */
import { describe, expect, it } from 'vitest'
import { mergeStates, orderMoved, stampChange } from './sync-merge.js'

const clone = v => JSON.parse(JSON.stringify(v))
const T = 1_800_000_000_000
const r = id => ({ id, name: id, ex: [], _ts: T - 1000 })
const ids = s => s.routines.map(x => x.id).join(',')
const change = (prev, fn, wall) => { const n = clone(prev); fn(n); n._ts = stampChange(prev, n, wall); return n }
const base = () => ({ _ts: T, unit: 'kg', workouts: [], routines: [r('a'), r('b'), r('c')], edited: { restSec: T } })
const reorder = order => s => { s.routines = order.map(id => s.routines.find(x => x.id === id)) }

describe('the order of the routines', () => {
  it('a reorder survives the other device\'s later, unrelated change, in either merge order', () => {
    const A = change(base(), reorder(['c', 'a', 'b']), T + 1000)
    const B = change(base(), s => { s.restSec = 45 }, T + 5000)
    for (const m of [mergeStates(A, B), mergeStates(B, A)]) {
      expect(ids(m)).toBe('c,a,b')
      expect(m.restSec).toBe(45)
    }
  })
  it('the order chosen last wins', () => {
    const A = change(base(), reorder(['c', 'a', 'b']), T + 1000)
    const B = change(base(), reorder(['b', 'a', 'c']), T + 2000)
    for (const m of [mergeStates(A, B), mergeStates(B, A)]) expect(ids(m)).toBe('b,a,c')
  })
  it('a routine only the other copy has goes next to its neighbour there, and both edits of an entry are kept', () => {
    const A = change(base(), reorder(['c', 'a', 'b']), T + 1000)
    const B = change(base(), s => { s.routines.splice(1, 0, { id: 'n', name: 'New', ex: [] }); s.routines[0].name = 'A2' }, T + 5000)
    for (const m of [mergeStates(A, B), mergeStates(B, A)]) {
      expect(ids(m)).toBe('c,a,n,b')
      expect(m.routines.find(x => x.id === 'a').name).toBe('A2')
    }
  })
  it('adding or removing a routine is no reorder', () => {
    expect(orderMoved([r('a'), r('b')], [r('a'), r('x'), r('b')])).toBe(false)
    expect(orderMoved([r('a'), r('b'), r('c')], [r('a'), r('c')])).toBe(false)
    expect(orderMoved([r('a'), r('b')], [r('b'), r('a')])).toBe(true)
    expect(change(base(), s => { s.routines.push(r('d')) }, T + 1).edited.routineOrder).toBeUndefined()
    expect(orderMoved([r('a'), r('b')], [r('b'), r('a'), r('z')])).toBe(true)
  })
})

