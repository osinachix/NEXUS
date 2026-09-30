import '@testing-library/jest-dom/vitest'

// jsdom does not implement scrollIntoView (used by ExecutionTrace to
// auto-scroll to the newest step) -- a no-op stub is sufficient for tests,
// which assert on rendered content, not real scroll behavior.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}
