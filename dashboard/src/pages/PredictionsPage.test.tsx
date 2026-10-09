import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { PredictionMetric, PredictionOverview } from '../types/dashboard'
import { PredictionsPage } from './PredictionsPage'

vi.mock('recharts', async () => {
  const actual = await vi.importActual<typeof import('recharts')>('recharts')
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: unknown }) => (
      <div data-testid="chart-surface">{children as never}</div>
    ),
  }
})

vi.mock('../api/dashboard', () => ({
  getPredictionsOverview: vi.fn(),
  getPredictionsStorage: vi.fn(),
  getPredictionsSystem: vi.fn(),
  getPredictionsPhotos: vi.fn(),
  getPredictionsBackup: vi.fn(),
}))

import {
  getPredictionsBackup,
  getPredictionsOverview,
  getPredictionsPhotos,
  getPredictionsStorage,
  getPredictionsSystem,
} from '../api/dashboard'

const metric: PredictionMetric = {
  risk: 'warning',
  summary: 'Will reach 90% estimated in 42 days.',
  recommendation: 'Plan additional storage capacity.',
  forecasts: [{ horizon_days: 30, summary: 'Will reach 90% estimated in 42 days.', value: 42, unit: 'days' }],
  series: [{ timestamp: null, label: 'Today', value: 10 }],
}

const overview: PredictionOverview = {
  overall_risk: 'warning',
  storage: metric,
  system: { ...metric, summary: 'CPU trend is rising. Memory is stable.' },
  photos: metric,
  backup: metric,
  recommendations: ['Plan additional storage capacity.'],
  summary: metric.summary,
}

describe('Predictive Alerting page', () => {
  beforeEach(() => {
    vi.mocked(getPredictionsOverview).mockResolvedValue(overview)
    vi.mocked(getPredictionsStorage).mockResolvedValue(metric)
    vi.mocked(getPredictionsSystem).mockResolvedValue(metric)
    vi.mocked(getPredictionsPhotos).mockResolvedValue(metric)
    vi.mocked(getPredictionsBackup).mockResolvedValue(metric)
  })

  it('renders forecast cards, recommendations, and charts', async () => {
    render(<PredictionsPage />)
    expect(await screen.findByRole('heading', { name: 'Predictive Alerting' })).toBeInTheDocument()
    expect(screen.getByLabelText('Overall Risk warning')).toBeInTheDocument()
    expect(screen.getByRole('list', { name: 'Recommendations' })).toBeInTheDocument()
    expect(screen.getByLabelText('Forecast charts')).toBeInTheDocument()
    expect(screen.getAllByTestId('chart-surface').length).toBeGreaterThan(0)
  })

  it('shows empty recommendations and a responsive chart grid', async () => {
    vi.mocked(getPredictionsOverview).mockResolvedValue({ ...overview, recommendations: [] })
    render(<PredictionsPage />)
    expect(await screen.findByText('No predictions yet.')).toBeInTheDocument()
    expect((await screen.findByLabelText('Forecast charts')).className).toMatch(/chartGrid/)
  })

  it('retries after an error', async () => {
    vi.mocked(getPredictionsOverview).mockRejectedValue(new Error('failed'))
    render(<PredictionsPage />)
    expect(await screen.findByText('Predictions failed')).toBeInTheDocument()
    vi.mocked(getPredictionsOverview).mockResolvedValue(overview)
    await userEvent.click(screen.getByRole('button', { name: 'Retry section' }))
    await waitFor(() => {
      expect(screen.getByLabelText('Forecast cards')).toBeInTheDocument()
    })
  })
})
