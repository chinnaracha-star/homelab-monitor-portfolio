import { useEffect, useRef } from 'react'
import { inspectPublicUrl, type TelegramPublicUrls } from './publicUrl'
import userStyles from '../pages/UsersPage.module.css'
import styles from '../pages/SettingsPage.module.css'

const FIELDS: Array<{
  key: keyof TelegramPublicUrls
  id: string
  title: string
  emoji: string
}> = [
  { key: 'dashboard', id: 'dashboard-public-url', title: 'Dashboard Public URL', emoji: '🏠' },
  { key: 'immich', id: 'immich-public-url', title: 'Immich Public URL', emoji: '📷' },
  { key: 'qnap', id: 'qnap-public-url', title: 'QNAP Public URL', emoji: '💾' },
]

export interface TelegramTestSummary {
  delivery: 'successful' | 'failed'
  buttons: Record<keyof TelegramPublicUrls, ReturnType<typeof inspectPublicUrl>>
}

export function TelegramPublicUrlPanel({
  urls,
  onChange,
  saveWarnings,
  testSummary,
  log,
  onLog,
}: {
  urls: TelegramPublicUrls
  onChange: (key: keyof TelegramPublicUrls, value: string) => void
  saveWarnings: string[]
  testSummary: TelegramTestSummary | null
  log: string[]
  onLog: (entry: string) => void
}) {
  const previous = useRef<Record<string, string>>({})

  useEffect(() => {
    for (const field of FIELDS) {
      const check = inspectPublicUrl(urls[field.key])
      const signature = `${check.status}:${check.logReason ?? ''}`
      if (previous.current[field.key] === signature) {
        continue
      }
      previous.current[field.key] = signature
      let entry = `${field.title} validated status=${check.status}`
      if (check.status === 'valid') {
        console.info(`${field.title} validated status=valid`)
      } else if (check.status === 'invalid') {
        entry = `${field.title} validated status=invalid reason=${check.logReason}`
        console.info(entry)
      } else {
        console.info(`${field.title} validated status=empty`)
      }
      onLog(entry)
    }
  }, [onLog, urls])

  return (
    <section className={styles.reportsSection} aria-labelledby="telegram-public-urls-title">
      <h3 className={styles.channelTitle} id="telegram-public-urls-title">
        Public URLs
      </h3>
      <p className={styles.channelHint}>
        Health URLs stay inside Docker. Public URLs are the only values Telegram buttons may use.
        Empty fields omit that button. Invalid values never block Save.
      </p>
      {FIELDS.map((field) => {
        const check = inspectPublicUrl(urls[field.key])
        const statusText =
          check.status === 'valid' ? 'Valid' : check.status === 'empty' ? 'Empty' : 'Invalid'
        const mark = check.status === 'valid' ? '🟢' : check.status === 'empty' ? '🟡' : '🔴'
        return (
          <label className={userStyles.label} htmlFor={field.id} key={field.key}>
            {field.title}
            <input
              className={userStyles.input}
              id={field.id}
              name={field.id}
              value={urls[field.key]}
              placeholder="https://"
              autoComplete="off"
              aria-label={field.title}
              onChange={(event) => onChange(field.key, event.target.value)}
            />
            <span
              className={
                check.status === 'valid'
                  ? styles.statusValid
                  : check.status === 'empty'
                    ? styles.statusEmpty
                    : styles.statusInvalid
              }
              data-status={check.status}
            >
              {mark} {statusText}
            </span>
            {check.explanation ? <span className={styles.channelHint}>{check.explanation}</span> : null}
          </label>
        )
      })}

      <section className={styles.previewCard} aria-labelledby="telegram-buttons-preview-title">
        <h4 className={styles.channelTitle} id="telegram-buttons-preview-title">
          Telegram Buttons Preview
        </h4>
        <ul className={styles.previewList}>
          {FIELDS.map((field) => {
            const check = inspectPublicUrl(urls[field.key])
            const enabled = check.status === 'valid'
            return (
              <li key={field.key} data-preview={field.key} data-enabled={enabled ? 'yes' : 'no'}>
                {enabled
                  ? `${field.emoji} ${field.title.replace(' Public URL', '')} ✅`
                  : `${field.title.replace(' Public URL', '')} ❌`}
              </li>
            )
          })}
        </ul>
      </section>

      {saveWarnings.length > 0 ? (
        <ul className={styles.saveWarning} aria-label="Public URL save warnings">
          {saveWarnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}

      {log.length > 0 ? (
        <section aria-labelledby="public-url-log-title">
          <h4 className={styles.channelTitle} id="public-url-log-title">
            Validation log
          </h4>
          <ol className={styles.validationLog}>
            {log.map((entry, index) => (
              <li key={`${entry}-${index}`}>{entry}</li>
            ))}
          </ol>
        </section>
      ) : null}

      {testSummary ? (
        <section className={styles.previewCard} aria-labelledby="telegram-test-summary-title">
          <h4 className={styles.channelTitle} id="telegram-test-summary-title">
            Telegram Test
          </h4>
          <ul className={styles.previewList}>
            {FIELDS.map((field) => {
              const check = testSummary.buttons[field.key]
              const enabled = check.status === 'valid'
              return (
                <li key={field.key}>
                  {field.title.replace(' Public URL', '')} button {enabled ? '✅ Enabled' : '❌ Disabled'}
                  {!enabled && check.explanation ? (
                    <span className={styles.channelHint}> Reason {check.explanation}</span>
                  ) : null}
                </li>
              )
            })}
            <li>
              Message delivery {testSummary.delivery === 'successful' ? '✅ Successful' : '❌ Failed'}
            </li>
          </ul>
        </section>
      ) : null}
    </section>
  )
}
