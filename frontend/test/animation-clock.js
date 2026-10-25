import { afterEach, beforeEach, vi } from 'vitest'

let animate
beforeEach(() => {
  // Gesture tests advance fake timers; happy-dom's animation timeline uses a separate clock.
  animate = vi.spyOn(Element.prototype, 'animate').mockImplementation((_frames, { duration }) => {
    const animation = { onfinish: null, cancel: () => clearTimeout(timer) }
    const timer = setTimeout(() => animation.onfinish?.(), duration)
    return animation
  })
})
afterEach(() => animate.mockRestore())
