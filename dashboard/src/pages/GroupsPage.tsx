import { useMemo, useState, type FormEvent } from 'react'
import { createGroup, getAgents, getGroups, assignAgentsToGroup } from '../api/dashboard'
import { useCan } from '../auth/useCan'
import { BulkAssignDialog } from '../components/BulkAssignDialog'
import { EmptyState } from '../components/EmptyState'
import { GroupCard } from '../components/GroupCard'
import { LastUpdated } from '../components/LastUpdated'
import { SectionError } from '../components/SectionError'
import { OverviewSkeleton } from '../components/Skeleton'
import { ModalDialog } from '../components/UserDialogs'
import { LIVE_PAGE_POLL } from '../constants'
import { useLivePolling } from '../hooks/useDashboardSocket'
import { getErrorMessage } from '../utils/errors'
import componentStyles from '../components/Components.module.css'
import userStyles from './UsersPage.module.css'
import pageStyles from './Pages.module.css'
import styles from './GroupsPage.module.css'

const GROUP_EVENTS = ['overview_updated', 'agent_updated'] as const

export function GroupsPage() {
  const canManage = useCan()('manage_groups')
  const groups = useLivePolling(getGroups, GROUP_EVENTS, LIVE_PAGE_POLL)
  const agents = useLivePolling(getAgents, GROUP_EVENTS, LIVE_PAGE_POLL)
  const [dialog, setDialog] = useState<'create' | 'assign' | null>(null)
  const [query, setQuery] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  const lastUpdated =
    [groups.lastUpdated, agents.lastUpdated]
      .filter((value): value is Date => value !== null)
      .sort((left, right) => right.getTime() - left.getTime())[0] ?? null

  const visibleGroups = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!groups.data) {
      return []
    }
    if (!needle) {
      return groups.data
    }
    return groups.data.filter(
      (group) =>
        group.name.toLowerCase().includes(needle) ||
        group.description.toLowerCase().includes(needle),
    )
  }, [groups.data, query])

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFormError(null)
    try {
      await createGroup({ name, description })
      setName('')
      setDescription('')
      setDialog(null)
      setToast('Group created.')
      groups.retry()
    } catch (error) {
      setFormError(getErrorMessage(error))
    }
  }

  return (
    <section className={pageStyles.page}>
      <header className={pageStyles.pageHeader}>
        <div>
          <p className={pageStyles.eyebrow}>Infrastructure</p>
          <h1 className={pageStyles.title}>Groups</h1>
          <p className={pageStyles.description}>Organize agents by rack, site, or role.</p>
        </div>
        <div className={styles.headerActions}>
          <LastUpdated refreshing={groups.isRefreshing} value={lastUpdated} />
          {canManage ? (
            <>
              <button
                className={userStyles.secondaryButton}
                type="button"
                onClick={() => setDialog('assign')}
                disabled={!groups.data?.length}
              >
                Assign agents
              </button>
              <button className={userStyles.primaryButton} type="button" onClick={() => setDialog('create')}>
                Create group
              </button>
            </>
          ) : null}
        </div>
      </header>

      {toast ? (
        <p className={userStyles.toast} role="status">
          {toast}
        </p>
      ) : null}
      {groups.error ? <SectionError title="Groups API failed" onRetry={groups.retry} /> : null}
      {!groups.data && !groups.error ? <OverviewSkeleton /> : null}
      {groups.data ? (
        <section className={componentStyles.toolbar} aria-label="Group search">
          <label className={componentStyles.searchLabel} htmlFor="group-search">
            Search groups
            <input
              className={componentStyles.searchInput}
              id="group-search"
              type="search"
              value={query}
              placeholder="Search name or description"
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
        </section>
      ) : null}
      {groups.data && groups.data.length === 0 ? <EmptyState message="No groups yet." /> : null}
      {groups.data && groups.data.length > 0 && visibleGroups.length === 0 ? (
        <EmptyState message="No groups match this search." />
      ) : null}
      {visibleGroups.length > 0 ? (
        <section className={styles.groupGrid} aria-label="Agent groups">
          {visibleGroups.map((group) => (
            <GroupCard group={group} key={group.id} />
          ))}
        </section>
      ) : null}

      {dialog === 'create' ? (
        <ModalDialog open title="Create group" onClose={() => setDialog(null)}>
          <form className={userStyles.form} onSubmit={(event) => void handleCreate(event)}>
            <label className={userStyles.label} htmlFor="group-name">
              Name
              <input
                className={userStyles.input}
                id="group-name"
                name="name"
                required
                maxLength={100}
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </label>
            <label className={userStyles.label} htmlFor="group-description">
              Description
              <input
                className={userStyles.input}
                id="group-description"
                name="description"
                maxLength={500}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
              />
            </label>
            {formError ? (
              <p className={userStyles.formError} role="alert">
                {formError}
              </p>
            ) : null}
            <div className={userStyles.dialogActions}>
              <button className={userStyles.secondaryButton} type="button" onClick={() => setDialog(null)}>
                Cancel
              </button>
              <button className={userStyles.primaryButton} type="submit">
                Create group
              </button>
            </div>
          </form>
        </ModalDialog>
      ) : null}

      {dialog === 'assign' && groups.data ? (
        <BulkAssignDialog
          open
          groups={groups.data}
          agents={agents.data ?? []}
          onClose={() => setDialog(null)}
          onAssign={async (groupId, agentIds) => {
            await assignAgentsToGroup(groupId, agentIds)
            setDialog(null)
            setToast('Agents assigned.')
            groups.retry()
          }}
        />
      ) : null}
    </section>
  )
}
