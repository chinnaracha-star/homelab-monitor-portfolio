import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../auth/AuthContext'
import type { PhotoServicesSummary } from '../types/dashboard'
import { PhotoServicesPage } from './PhotoServicesPage'

vi.mock('../api/dashboard', () => ({
  getPhotoServices: vi.fn(),
}))

import { getPhotoServices } from '../api/dashboard'

const mockedGet = vi.mocked(getPhotoServices)

const payload: PhotoServicesSummary = {
  collected_at: '2026-09-08T01:00:00Z',
  read_only: true,
  services: [
    {
      service: 'immich',
      status: 'healthy',
      version: '1.118.0',
      updated_at: '2026-09-08T01:00:00Z',
      summary: { health: 'ok', indexed_photos: 18420 },
    },
    {
      service: 'qumagie',
      status: 'healthy',
      version: '2.6.0',
      updated_at: '2026-09-08T01:00:00Z',
      summary: { health: 'ok', indexed_photos: 17602 },
    },
    {
      service: 'qnap',
      status: 'healthy',
      version: '5.2.1',
      updated_at: '2026-09-08T01:00:00Z',
      summary: {
        capacity_bytes: 12_000_000_000_000,
        used_bytes: 4_980_000_000_000,
        free_bytes: 7_020_000_000_000,
        storage_percent: 41.5,
        storage_health: 'healthy',
      },
    },
  ],
  stats: {
    indexed_photos: 18420,
    indexed_videos: 412,
    albums: 28,
    users: 3,
    storage_used: 4_980_000_000_000,
    storage_free: 7_020_000_000_000,
    storage_percent: 41.5,
    thumbnail_queue: 3,
    face_queue: 1,
    last_scan: '2026-09-08T00:40:00+00:00',
    capacity_bytes: 12_000_000_000_000,
    storage_health: 'healthy',
    storage_percent_metric: 41.5,
    thumbnail_queue_metric: 3,
    face_queue_metric: 1,
    immich_health: 1,
    qumagie_health: 1,
    storage_history: {
      today: 4_980_000_000_000,
      yesterday: 4_850_000_000_000,
      last_week: 4_420_000_000_000,
    },
    photo_growth: {
      today: 250,
      yesterday: 180,
      this_week: 1200,
    },
  },
}

function renderPage() {
  return render(
    <AuthContext.Provider
      value={{
        user: {
          id: 'user-admin',
          username: 'admin',
          full_name: 'Administrator',
          role: 'admin',
          is_active: true,
        },
        loading: false,
        login: async () => undefined,
        logout: () => undefined,
      }}
    >
      <PhotoServicesPage />
    </AuthContext.Provider>,
  )
}

describe('Photo Services page', () => {
  beforeEach(() => {
    mockedGet.mockReset()
    mockedGet.mockResolvedValue(payload)
  })

  it('renders Immich, QuMagie, and QNAP Storage cards', async () => {
    const { container } = renderPage()
    expect(await screen.findByRole('heading', { name: 'Photo Services' })).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'Immich card' })).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'QuMagie card' })).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'QNAP Storage card' })).toBeInTheDocument()
    expect(screen.getByText('Version 1.118.0')).toBeInTheDocument()
    expect(screen.getByLabelText('Storage Healthy')).toBeInTheDocument()
    expect(screen.getByLabelText('Indexed Photos 18,420')).toBeInTheDocument()
    expect(screen.getByLabelText('Thumbnail Queue 3')).toBeInTheDocument()
    expect(screen.getByLabelText('Storage History')).toBeInTheDocument()
    expect(screen.getByLabelText('Photo Growth')).toBeInTheDocument()
    expect(screen.getByText('+250')).toBeInTheDocument()
    expect(screen.getByText('+180')).toBeInTheDocument()
    expect(screen.getByText('+1,200')).toBeInTheDocument()
    expect(screen.getByLabelText('Photo service cards')).toBeInTheDocument()
    expect(container.querySelector('#qnap-storage-usage')).toBeInTheDocument()
  })

  it('retries after an API failure', async () => {
    const user = userEvent.setup()
    mockedGet.mockRejectedValueOnce(new Error('offline'))
    mockedGet.mockResolvedValue(payload)
    renderPage()
    expect(await screen.findByText('Photo Services API failed')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry section' }))
    expect(await screen.findByRole('article', { name: 'Immich card' })).toBeInTheDocument()
  })

  it('shows a loading state before data arrives', async () => {
    mockedGet.mockReturnValue(new Promise(() => undefined))
    renderPage()
    expect(await screen.findByLabelText('Loading overview')).toBeInTheDocument()
  })

  it('shows an empty state when no services report', async () => {
    mockedGet.mockResolvedValue({
      collected_at: '2026-09-08T01:00:00Z',
      read_only: true,
      services: [],
      stats: payload.stats,
    })
    renderPage()
    expect(await screen.findByText('No photo services reported a snapshot.')).toBeInTheDocument()
  })

  it('retries from a photo service card', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('article', { name: 'Immich card' })
    await user.click(screen.getAllByRole('button', { name: 'Retry' })[0])
    await waitFor(() => expect(mockedGet.mock.calls.length).toBeGreaterThan(1))
  })

  it('uses a responsive photo card grid', async () => {
    renderPage()
    const grid = await screen.findByLabelText('Photo service cards')
    expect(grid.className).toMatch(/connectorGrid/)
  })
})
