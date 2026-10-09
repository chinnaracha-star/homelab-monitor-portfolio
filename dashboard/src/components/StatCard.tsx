import { memo, type ReactNode } from 'react'
import type { IconName } from './Icon'
import { Icon } from './Icon'
import styles from './Components.module.css'

export const StatCard = memo(function StatCard({
  label,
  value,
  valueLabel,
  tone,
  icon,
  meta,
  status,
  statusKind,
  extras,
}: {
  label: string
  value: number | string | ReactNode
  valueLabel?: string
  tone?: string
  icon?: IconName
  meta?: string
  status?: string
  statusKind?: string
  extras?: { label: string; value: string }[]
}) {
  const isPlain = typeof value === 'number' || typeof value === 'string'
  const display = typeof value === 'number' ? value.toLocaleString() : value
  const ariaValue = valueLabel ?? (isPlain ? String(display) : '')
  const extraLabels = (extras ?? []).map((item) => `${item.label} ${item.value}`)
  const parts = [ariaValue, meta, status ? `Status: ${status}` : '', ...extraLabels]
  const ariaLabel = [label, ...parts.filter(Boolean)].join(' ')

  return (
    <article
      className={styles.statCard}
      data-status={statusKind}
      data-tone={tone}
      aria-label={ariaLabel}
    >
      <p className={styles.statLabel}>
        {icon ? <Icon name={icon} /> : null}
        {label}
      </p>
      <p className={`${styles.statValue} ${isPlain ? '' : styles.statValueRich}`.trim()}>
        <span className={styles.valuePulse} key={isPlain ? String(display) : valueLabel ?? label}>
          {display}
        </span>
      </p>
      {meta ? <p className={styles.statMeta}>{meta}</p> : null}
      {status ? (
        <p className={styles.statStatus}>
          Status:
          <span>{status}</span>
        </p>
      ) : null}
      {extras?.length ? (
        <ul className={styles.statExtras}>
          {extras.map((item) => (
            <li key={item.label}>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </li>
          ))}
        </ul>
      ) : null}
    </article>
  )
})
