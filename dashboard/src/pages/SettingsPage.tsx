import { useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  getNotificationSettings,
  getRemoteAccess,
  sendTelegramTestReport,
  sendTestNotification,
  updateNotificationSettings,
} from '../api/dashboard'
import { useCan } from '../auth/useCan'
import { SectionError } from '../components/SectionError'
import { OverviewSkeleton } from '../components/Skeleton'
import { RemoteAccessCard } from '../components/RemoteAccessCard'
import { PwaSettingsCard } from '../components/PwaSettingsCard'
import { PhotoMonitorSettingsCard } from '../components/PhotoMonitorSettingsCard'
import { TelegramPublicUrlPanel, type TelegramTestSummary } from '../settings/TelegramPublicUrlPanel'
import {
  inspectPublicUrl,
  loadStoredPublicUrls,
  persistPublicUrls,
  publicUrlSaveWarnings,
  type TelegramPublicUrls,
} from '../settings/publicUrl'
import { getErrorMessage } from '../utils/errors'
import { formatThaiDateTime } from '../utils/thaiDate'
import userStyles from './UsersPage.module.css'
import pageStyles from './Pages.module.css'
import styles from './SettingsPage.module.css'
import type {
  NotificationSettings,
  RemoteAccess,
  ScheduledReportCard,
  ScheduledReportsSettings,
} from '../types/dashboard'

const emptyReports: ScheduledReportsSettings = {
  hourly_enabled: false,
  daily_enabled: false,
  weekly_enabled: false,
  hour_interval: 1,
  daily_time: '08:00',
  weekly_day: 'sunday',
  weekly_time: '08:00',
  timezone: 'Asia/Bangkok',
  hourly: { enabled: false, last_sent: null, next_scheduled: null, status: 'disabled' },
  daily: { enabled: false, last_sent: null, next_scheduled: null, status: 'disabled' },
  weekly: { enabled: false, last_sent: null, next_scheduled: null, status: 'disabled' },
}

const emptySettings: NotificationSettings = {
  telegram: {
    enabled: false,
    configured: false,
    api_base_url: '',
    chat_id: '',
    bot_token_set: false,
    last_test: null,
  },
  discord: { enabled: false, configured: false, webhook_url_set: false },
  slack: { enabled: false, configured: false, webhook_url_set: false },
  email: {
    enabled: false,
    configured: false,
    host: '',
    port: 587,
    username: '',
    from_address: '',
    to_address: '',
    use_tls: true,
    password_set: false,
  },
  reports: emptyReports,
}

export function SettingsPage() {
  const canSend = useCan()('send_notifications')
  const canConfigure = useCan()('settings')
  const [settings, setSettings] = useState<NotificationSettings | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [telegramToken, setTelegramToken] = useState('')
  const [discordUrl, setDiscordUrl] = useState('')
  const [slackUrl, setSlackUrl] = useState('')
  const [emailPassword, setEmailPassword] = useState('')
  const [sendingReport, setSendingReport] = useState(false)
  const [remote, setRemote] = useState<RemoteAccess | null>(null)
  const [remoteError, setRemoteError] = useState<string | null>(null)
  const [publicUrls, setPublicUrls] = useState<TelegramPublicUrls>(loadStoredPublicUrls)
  const [urlLog, setUrlLog] = useState<string[]>([])
  const [saveWarnings, setSaveWarnings] = useState<string[]>([])
  const [testSummary, setTestSummary] = useState<TelegramTestSummary | null>(null)

  const appendUrlLog = useCallback((entry: string) => {
    setUrlLog((current) => [...current.slice(-7), entry])
  }, [])

  const loadSettings = useCallback(() => {
    setError(null)
    void getNotificationSettings()
      .then(setSettings)
      .catch((requestError: unknown) => setError(getErrorMessage(requestError)))
  }, [])

  const loadRemote = useCallback(() => {
    setRemoteError(null)
    void getRemoteAccess()
      .then(setRemote)
      .catch((requestError: unknown) => setRemoteError(getErrorMessage(requestError)))
  }, [])

  useEffect(() => {
    loadSettings()
    loadRemote()
  }, [loadSettings, loadRemote])

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!settings) {
      return
    }
    setError(null)
    try {
      const saved = await updateNotificationSettings({
        telegram: {
          enabled: settings.telegram.enabled,
          api_base_url: settings.telegram.api_base_url,
          chat_id: settings.telegram.chat_id,
          ...(telegramToken ? { bot_token: telegramToken } : {}),
        },
        discord: {
          enabled: settings.discord.enabled,
          ...(discordUrl ? { webhook_url: discordUrl } : {}),
        },
        slack: {
          enabled: settings.slack.enabled,
          ...(slackUrl ? { webhook_url: slackUrl } : {}),
        },
        email: {
          enabled: settings.email.enabled,
          host: settings.email.host,
          port: settings.email.port,
          username: settings.email.username,
          from_address: settings.email.from_address,
          to_address: settings.email.to_address,
          use_tls: settings.email.use_tls,
          ...(emailPassword ? { password: emailPassword } : {}),
        },
        reports: {
          hourly_enabled: settings.reports.hourly_enabled,
          daily_enabled: settings.reports.daily_enabled,
          weekly_enabled: settings.reports.weekly_enabled,
          hour_interval: settings.reports.hour_interval,
          daily_time: settings.reports.daily_time,
          weekly_day: settings.reports.weekly_day,
          weekly_time: settings.reports.weekly_time,
          timezone: settings.reports.timezone,
        },
      })
      setSettings(saved)
      setTelegramToken('')
      setDiscordUrl('')
      setSlackUrl('')
      setEmailPassword('')
      setToast('Notification settings saved.')
      const warnings = publicUrlSaveWarnings(publicUrls)
      setSaveWarnings(warnings)
      persistPublicUrls(publicUrls)
      if (warnings.length > 0) {
        setToast(`Notification settings saved. ${warnings[0]}`)
      }
    } catch (requestError) {
      setError(getErrorMessage(requestError))
    }
  }

  async function handleTest(channel: 'telegram' | 'discord' | 'slack' | 'email') {
    setError(null)
    try {
      await sendTestNotification(channel)
      setToast(channel === 'telegram' ? 'Telegram test message sent.' : `Test sent on ${channel}.`)
      if (channel === 'telegram') {
        const refreshed = await getNotificationSettings()
        setSettings(refreshed)
      }
    } catch (requestError) {
      setError(getErrorMessage(requestError))
    }
  }

  async function handleTestReport() {
    setError(null)
    setSendingReport(true)
    setToast('Sending...')
    const buttons = {
      dashboard: inspectPublicUrl(publicUrls.dashboard),
      immich: inspectPublicUrl(publicUrls.immich),
      qnap: inspectPublicUrl(publicUrls.qnap),
    }
    try {
      const result = await sendTelegramTestReport()
      const ok = result.status === 'sent'
      setToast(ok ? 'Telegram Test Report Sent' : 'Unable to deliver Telegram report.')
      setTestSummary({ delivery: ok ? 'successful' : 'failed', buttons })
    } catch {
      setToast('Unable to deliver Telegram report.')
      setTestSummary({ delivery: 'failed', buttons })
    } finally {
      setSendingReport(false)
    }
  }

  async function handleCopyUrl(url: string) {
    try {
      await navigator.clipboard.writeText(url)
      setToast('Remote dashboard URL copied.')
    } catch {
      setToast('Unable to copy remote dashboard URL.')
    }
  }

  function handleOpenUrl(url: string) {
    window.open(url, '_blank', 'noopener,noreferrer')
  }

  const current = settings ?? emptySettings

  return (
    <section className={pageStyles.page}>
      <header className={pageStyles.pageHeader}>
        <div>
          <p className={pageStyles.eyebrow}>Administration</p>
          <h1 className={pageStyles.title}>Settings</h1>
          <p className={pageStyles.description}>Configure notification channels. Secrets are never displayed.</p>
        </div>
      </header>
      {toast ? (
        <p className={userStyles.toast} role="status">
          {toast}
        </p>
      ) : null}
      {error ? <SectionError title={error} onRetry={loadSettings} /> : null}
      {!settings && !error ? <OverviewSkeleton /> : null}
      {settings ? (
        <form className={styles.channelGrid} onSubmit={(event) => void handleSave(event)}>
          <article className={styles.channelCard} aria-labelledby="telegram-settings">
            <h2 className={styles.channelTitle} id="telegram-settings">
              Telegram
            </h2>
            <p className={styles.channelHint}>
              {current.telegram.configured ? 'Configured' : 'Not configured'}
            </p>
            <p className={styles.channelHint}>
              Telegram buttons use Dashboard Public URL, Immich Public URL, and QNAP Public URL
              only. Docker health URLs are never sent to Telegram.
            </p>
            <p className={styles.channelHint}>
              Last test:{' '}
              {current.telegram.last_test
                ? formatThaiDateTime(current.telegram.last_test, false)
                : 'Never'}
            </p>
            <label className={userStyles.checkbox} htmlFor="telegram-enabled">
              <input
                id="telegram-enabled"
                type="checkbox"
                checked={current.telegram.enabled}
                onChange={(event) =>
                  setSettings({
                    ...current,
                    telegram: { ...current.telegram, enabled: event.target.checked },
                  })
                }
              />
              Enable Telegram
            </label>
            <label className={userStyles.label} htmlFor="telegram-url">
              API base URL
              <input
                className={userStyles.input}
                id="telegram-url"
                value={current.telegram.api_base_url}
                onChange={(event) =>
                  setSettings({
                    ...current,
                    telegram: { ...current.telegram, api_base_url: event.target.value },
                  })
                }
              />
            </label>
            <label className={userStyles.label} htmlFor="telegram-chat">
              Chat ID
              <input
                className={userStyles.input}
                id="telegram-chat"
                value={current.telegram.chat_id}
                onChange={(event) =>
                  setSettings({
                    ...current,
                    telegram: { ...current.telegram, chat_id: event.target.value },
                  })
                }
              />
            </label>
            <label className={userStyles.label} htmlFor="telegram-token">
              Bot token
              <input
                className={userStyles.input}
                id="telegram-token"
                type="password"
                autoComplete="off"
                value={telegramToken}
                placeholder={current.telegram.bot_token_set ? 'Stored token unchanged' : ''}
                onChange={(event) => setTelegramToken(event.target.value)}
              />
            </label>
            {canSend ? (
              <button className={userStyles.secondaryButton} type="button" onClick={() => void handleTest('telegram')}>
                Test Message
              </button>
            ) : null}
            <TelegramPublicUrlPanel
              urls={publicUrls}
              onChange={(key, value) => setPublicUrls((current) => ({ ...current, [key]: value }))}
              saveWarnings={saveWarnings}
              testSummary={testSummary}
              log={urlLog}
              onLog={appendUrlLog}
            />
          </article>

          <article className={styles.channelCard} aria-labelledby="discord-settings">
            <h2 className={styles.channelTitle} id="discord-settings">
              Discord
            </h2>
            <label className={userStyles.checkbox} htmlFor="discord-enabled">
              <input
                id="discord-enabled"
                type="checkbox"
                checked={current.discord.enabled}
                onChange={(event) =>
                  setSettings({
                    ...current,
                    discord: { ...current.discord, enabled: event.target.checked },
                  })
                }
              />
              Enable Discord
            </label>
            <label className={userStyles.label} htmlFor="discord-webhook">
              Discord webhook URL
              <input
                className={userStyles.input}
                id="discord-webhook"
                type="password"
                autoComplete="off"
                value={discordUrl}
                placeholder={current.discord.webhook_url_set ? 'Stored webhook unchanged' : 'https://'}
                onChange={(event) => setDiscordUrl(event.target.value)}
              />
            </label>
            {canSend ? (
              <button className={userStyles.secondaryButton} type="button" onClick={() => void handleTest('discord')}>
                Send Discord test
              </button>
            ) : null}
          </article>

          <article className={styles.channelCard} aria-labelledby="slack-settings">
            <h2 className={styles.channelTitle} id="slack-settings">
              Slack
            </h2>
            <label className={userStyles.checkbox} htmlFor="slack-enabled">
              <input
                id="slack-enabled"
                type="checkbox"
                checked={current.slack.enabled}
                onChange={(event) =>
                  setSettings({
                    ...current,
                    slack: { ...current.slack, enabled: event.target.checked },
                  })
                }
              />
              Enable Slack
            </label>
            <label className={userStyles.label} htmlFor="slack-webhook">
              Slack webhook URL
              <input
                className={userStyles.input}
                id="slack-webhook"
                type="password"
                autoComplete="off"
                value={slackUrl}
                placeholder={current.slack.webhook_url_set ? 'Stored webhook unchanged' : 'https://'}
                onChange={(event) => setSlackUrl(event.target.value)}
              />
            </label>
            {canSend ? (
              <button className={userStyles.secondaryButton} type="button" onClick={() => void handleTest('slack')}>
                Send Slack test
              </button>
            ) : null}
          </article>

          <article className={styles.channelCard} aria-labelledby="email-settings">
            <h2 className={styles.channelTitle} id="email-settings">
              Email
            </h2>
            <label className={userStyles.checkbox} htmlFor="email-enabled">
              <input
                id="email-enabled"
                type="checkbox"
                checked={current.email.enabled}
                onChange={(event) =>
                  setSettings({
                    ...current,
                    email: { ...current.email, enabled: event.target.checked },
                  })
                }
              />
              Enable email
            </label>
            <label className={userStyles.label} htmlFor="email-host">
              SMTP host
              <input
                className={userStyles.input}
                id="email-host"
                value={current.email.host}
                onChange={(event) =>
                  setSettings({ ...current, email: { ...current.email, host: event.target.value } })
                }
              />
            </label>
            <label className={userStyles.label} htmlFor="email-port">
              Port
              <input
                className={userStyles.input}
                id="email-port"
                type="number"
                value={current.email.port}
                onChange={(event) =>
                  setSettings({
                    ...current,
                    email: { ...current.email, port: Number(event.target.value) },
                  })
                }
              />
            </label>
            <label className={userStyles.label} htmlFor="email-username">
              Username
              <input
                className={userStyles.input}
                id="email-username"
                value={current.email.username}
                onChange={(event) =>
                  setSettings({
                    ...current,
                    email: { ...current.email, username: event.target.value },
                  })
                }
              />
            </label>
            <label className={userStyles.label} htmlFor="email-password">
              Password
              <input
                className={userStyles.input}
                id="email-password"
                type="password"
                autoComplete="off"
                value={emailPassword}
                placeholder={current.email.password_set ? 'Stored password unchanged' : ''}
                onChange={(event) => setEmailPassword(event.target.value)}
              />
            </label>
            <label className={userStyles.label} htmlFor="email-from">
              From address
              <input
                className={userStyles.input}
                id="email-from"
                value={current.email.from_address}
                onChange={(event) =>
                  setSettings({
                    ...current,
                    email: { ...current.email, from_address: event.target.value },
                  })
                }
              />
            </label>
            <label className={userStyles.label} htmlFor="email-to">
              To address
              <input
                className={userStyles.input}
                id="email-to"
                value={current.email.to_address}
                onChange={(event) =>
                  setSettings({
                    ...current,
                    email: { ...current.email, to_address: event.target.value },
                  })
                }
              />
            </label>
            <label className={userStyles.checkbox} htmlFor="email-tls">
              <input
                id="email-tls"
                type="checkbox"
                checked={current.email.use_tls}
                onChange={(event) =>
                  setSettings({
                    ...current,
                    email: { ...current.email, use_tls: event.target.checked },
                  })
                }
              />
              Use STARTTLS
            </label>
            {canSend ? (
              <button className={userStyles.secondaryButton} type="button" onClick={() => void handleTest('email')}>
                Send email test
              </button>
            ) : null}
          </article>

          <section className={`${styles.channelCard} ${styles.reportsSection}`} aria-labelledby="scheduled-reports">
            <h2 className={styles.channelTitle} id="scheduled-reports">
              Scheduled Reports
            </h2>
            <p className={styles.channelHint}>Telegram summaries using existing analytics services.</p>
            <section className={pageStyles.statGrid} aria-label="Scheduled report cards">
              <ReportStatusCard
                title="Hourly Report"
                card={current.reports.hourly}
                enabled={current.reports.hourly_enabled}
              />
              <ReportStatusCard
                title="Daily Report"
                card={current.reports.daily}
                enabled={current.reports.daily_enabled}
              />
              <ReportStatusCard
                title="Weekly Report"
                card={current.reports.weekly}
                enabled={current.reports.weekly_enabled}
              />
            </section>
            <label className={userStyles.checkbox} htmlFor="hourly-report-enabled">
              <input
                id="hourly-report-enabled"
                type="checkbox"
                checked={current.reports.hourly_enabled}
                onChange={(event) =>
                  setSettings({
                    ...current,
                    reports: { ...current.reports, hourly_enabled: event.target.checked },
                  })
                }
              />
              Enable Hourly Report
            </label>
            <label className={userStyles.checkbox} htmlFor="daily-report-enabled">
              <input
                id="daily-report-enabled"
                type="checkbox"
                checked={current.reports.daily_enabled}
                onChange={(event) =>
                  setSettings({
                    ...current,
                    reports: { ...current.reports, daily_enabled: event.target.checked },
                  })
                }
              />
              Enable Daily Report
            </label>
            <label className={userStyles.checkbox} htmlFor="weekly-report-enabled">
              <input
                id="weekly-report-enabled"
                type="checkbox"
                checked={current.reports.weekly_enabled}
                onChange={(event) =>
                  setSettings({
                    ...current,
                    reports: { ...current.reports, weekly_enabled: event.target.checked },
                  })
                }
              />
              Enable Weekly Report
            </label>
            <label className={userStyles.label} htmlFor="hour-interval">
              Hour Interval
              <input
                className={userStyles.input}
                id="hour-interval"
                type="number"
                min={1}
                max={24}
                value={current.reports.hour_interval}
                onChange={(event) =>
                  setSettings({
                    ...current,
                    reports: { ...current.reports, hour_interval: Number(event.target.value) },
                  })
                }
              />
            </label>
            <label className={userStyles.label} htmlFor="daily-time">
              Daily Time
              <input
                className={userStyles.input}
                id="daily-time"
                type="time"
                value={current.reports.daily_time}
                onChange={(event) =>
                  setSettings({
                    ...current,
                    reports: { ...current.reports, daily_time: event.target.value },
                  })
                }
              />
            </label>
            <label className={userStyles.label} htmlFor="weekly-day">
              Weekly Day
              <select
                className={userStyles.input}
                id="weekly-day"
                value={current.reports.weekly_day}
                onChange={(event) =>
                  setSettings({
                    ...current,
                    reports: { ...current.reports, weekly_day: event.target.value },
                  })
                }
              >
                <option value="sunday">Sunday</option>
                <option value="monday">Monday</option>
                <option value="tuesday">Tuesday</option>
                <option value="wednesday">Wednesday</option>
                <option value="thursday">Thursday</option>
                <option value="friday">Friday</option>
                <option value="saturday">Saturday</option>
              </select>
            </label>
            <label className={userStyles.label} htmlFor="weekly-time">
              Weekly Time
              <input
                className={userStyles.input}
                id="weekly-time"
                type="time"
                value={current.reports.weekly_time}
                onChange={(event) =>
                  setSettings({
                    ...current,
                    reports: { ...current.reports, weekly_time: event.target.value },
                  })
                }
              />
            </label>
            <label className={userStyles.label} htmlFor="report-timezone">
              Timezone
              <input
                className={userStyles.input}
                id="report-timezone"
                value={current.reports.timezone}
                onChange={(event) =>
                  setSettings({
                    ...current,
                    reports: { ...current.reports, timezone: event.target.value },
                  })
                }
              />
            </label>
            {canConfigure ? (
              <section className={styles.reportsSection} aria-labelledby="telegram-test-title">
                <h3 className={styles.channelTitle} id="telegram-test-title">
                  Telegram Test
                </h3>
                <p className={styles.channelHint}>Verify Telegram configuration immediately.</p>
                <button
                  className={userStyles.secondaryButton}
                  disabled={sendingReport}
                  type="button"
                  onClick={() => void handleTestReport()}
                >
                  Send Test Report
                </button>
              </section>
            ) : null}
          </section>

          <div className={userStyles.dialogActions}>
            <button className={userStyles.primaryButton} type="submit">
              Save notification settings
            </button>
          </div>
        </form>
      ) : null}
      <PhotoMonitorSettingsCard canConfigure={canConfigure} />
      <section className={styles.reportsSection} aria-labelledby="deployment-title">
        <h2 className={styles.channelTitle} id="deployment-title">
          Deployment
        </h2>
        {remoteError ? <SectionError title="Remote Access failed" onRetry={loadRemote} /> : null}
        {!remote && !remoteError ? <OverviewSkeleton /> : null}
        {remote ? (
          <RemoteAccessCard
            access={remote}
            showActions
            onCopy={(url) => void handleCopyUrl(url)}
            onOpen={handleOpenUrl}
          />
        ) : null}
      </section>
      <PwaSettingsCard />
    </section>
  )
}

function ReportStatusCard({
  title,
  card,
  enabled,
}: {
  title: string
  card: ScheduledReportCard
  enabled: boolean
}) {
  const lastSent = card.last_sent ? formatThaiDateTime(card.last_sent, false) : 'Never'
  const nextScheduled = card.next_scheduled ? formatThaiDateTime(card.next_scheduled, false) : '—'
  const state = enabled ? 'Enabled' : 'Disabled'
  return (
    <article className={styles.channelCard} aria-label={`${title} ${state}`}>
      <h3 className={styles.channelTitle}>{title}</h3>
      <p className={styles.channelHint}>{state}</p>
      <p className={styles.channelHint}>Last Sent: {lastSent}</p>
      <p className={styles.channelHint}>Next Scheduled: {nextScheduled}</p>
      <p className={styles.channelHint}>Status {card.status}</p>
    </article>
  )
}
