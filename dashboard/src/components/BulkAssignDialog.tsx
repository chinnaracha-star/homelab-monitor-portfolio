import { useMemo, useState, type FormEvent } from 'react'
import type { AgentSummary, GroupSummary } from '../types/dashboard'
import { ConfirmDialog, ModalDialog } from './UserDialogs'
import userStyles from '../pages/UsersPage.module.css'
import styles from '../pages/GroupsPage.module.css'

interface BulkAssignDialogProps {
  open: boolean
  groups: GroupSummary[]
  agents: AgentSummary[]
  defaultGroupId?: string
  onClose: () => void
  onAssign: (groupId: string, agentIds: string[]) => Promise<void>
}

export function BulkAssignDialog({
  open,
  groups,
  agents,
  defaultGroupId,
  onClose,
  onAssign,
}: BulkAssignDialogProps) {
  const [groupId, setGroupId] = useState(defaultGroupId ?? groups[0]?.id ?? '')
  const [selected, setSelected] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [confirming, setConfirming] = useState(false)

  const memberIds = useMemo(() => {
    const group = groups.find((item) => item.id === groupId)
    return new Set(group?.agent_ids ?? [])
  }, [groupId, groups])

  const assignable = agents.filter((agent) => !memberIds.has(agent.id))

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!groupId || selected.length === 0) {
      setError('Select a group and at least one agent.')
      return
    }
    setConfirming(true)
  }

  async function confirmAssign() {
    setError(null)
    try {
      await onAssign(groupId, selected)
      setSelected([])
      setConfirming(false)
    } catch (requestError) {
      setConfirming(false)
      setError(requestError instanceof Error ? requestError.message : 'Assignment failed.')
    }
  }

  return (
    <>
      <ModalDialog open={open && !confirming} title="Assign agents" wide onClose={onClose}>
        <form className={userStyles.form} onSubmit={(event) => void handleSubmit(event)}>
          <label className={userStyles.label} htmlFor="bulk-group">
            Group
            <select
              className={userStyles.input}
              id="bulk-group"
              value={groupId}
              onChange={(event) => {
                setGroupId(event.target.value)
                setSelected([])
              }}
            >
              {groups.map((group) => (
                <option key={group.id} value={group.id}>
                  {group.name}
                </option>
              ))}
            </select>
          </label>
          <fieldset className={styles.agentPicker}>
            <legend>Agents</legend>
            {assignable.length === 0 ? (
              <p className={styles.groupDescription}>All agents are already in this group.</p>
            ) : (
              assignable.map((agent) => (
                <label className={userStyles.checkbox} htmlFor={`assign-${agent.id}`} key={agent.id}>
                  <input
                    id={`assign-${agent.id}`}
                    type="checkbox"
                    checked={selected.includes(agent.id)}
                    onChange={(event) => {
                      setSelected((current) =>
                        event.target.checked
                          ? [...current, agent.id]
                          : current.filter((id) => id !== agent.id),
                      )
                    }}
                  />
                  {agent.name}
                </label>
              ))
            )}
          </fieldset>
          {error ? (
            <p className={userStyles.formError} role="alert">
              {error}
            </p>
          ) : null}
          <div className={userStyles.dialogActions}>
            <button className={userStyles.secondaryButton} type="button" onClick={onClose}>
              Cancel
            </button>
            <button className={userStyles.primaryButton} type="submit" disabled={assignable.length === 0}>
              Assign
            </button>
          </div>
        </form>
      </ModalDialog>
      <ConfirmDialog
        open={confirming}
        title="Confirm assignment"
        message={`Assign ${selected.length} agent${selected.length === 1 ? '' : 's'} to this group?`}
        confirmLabel="Confirm assign"
        onClose={() => setConfirming(false)}
        onConfirm={() => void confirmAssign()}
      />
    </>
  )
}
