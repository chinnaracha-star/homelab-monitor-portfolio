import { describe, expect, it } from 'vitest'
import { dashboardHealthStatus, estimatedFullLabel, metricStatus } from './healthStatus'

describe('dashboard health and capacity labels', () => {
  it('maps alert severity to dashboard health', () => {
    expect(dashboardHealthStatus(['critical'], 99)).toBe('Critical')
    expect(dashboardHealthStatus(['warning'], 99)).toBe('Warning')
    expect(dashboardHealthStatus([], 94)).toBe('Excellent')
    expect(dashboardHealthStatus(['info'], 70)).toBe('Good')
  })

  it('maps metric bands to Normal Warning Critical', () => {
    expect(metricStatus('cpu', 15)).toBe('Normal')
    expect(metricStatus('cpu', 70)).toBe('Warning')
    expect(metricStatus('cpu', 91)).toBe('Critical')
    expect(metricStatus('memory', 42)).toBe('Normal')
    expect(metricStatus('memory', 80)).toBe('Warning')
    expect(metricStatus('temperature', 46)).toBe('Normal')
    expect(metricStatus('temperature', 76)).toBe('Critical')
    expect(metricStatus('storage', 78)).toBe('Normal')
    expect(metricStatus('storage', 85)).toBe('Warning')
  })

  it('formats estimated full without dividing by zero', () => {
    expect(estimatedFullLabel(138, 10)).toBe('138 Days')
    expect(estimatedFullLabel(5.25, 800)).toBe('5 Days')
    expect(estimatedFullLabel(10, 0)).toBe('Unknown')
    expect(estimatedFullLabel(null, 100)).toBe('Unknown')
  })
})
