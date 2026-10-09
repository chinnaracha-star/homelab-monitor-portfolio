import type { QnapDiskRecord } from '../types/dashboard'
import styles from '../pages/InfrastructurePage.module.css'

const TEMP_LABEL: Record<string, string> = {
  normal: 'Normal',
  warning: 'Warning',
  critical: 'Critical',
  unknown: 'Unknown',
}

function celsiusLabel(value: string | number | boolean | null | QnapDiskRecord[] | undefined): string {
  if (value === null || value === undefined || value === '') {
    return 'Unknown'
  }
  return `${value}°C`
}

export function QnapDiskHealth({
  summary,
}: {
  summary: Record<string, string | number | boolean | null | QnapDiskRecord[]>
}) {
  const online = summary.online !== false && summary.online !== 'false'
  const systemTemp = summary.sys_tempc ?? summary.temperature_celsius
  const cpuTemp = summary.cpu_tempc
  const storage = summary.storage_percent ?? summary.storage_used_percent
  const disks = Array.isArray(summary.disks) ? summary.disks : null
  const model = typeof summary.model === 'string' && summary.model ? summary.model : 'QNAP'
  const warning = summary.disk_temp_warning_c
  const critical = summary.disk_temp_critical_c

  return (
    <section className={styles.diskHealth} aria-label="QNAP disk health">
      <p className={styles.meta}>
        {model} · {online ? 'Online' : 'Offline'}
      </p>
      <dl className={styles.summaryList}>
        <div>
          <dt>Storage</dt>
          <dd>
            {storage === null || storage === undefined || storage === '' ? 'Unavailable' : `${storage}%`}
          </dd>
        </div>
        <div>
          <dt>System Temp</dt>
          <dd>{celsiusLabel(systemTemp)}</dd>
        </div>
        {cpuTemp !== null && cpuTemp !== undefined ? (
          <div>
            <dt>CPU Temp</dt>
            <dd>{celsiusLabel(cpuTemp)}</dd>
          </div>
        ) : null}
      </dl>
      <h3 className={styles.diskHeading}>Disk Health</h3>
      {!online || disks === null || disks.length === 0 ? (
        <p className={styles.meta}>Disk Temperature: unavailable</p>
      ) : (
        <ul className={styles.diskList}>
          {disks.map((disk) => {
            const tempStatus = disk.temperature_status || 'unknown'
            const kind = disk.is_ssd ? 'SSD' : 'HDD'
            return (
              <li key={disk.bay ?? tempStatus} className={styles.diskItem}>
                <p className={styles.diskName}>
                  {kind} {disk.bay ?? '?'}
                </p>
                {disk.alias ? <p className={styles.meta}>{disk.alias}</p> : null}
                <p className={styles.diskTemp} data-temperature={tempStatus}>
                  {disk.temperature_celsius === null || disk.temperature_celsius === undefined
                    ? 'Temperature: Unknown'
                    : `${disk.temperature_celsius}°C`}
                </p>
                <p className={styles.meta}>{TEMP_LABEL[tempStatus] ?? 'Unknown'}</p>
              </li>
            )
          })}
        </ul>
      )}
      <p className={styles.meta}>SMART: Unavailable</p>
      {typeof warning === 'number' && typeof critical === 'number' ? (
        <p className={styles.meta}>
          Threshold: Warning {warning}°C / Critical {critical}°C
        </p>
      ) : null}
    </section>
  )
}
