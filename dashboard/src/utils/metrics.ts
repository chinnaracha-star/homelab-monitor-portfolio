import type { LatestMetricReport, SystemMetrics, TemperatureMetrics } from '../types/dashboard'

export type MetricLevel = 'normal' | 'warning' | 'critical' | 'unknown'

export function getUsageLevel(value: number | undefined): MetricLevel {
  if (value === undefined || !Number.isFinite(value)) {
    return 'unknown'
  }
  if (value >= 85) {
    return 'critical'
  }
  if (value >= 60) {
    return 'warning'
  }
  return 'normal'
}

export function getTemperatureLevel(value: number | undefined): MetricLevel {
  if (value === undefined || !Number.isFinite(value)) {
    return 'unknown'
  }
  if (value > 80) {
    return 'critical'
  }
  if (value >= 60) {
    return 'warning'
  }
  return 'normal'
}

export function getSystemMetrics(report: LatestMetricReport | undefined): SystemMetrics | null {
  const systemModule = report?.payload.modules.find((module) => module.module === 'system')
  return systemModule ? (systemModule.metrics as SystemMetrics) : null
}

export function getHighestTemperature(
  temperatures: TemperatureMetrics[] | undefined,
): TemperatureMetrics | undefined {
  return temperatures?.reduce<TemperatureMetrics | undefined>(
    (highest, sensor) =>
      !highest || sensor.current_celsius > highest.current_celsius ? sensor : highest,
    undefined,
  )
}

export const alertLabels: Record<string, string> = {
  agent_offline: 'Agent Offline',
  cpu_high: 'CPU High',
  memory_high: 'Memory High',
  disk_high: 'Disk High',
  temperature_high: 'Temperature High',
}
