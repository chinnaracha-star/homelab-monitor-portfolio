import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactElement } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { PwaInstallButton } from './PwaInstallButton'
import { PwaUpdateBanner } from './PwaUpdateBanner'
import { OfflineBanner } from './OfflineBanner'
import { PwaSettingsCard } from './PwaSettingsCard'
import { PwaContext, PwaProvider, type PwaContextValue } from '../pwa/PwaProvider'

function pwaValue(overrides: Partial<PwaContextValue> = {}): PwaContextValue {
  return {
    installed: false,
    canInstall: false,
    serviceWorker: 'missing',
    cacheReady: false,
    version: '0.1.0',
    updateAvailable: false,
    offline: false,
    install: vi.fn(),
    checkForUpdate: vi.fn(),
    applyUpdate: vi.fn(),
    dismissUpdate: vi.fn(),
    clearCache: vi.fn(),
    ...overrides,
  }
}

function renderPwa(ui: ReactElement, value: PwaContextValue) {
  return render(<PwaContext.Provider value={value}>{ui}</PwaContext.Provider>)
}

describe('PWA install, update, and offline chrome', () => {
  it('shows the install prompt and hides it after installation', async () => {
    const user = userEvent.setup()
    const install = vi.fn()
    const { rerender } = renderPwa(<PwaInstallButton />, pwaValue({ canInstall: true, install }))
    await user.click(screen.getByRole('button', { name: 'Install HomeLab Monitor' }))
    expect(install).toHaveBeenCalled()
    rerender(
      <PwaContext.Provider value={pwaValue({ installed: true, canInstall: true })}>
        <PwaInstallButton />
      </PwaContext.Provider>,
    )
    expect(screen.queryByRole('button', { name: 'Install HomeLab Monitor' })).not.toBeInTheDocument()
  })

  it('shows an update prompt that can reload or dismiss', async () => {
    const user = userEvent.setup()
    const applyUpdate = vi.fn()
    const dismissUpdate = vi.fn()
    renderPwa(<PwaUpdateBanner />, pwaValue({ updateAvailable: true, applyUpdate, dismissUpdate }))
    expect(screen.getByText('Update Available')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Reload' }))
    await user.click(screen.getByRole('button', { name: 'Dismiss' }))
    expect(applyUpdate).toHaveBeenCalled()
    expect(dismissUpdate).toHaveBeenCalled()
  })

  it('shows the offline banner with last updated and cached data', () => {
    renderPwa(
      <OfflineBanner cached lastUpdated={new Date('2026-09-08T10:00:00Z')} />,
      pwaValue({ offline: true }),
    )
    expect(screen.getByLabelText('Offline status')).toBeInTheDocument()
    expect(screen.getByText('Offline')).toBeInTheDocument()
    expect(screen.getByText('Last Updated')).toBeInTheDocument()
    expect(screen.getByText('Cached Data')).toBeInTheDocument()
  })

  it('renders the Settings application card and PWA actions', async () => {
    const user = userEvent.setup()
    const checkForUpdate = vi.fn()
    const clearCache = vi.fn()
    const install = vi.fn()
    renderPwa(
      <PwaSettingsCard />,
      pwaValue({
        canInstall: true,
        serviceWorker: 'registered',
        cacheReady: true,
        checkForUpdate,
        clearCache,
        install,
      }),
    )
    expect(screen.getByRole('heading', { name: 'Application' })).toBeInTheDocument()
    expect(screen.getByLabelText('Installed No')).toBeInTheDocument()
    expect(screen.getByLabelText('Service Worker Registered')).toBeInTheDocument()
    expect(screen.getByLabelText('Cache Status Ready')).toBeInTheDocument()
    expect(screen.getByLabelText('Version 0.1.0')).toBeInTheDocument()
    expect(screen.getByLabelText('Update Available No')).toBeInTheDocument()
    expect(screen.getByLabelText('Application status').className).toMatch(/remoteAccessGrid/)
    await user.click(screen.getByRole('button', { name: 'Install' }))
    await user.click(screen.getByRole('button', { name: 'Check for Update' }))
    await user.click(screen.getByRole('button', { name: 'Clear Cache' }))
    expect(install).toHaveBeenCalled()
    expect(checkForUpdate).toHaveBeenCalled()
    expect(clearCache).toHaveBeenCalled()
  })

  it('hides Settings install when the app is already installed', () => {
    renderPwa(<PwaSettingsCard />, pwaValue({ installed: true }))
    expect(screen.getByLabelText('Installed Yes')).toBeInTheDocument()
    expect(screen.getByLabelText('Display Installed')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Install' })).not.toBeInTheDocument()
  })
})

describe('PWA app mode', () => {
  it('marks the document as standalone when display-mode matches', async () => {
    window.matchMedia = ((query: string) => ({
      matches: query.includes('standalone'),
      media: query,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => false,
    })) as typeof window.matchMedia
    render(
      <PwaProvider>
        <p>shell</p>
      </PwaProvider>,
    )
    expect(document.documentElement.classList.contains('pwa-standalone')).toBe(true)
    expect(document.documentElement.dataset.appMode).toBe('standalone')
  })
})
