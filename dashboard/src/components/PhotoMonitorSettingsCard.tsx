import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { getPhotoMonitorSettings, updatePhotoMonitorSettings } from '../api/dashboard'
import type { PhotoMonitorSettings } from '../types/dashboard'
import { SectionError } from './SectionError'
import { getErrorMessage } from '../utils/errors'
import { displayFolderName } from '../utils/photoFolders'
import userStyles from '../pages/UsersPage.module.css'
import styles from '../pages/SettingsPage.module.css'

function foldersFromSettings(settings: PhotoMonitorSettings): string[] {
  if (settings.watch_folders?.length) {
    return settings.watch_folders
  }
  return settings.watch_folder ? [settings.watch_folder] : []
}

export function PhotoMonitorSettingsCard({ canConfigure }: { canConfigure: boolean }) {
  const [settings, setSettings] = useState<PhotoMonitorSettings | null>(null)
  const [draftFolder, setDraftFolder] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  const load = useCallback(() => {
    setError(null)
    void getPhotoMonitorSettings()
      .then(setSettings)
      .catch((loadError: unknown) => {
        setError(getErrorMessage(loadError))
      })
  }, [])

  useEffect(() => {
    load()
  }, [load])

  function updateFolders(folders: string[]) {
    if (!settings) {
      return
    }
    setSettings({
      ...settings,
      watch_folders: folders,
      watch_folder: folders[0] ?? '',
    })
  }

  function addFolder() {
    const folder = draftFolder.trim()
    if (!settings || !folder) {
      return
    }
    const folders = foldersFromSettings(settings)
    if (folders.includes(folder)) {
      setError('Duplicate watch folders are not allowed')
      return
    }
    setError(null)
    updateFolders([...folders, folder])
    updateFolders([...folders, folder])
    setDraftFolder('')
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!settings || !canConfigure) {
      return
    }
    setError(null)
    try {
      const folders = foldersFromSettings(settings)
      if (folders.length === 0) {
        setError('At least one watch folder is required')
        return
      }
      const saved = await updatePhotoMonitorSettings({
        ...settings,
        watch_folders: folders,
        watch_folder: folders[0] ?? '',
      })
      setSettings(saved)
      setToast('Photo Monitor settings saved')
    } catch (saveError: unknown) {
      setError(getErrorMessage(saveError))
    }
  }

  const folders = settings ? foldersFromSettings(settings) : []

  return (
    <section className={styles.reportsSection} aria-labelledby="photo-monitor-settings-title">
      <h2 className={styles.channelTitle} id="photo-monitor-settings-title">
        Photo Monitor Settings
      </h2>
      <p className={styles.channelHint}>
        Poll NAS folders for new image files (jpg, jpeg, png, heic, gif, bmp, webp). Hidden files
        and .tmp / .part uploads are ignored. Each folder is scanned in the same watcher loop
        with its own baseline.
      </p>
      {error ? <SectionError title="Photo Monitor settings failed" onRetry={load} /> : null}
      {toast ? (
        <p className={userStyles.toast} role="status">
          {toast}
        </p>
      ) : null}
      {settings ? (
        <form className={userStyles.form} onSubmit={(event) => void handleSubmit(event)}>
          <label className={userStyles.checkbox} htmlFor="photo-monitor-enabled">
            <input
              checked={settings.enabled}
              disabled={!canConfigure}
              id="photo-monitor-enabled"
              type="checkbox"
              onChange={(event) =>
                setSettings({ ...settings, enabled: event.target.checked })
              }
            />
            Enable Photo Monitor
          </label>
          <fieldset className={userStyles.label}>
            <legend>Watch Folders</legend>
            <ul className={styles.folderList}>
              {folders.map((folder) => (
                <li className={styles.folderRow} key={folder}>
                  <div>
                    <p className={styles.folderPath}>{displayFolderName(folder)}</p>
                    <p className={styles.folderHint}>{folder}</p>
                  </div>
                  {canConfigure ? (
                    <button
                      className={userStyles.secondaryButton}
                      disabled={folders.length <= 1}
                      onClick={() => updateFolders(folders.filter((item) => item !== folder))}
                      type="button"
                    >
                      Remove
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
            {canConfigure ? (
              <div className={styles.folderAddRow}>
                <label className={userStyles.label} htmlFor="photo-watch-folder">
                  Add folder
                  <input
                    className={userStyles.input}
                    id="photo-watch-folder"
                    onChange={(event) => setDraftFolder(event.target.value)}
                    value={draftFolder}
                  />
                </label>
                <button
                  className={userStyles.secondaryButton}
                  onClick={addFolder}
                  type="button"
                >
                  + Add Folder
                </button>
              </div>
            ) : null}
          </fieldset>
          <label className={userStyles.checkbox} htmlFor="photo-recursive">
            <input
              checked={settings.recursive}
              disabled={!canConfigure}
              id="photo-recursive"
              type="checkbox"
              onChange={(event) =>
                setSettings({ ...settings, recursive: event.target.checked })
              }
            />
            Recursive Scan
          </label>
          <label className={userStyles.label} htmlFor="photo-scan-interval">
            Scan Interval
            <select
              className={userStyles.input}
              disabled={!canConfigure}
              id="photo-scan-interval"
              onChange={(event) =>
                setSettings({
                  ...settings,
                  scan_interval_seconds: Number(event.target.value) as 5 | 10 | 30 | 60,
                })
              }
              value={settings.scan_interval_seconds}
            >
              <option value={5}>5 sec</option>
              <option value={10}>10 sec</option>
              <option value={30}>30 sec</option>
              <option value={60}>60 sec</option>
            </select>
          </label>
          <label className={userStyles.label} htmlFor="photo-max-events">
            Maximum Events
            <select
              className={userStyles.input}
              disabled={!canConfigure}
              id="photo-max-events"
              onChange={(event) =>
                setSettings({
                  ...settings,
                  max_events: Number(event.target.value) as 100 | 500 | 1000,
                })
              }
              value={settings.max_events}
            >
              <option value={100}>100</option>
              <option value={500}>500</option>
              <option value={1000}>1000</option>
            </select>
          </label>
          <label className={userStyles.label} htmlFor="photo-auto-delete">
            Auto Delete History
            <select
              className={userStyles.input}
              disabled={!canConfigure}
              id="photo-auto-delete"
              onChange={(event) =>
                setSettings({
                  ...settings,
                  auto_delete_days: Number(event.target.value) as 0 | 30 | 90,
                })
              }
              value={settings.auto_delete_days}
            >
              <option value={0}>Never</option>
              <option value={30}>30 days</option>
              <option value={90}>90 days</option>
            </select>
          </label>
          {canConfigure ? (
            <div className={userStyles.dialogActions}>
              <button className={userStyles.primaryButton} type="submit">
                Save Photo Monitor settings
              </button>
            </div>
          ) : null}
        </form>
      ) : null}
    </section>
  )
}
