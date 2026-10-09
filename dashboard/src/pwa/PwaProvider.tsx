import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { registerSW } from 'virtual:pwa-register'
import { AuthContext } from '../auth/AuthContext'
import { APP_VERSION } from './manifest'

export interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

export interface PwaStatus {
  installed: boolean
  canInstall: boolean
  serviceWorker: 'registered' | 'missing'
  cacheReady: boolean
  version: string
  updateAvailable: boolean
  offline: boolean
}

export interface PwaContextValue extends PwaStatus {
  install: () => Promise<void>
  checkForUpdate: () => Promise<void>
  applyUpdate: () => Promise<void>
  dismissUpdate: () => void
  clearCache: () => Promise<void>
}

export const PwaContext = createContext<PwaContextValue | undefined>(undefined)

function readStandalone(): boolean {
  const media = window.matchMedia?.('(display-mode: standalone)')
  const ios = 'standalone' in navigator && Boolean((navigator as Navigator & { standalone?: boolean }).standalone)
  return Boolean(media?.matches) || ios
}

async function readCacheReady(): Promise<boolean> {
  if (!('caches' in window)) {
    return false
  }
  const keys = await caches.keys()
  return keys.length > 0
}

async function unregisterServiceWorkers(): Promise<void> {
  if (!('serviceWorker' in navigator)) {
    return
  }
  const registrations = await navigator.serviceWorker.getRegistrations()
  await Promise.all(registrations.map((registration) => registration.unregister()))
}

export function PwaProvider({ children }: { children: ReactNode }) {
  const auth = useContext(AuthContext)
  const sessionReady = Boolean(auth?.user)
  const [installed, setInstalled] = useState(readStandalone)
  const [canInstall, setCanInstall] = useState(false)
  const [serviceWorker, setServiceWorker] = useState<'registered' | 'missing'>('missing')
  const [cacheReady, setCacheReady] = useState(false)
  const [updateAvailable, setUpdateAvailable] = useState(false)
  const [offline, setOffline] = useState(!navigator.onLine)
  const promptRef = useRef<BeforeInstallPromptEvent | null>(null)
  const applyUpdateRef = useRef<(reload?: boolean) => Promise<void>>(async () => undefined)

  const refreshRegistration = useCallback(async () => {
    if (!('serviceWorker' in navigator)) {
      setServiceWorker('missing')
      return undefined
    }
    const registration = await navigator.serviceWorker.getRegistration()
    setServiceWorker(registration ? 'registered' : 'missing')
    setCacheReady(await readCacheReady())
    return registration
  }, [])

  useEffect(() => {
    document.documentElement.classList.toggle('pwa-standalone', installed)
    document.documentElement.dataset.appMode = installed ? 'standalone' : 'browser'
  }, [installed])

  useEffect(() => {
    function handleOnline() {
      setOffline(false)
    }
    function handleOffline() {
      setOffline(true)
    }
    function handleInstalled() {
      setInstalled(true)
      setCanInstall(false)
      promptRef.current = null
    }
    function handlePrompt(event: Event) {
      event.preventDefault()
      promptRef.current = event as BeforeInstallPromptEvent
      setCanInstall(true)
    }
    function handleDisplayChange(event: MediaQueryListEvent) {
      if (event.matches) {
        setInstalled(true)
        setCanInstall(false)
      }
    }

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    window.addEventListener('beforeinstallprompt', handlePrompt)
    window.addEventListener('appinstalled', handleInstalled)
    const media = window.matchMedia?.('(display-mode: standalone)')
    media?.addEventListener?.('change', handleDisplayChange)
    void refreshRegistration()

    if (!sessionReady) {
      void unregisterServiceWorkers().then(() => {
        setServiceWorker('missing')
      })
      applyUpdateRef.current = async () => undefined
      return () => {
        window.removeEventListener('online', handleOnline)
        window.removeEventListener('offline', handleOffline)
        window.removeEventListener('beforeinstallprompt', handlePrompt)
        window.removeEventListener('appinstalled', handleInstalled)
        media?.removeEventListener?.('change', handleDisplayChange)
      }
    }

    const updateSW = registerSW({
      immediate: true,
      onNeedRefresh() {
        setUpdateAvailable(true)
      },
      onRegisteredSW(_url, registration) {
        setServiceWorker(registration ? 'registered' : 'missing')
        const syncManager = (registration as ServiceWorkerRegistration & { sync?: { register: (tag: string) => Promise<void> } })
          ?.sync
        void syncManager?.register('homelab-refresh')
        const periodic = (
          registration as ServiceWorkerRegistration & {
            periodicSync?: { register: (tag: string, options: { minInterval: number }) => Promise<void> }
          }
        )?.periodicSync
        void periodic?.register('homelab-health', { minInterval: 60 * 60 * 1000 })
      },
      onRegisterError() {
        setServiceWorker('missing')
      },
    })
    applyUpdateRef.current = updateSW

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
      window.removeEventListener('beforeinstallprompt', handlePrompt)
      window.removeEventListener('appinstalled', handleInstalled)
      media?.removeEventListener?.('change', handleDisplayChange)
    }
  }, [refreshRegistration, sessionReady])

  const install = useCallback(async () => {
    const prompt = promptRef.current
    if (!prompt) {
      return
    }
    await prompt.prompt()
    const choice = await prompt.userChoice
    if (choice.outcome === 'accepted') {
      setInstalled(true)
      setCanInstall(false)
      promptRef.current = null
    }
  }, [])

  const checkForUpdate = useCallback(async () => {
    const registration = await refreshRegistration()
    await registration?.update()
    if (registration?.waiting) {
      setUpdateAvailable(true)
    }
  }, [refreshRegistration])

  const applyUpdate = useCallback(async () => {
    await applyUpdateRef.current(true)
    setUpdateAvailable(false)
  }, [])

  const dismissUpdate = useCallback(() => {
    setUpdateAvailable(false)
  }, [])

  const clearCache = useCallback(async () => {
    if ('caches' in window) {
      const keys = await caches.keys()
      await Promise.all(keys.map((key) => caches.delete(key)))
    }
    setCacheReady(false)
    await refreshRegistration()
  }, [refreshRegistration])

  const value = useMemo<PwaContextValue>(
    () => ({
      installed,
      canInstall,
      serviceWorker,
      cacheReady,
      version: APP_VERSION,
      updateAvailable,
      offline,
      install,
      checkForUpdate,
      applyUpdate,
      dismissUpdate,
      clearCache,
    }),
    [
      applyUpdate,
      cacheReady,
      canInstall,
      checkForUpdate,
      clearCache,
      dismissUpdate,
      install,
      installed,
      offline,
      serviceWorker,
      updateAvailable,
    ],
  )

  return <PwaContext.Provider value={value}>{children}</PwaContext.Provider>
}

export function usePwa(): PwaContextValue {
  const value = useContext(PwaContext)
  if (!value) {
    throw new Error('usePwa must be used within PwaProvider')
  }
  return value
}

export function useOptionalPwa(): PwaContextValue | undefined {
  return useContext(PwaContext)
}
