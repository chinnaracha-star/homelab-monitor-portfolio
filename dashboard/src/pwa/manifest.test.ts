import { describe, expect, it } from 'vitest'
import { cacheStatusLabel, isStandaloneDisplay, pwaManifest, serviceWorkerLabel } from './manifest'

describe('PWA manifest', () => {
  it('declares standalone display, portrait orientation, and required icons', () => {
    expect(pwaManifest.name).toBe('HomeLab Monitor')
    expect(pwaManifest.short_name).toBe('HomeLab')
    expect(pwaManifest.display).toBe('standalone')
    expect(pwaManifest.orientation).toBe('portrait')
    expect(pwaManifest.scope).toBe('/')
    expect(pwaManifest.start_url).toBe('/')
    expect(pwaManifest.theme_color).toBe('#111827')
    expect(pwaManifest.background_color).toBe('#111827')
    const sizes = pwaManifest.icons.map((icon) => icon.sizes)
    expect(sizes).toContain('192x192')
    expect(sizes).toContain('512x512')
    expect(pwaManifest.shortcuts?.length).toBeGreaterThan(0)
    expect(pwaManifest.widgets?.[0]?.tag).toBe('homelab-status')
  })

  it('detects standalone app mode and service worker labels', () => {
    expect(isStandaloneDisplay({ matches: true })).toBe(true)
    expect(isStandaloneDisplay({ matches: false }, true)).toBe(true)
    expect(isStandaloneDisplay({ matches: false })).toBe(false)
    expect(serviceWorkerLabel(true)).toBe('Registered')
    expect(serviceWorkerLabel(false)).toBe('Missing')
    expect(cacheStatusLabel(true)).toBe('Ready')
    expect(cacheStatusLabel(false)).toBe('Empty')
  })
})
