import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  assignAgentsToGroup,
  deleteGroup,
  getAgents,
  getGroup,
  getGroups,
  removeAgentFromGroup,
  updateGroup,
} from '../api/dashboard'
import { useCan } from '../auth/useCan'
import { AgentCard } from '../components/AgentCard'
import { BulkAssignDialog } from '../components/BulkAssignDialog'
import { EmptyState } from '../components/EmptyState'
import { LastUpdated } from '../components/LastUpdated'
import { SectionError } from '../components/SectionError'
import { OverviewSkeleton } from '../components/Skeleton'
import { StatCard } from '../components/StatCard'
import { ConfirmDialog, ModalDialog } from '../components/UserDialogs'
import { LIVE_PAGE_POLL } from '../constants'
import { useLivePolling } from '../hooks/useDashboardSocket'
import { getErrorMessage, isNotFound } from '../utils/errors'
import userStyles from './UsersPage.module.css'
import pageStyles from './Pages.module.css'
import styles from './GroupsPage.module.css'

const GROUP_EVENTS = ['overview_updated', 'agent_updated'] as const

export function GroupDetailPage() {
  const { groupId = '' } = useParams()
  const navigate = useNavigate()
  const canManage = useCan()('manage_groups')
  const group = useLivePolling(() => getGroup(groupId), GROUP_EVENTS, LIVE_PAGE_POLL)
  const groups = useLivePolling(getGroups, GROUP_EVENTS, LIVE_PAGE_POLL)
  const agents = useLivePolling(getAgents, GROUP_EVENTS, LIVE_PAGE_POLL)
  const [dialog, setDialog] = useState<'edit' | 'assign' | 'delete' | string | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  const lastUpdated =
    [group.lastUpdated, agents.lastUpdated]
      .filter((value): value is Date => value !== null)
      .sort((left, right) => right.getTime() - left.getTime())[0] ?? null

  async function handleEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFormError(null)
    try {
      await updateGroup(groupId, { name, description })
      setDialog(null)
      setToast('Group updated.')
      group.retry()
    } catch (error) {
      setFormError(getErrorMessage(error))
    }
  }

  return (
    <section className={pageStyles.page}>
      <header className={pageStyles.pageHeader}>
        <div>
          <p className={pageStyles.eyebrow}>
            <Link className={styles.groupLink} to="/groups">
              Groups
            </Link>
          </p>
          <h1 className={pageStyles.title}>{group.data?.name ?? 'Group'}</h1>
          <p className={pageStyles.description}>{group.data?.description || 'No description'}</p>
        </div>
        <div className={styles.headerActions}>
          <LastUpdated refreshing={group.isRefreshing} value={lastUpdated} />
          {canManage && group.data ? (
            <>
              <button className={userStyles.secondaryButton} type="button" onClick={() => setDialog('assign')}>
                Assign agents
              </button>
              <button
                className={userStyles.secondaryButton}
                type="button"
                onClick={() => {
                  setName(group.data?.name ?? '')
                  setDescription(group.data?.description ?? '')
                  setFormError(null)
                  setDialog('edit')
                }}
              >
                Edit group
              </button>
              <button className={userStyles.dangerButton} type="button" onClick={() => setDialog('delete')}>
                Delete group
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
      {group.error ? (
        <SectionError
          title={isNotFound(group.error) ? 'Group not found' : 'Group API failed'}
          onRetry={group.retry}
        />
      ) : null}
      {!group.data && !group.error ? <OverviewSkeleton /> : null}
      {group.data ? (
        <>
          <section className={pageStyles.statGrid} aria-label="Group summary">
            <StatCard label="Agents" value={group.data.agents} />
            <StatCard label="Online" value={group.data.online} />
          </section>
          {group.data.members.length === 0 ? (
            <EmptyState message="No agents in this group." />
          ) : (
            <section className={styles.memberGrid} aria-label="Agents in group">
              {group.data.members.map((member) => (
                <div key={member.id}>
                  <AgentCard agent={member} />
                  {canManage ? (
                    <button
                      className={`${userStyles.dangerButton} ${styles.removeButton}`}
                      type="button"
                      onClick={() => setDialog(`remove:${member.id}`)}
                    >
                      Remove from group
                    </button>
                  ) : null}
                </div>
              ))}
            </section>
          )}
        </>
      ) : null}

      {dialog === 'edit' ? (
        <ModalDialog open title="Edit group" onClose={() => setDialog(null)}>
          <form className={userStyles.form} onSubmit={(event) => void handleEdit(event)}>
            <label className={userStyles.label} htmlFor="edit-group-name">
              Name
              <input
                className={userStyles.input}
                id="edit-group-name"
                required
                maxLength={100}
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </label>
            <label className={userStyles.label} htmlFor="edit-group-description">
              Description
              <input
                className={userStyles.input}
                id="edit-group-description"
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
                Save group
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
          defaultGroupId={groupId}
          onClose={() => setDialog(null)}
          onAssign={async (targetGroupId, agentIds) => {
            await assignAgentsToGroup(targetGroupId, agentIds)
            setDialog(null)
            setToast('Agents assigned.')
            group.retry()
          }}
        />
      ) : null}

      <ConfirmDialog
        open={dialog === 'delete'}
        title="Delete group"
        message="Delete this group? Agents stay registered."
        confirmLabel="Confirm delete"
        onClose={() => setDialog(null)}
        onConfirm={async () => {
          await deleteGroup(groupId)
          navigate('/groups')
        }}
      />
      {typeof dialog === 'string' && dialog.startsWith('remove:') ? (
        <ConfirmDialog
          open
          title="Remove agent"
          message="Remove this agent from the group?"
          confirmLabel="Remove agent"
          onClose={() => setDialog(null)}
          onConfirm={async () => {
            await removeAgentFromGroup(groupId, dialog.slice('remove:'.length))
            setDialog(null)
            setToast('Agent removed.')
            group.retry()
          }}
        />
      ) : null}
    </section>
  )
}
