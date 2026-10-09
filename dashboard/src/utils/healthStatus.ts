export type DashboardHealthStatus = 'Excellent' | 'Good' | 'Warning' | 'Critical'
export type MetricStatus = 'Normal' | 'Warning' | 'Critical'

export function metricStatus(
  kind: 'cpu' | 'memory' | 'temperature' | 'storage',
  value: number | null | undefined,
): MetricStatus {
  if (value == null || !Number.isFinite(value)) {
    return 'Normal'
  }
  if (kind === 'cpu') {
    if (value > 90) {
      return 'Critical'
    }
    if (value >= 70) {
      return 'Warning'
    }
    return 'Normal'
  }
  if (kind === 'temperature') {
    if (value > 75) {
      return 'Critical'
    }
    if (value >= 60) {
      return 'Warning'
    }
    return 'Normal'
  }
  if (value > 90) {
    return 'Critical'
  }
  if (value >= 80) {
    return 'Warning'
  }
  return 'Normal'
}

export function dashboardHealthStatus(
  severities: string[],
  score: number | null | undefined,
): DashboardHealthStatus {
  const ranks = new Set(severities.map((item) => item.toLowerCase()))
  if (ranks.has('critical')) {
    return 'Critical'
  }
  if (ranks.has('warning')) {
    return 'Warning'
  }
  if (typeof score === 'number' && score >= 90) {
    return 'Excellent'
  }
  return 'Good'
}

export function estimatedFullLabel(days: number | null | undefined, growthPerDay: number): string {
  if (days == null || growthPerDay <= 0) {
    return 'Unknown'
  }
  return `${Math.round(days)} Days`
}
