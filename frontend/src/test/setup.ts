import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach } from 'vitest'
import { cleanup } from '@testing-library/react'
import { installApiMock, resetApiMock } from './apiMock'

// Serve the fixture-backed API over a fetch stub for every test, with fresh
// state each time (the app's runtime client makes real fetch calls).
beforeEach(() => {
  resetApiMock()
  installApiMock()
})

// jsdom does not implement matchMedia; ThemeProvider and responsive code use it.
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList
}

afterEach(() => {
  cleanup()
})
