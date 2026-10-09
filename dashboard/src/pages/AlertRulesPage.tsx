import { useMemo, useState, type FormEvent } from 'react'
import {
  createAlertRule,
  deleteAlertRule,
  getAgents,
  getAlertRules,
  getGroups,
  setAlertRuleEnabled,
  updateAlertRule,
} from '../api/dashboard'
import { useCan } from '../auth/useCan'
import { ConfirmDialog, ModalDialog } from '../components/UserDialogs'
import { EmptyState } from '../components/EmptyState'
import { LastUpdated } from '../components/LastUpdated'
import { SectionError } from '../components/SectionError'
import { TableSkeleton } from '../components/Skeleton'
import { useLivePolling } from '../hooks/useDashboardSocket'
import type {
  AlertAppliesTo,
  AlertMetric,
  AlertOperator,
  AlertRule,
  AlertRulePayload,
  AlertSeverity,
} from '../types/dashboard'
import { getErrorMessage } from '../utils/errors'
import {
  formatCooldown,
  METRIC_OPTIONS,
  OPERATOR_OPTIONS,
  previewAlertRule,
  SEVERITY_OPTIONS,
} from '../utils/alertRules'
import componentStyles from '../components/Components.module.css'
import userStyles from './UsersPage.module.css'
import pageStyles from './Pages.module.css'
import styles from './AlertRulesPage.module.css'

const RULE_EVENTS = ['overview_updated', 'alert_updated'] as const

type DialogState =
  | { type: 'create' }
  | { type: 'edit'; rule: AlertRule }
  | { type: 'delete'; rule: AlertRule }
  | null

const emptyForm: AlertRulePayload = {
  name: '',
  description: '',
  metric: 'cpu_percent',
  operator: '>',
  threshold: 90,
  severity: 'critical',
  enabled: true,
  cooldown_seconds: 0,
  applies_to: 'all',
  group_id: null,
  agent_id: null,
}

export function AlertRulesPage() {
  const canManage = useCan()('manage_alert_rules')
  const rules = useLivePolling(getAlertRules, RULE_EVENTS)
  const groups = useLivePolling(getGroups, RULE_EVENTS)
  const agents = useLivePolling(getAgents, RULE_EVENTS)
  const [query, setQuery] = useState('')
  const [metricFilter, setMetricFilter] = useState<'all' | AlertMetric>('all')
  const [severityFilter, setSeverityFilter] = useState<'all' | AlertSeverity>('all')
  const [statusFilter, setStatusFilter] = useState<'all' | 'enabled' | 'disabled'>('all')
  const [dialog, setDialog] = useState<DialogState>(null)
  const [form, setForm] = useState<AlertRulePayload>(emptyForm)
  const [formError, setFormError] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  const visibleRules = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return (rules.data ?? []).filter((rule) => {
      const matchesQuery =
        needle.length === 0 ||
        rule.name.toLowerCase().includes(needle) ||
        rule.description.toLowerCase().includes(needle) ||
        rule.preview.toLowerCase().includes(needle)
      const matchesMetric = metricFilter === 'all' || rule.metric === metricFilter
      const matchesSeverity = severityFilter === 'all' || rule.severity === severityFilter
      const matchesStatus =
        statusFilter === 'all' || (statusFilter === 'enabled' ? rule.enabled : !rule.enabled)
      return matchesQuery && matchesMetric && matchesSeverity && matchesStatus
    })
  }, [metricFilter, query, rules.data, severityFilter, statusFilter])

  function openCreate() {
    setForm(emptyForm)
    setFormError(null)
    setDialog({ type: 'create' })
  }

  function openEdit(rule: AlertRule) {
    setForm({
      name: rule.name,
      description: rule.description,
      metric: rule.metric,
      operator: rule.operator,
      threshold: rule.threshold,
      severity: rule.severity,
      enabled: rule.enabled,
      cooldown_seconds: rule.cooldown_seconds,
      applies_to: rule.applies_to,
      group_id: rule.group_id,
      agent_id: rule.agent_id,
    })
    setFormError(null)
    setDialog({ type: 'edit', rule })
  }

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFormError(null)
    const payload: AlertRulePayload = {
      ...form,
      group_id: form.applies_to === 'group' ? form.group_id : null,
      agent_id: form.applies_to === 'agent' ? form.agent_id : null,
    }
    try {
      if (dialog?.type === 'edit') {
        await updateAlertRule(dialog.rule.id, payload)
        setToast('Alert rule updated.')
      } else {
        await createAlertRule(payload)
        setToast('Alert rule created.')
      }
      setDialog(null)
      rules.retry()
    } catch (error) {
      setFormError(getErrorMessage(error))
    }
  }

  async function handleEnable(rule: AlertRule, enabled: boolean) {
    try {
      await setAlertRuleEnabled(rule.id, enabled)
      setToast(enabled ? 'Alert rule enabled.' : 'Alert rule disabled.')
      rules.retry()
    } catch (error) {
      setToast(getErrorMessage(error))
    }
  }

  async function handleDelete() {
    if (dialog?.type !== 'delete') {
      return
    }
    try {
      await deleteAlertRule(dialog.rule.id)
      setDialog(null)
      setToast('Alert rule deleted.')
      rules.retry()
    } catch (error) {
      setToast(getErrorMessage(error))
    }
  }

  const preview = previewAlertRule(form.metric, form.operator, form.threshold, form.severity)

  return (
    <section className={pageStyles.page}>
      <header className={pageStyles.pageHeader}>
        <div>
          <p className={pageStyles.eyebrow}>Operations</p>
          <h1 className={pageStyles.title}>Alert Rules</h1>
          <p className={pageStyles.description}>
            Configurable thresholds for the existing alert engine.
          </p>
        </div>
        <div className={userStyles.actions}>
          <LastUpdated refreshing={rules.isRefreshing} value={rules.lastUpdated} />
          {canManage ? (
            <button className={userStyles.primaryButton} type="button" onClick={openCreate}>
              Create rule
            </button>
          ) : null}
        </div>
      </header>
      {toast ? (
        <p className={userStyles.toast} role="status">
          {toast}
        </p>
      ) : null}
      {rules.error ? <SectionError title="Alert rules API failed" onRetry={rules.retry} /> : null}
      {!rules.data && !rules.error ? <TableSkeleton label="Loading alert rules" /> : null}
      {rules.data ? (
        <section className={componentStyles.toolbar} aria-label="Alert rule filters">
          <label className={componentStyles.searchLabel} htmlFor="rule-search">
            Search rules
            <input
              className={componentStyles.searchInput}
              id="rule-search"
              type="search"
              value={query}
              placeholder="Search name, description, or preview"
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <div className={styles.filters}>
            <label className={userStyles.label} htmlFor="rule-metric-filter">
              Metric
              <select
                className={userStyles.input}
                id="rule-metric-filter"
                value={metricFilter}
                onChange={(event) => setMetricFilter(event.target.value as 'all' | AlertMetric)}
              >
                <option value="all">All metrics</option>
                {METRIC_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className={userStyles.label} htmlFor="rule-severity-filter">
              Severity
              <select
                className={userStyles.input}
                id="rule-severity-filter"
                value={severityFilter}
                onChange={(event) => setSeverityFilter(event.target.value as 'all' | AlertSeverity)}
              >
                <option value="all">All severities</option>
                {SEVERITY_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
            <label className={userStyles.label} htmlFor="rule-status-filter">
              Status
              <select
                className={userStyles.input}
                id="rule-status-filter"
                value={statusFilter}
                onChange={(event) =>
                  setStatusFilter(event.target.value as 'all' | 'enabled' | 'disabled')
                }
              >
                <option value="all">All statuses</option>
                <option value="enabled">Enabled</option>
                <option value="disabled">Disabled</option>
              </select>
            </label>
          </div>
        </section>
      ) : null}
      {rules.data && rules.data.length === 0 ? <EmptyState message="No alert rules yet." /> : null}
      {rules.data && rules.data.length > 0 && visibleRules.length === 0 ? (
        <EmptyState message="No alert rules match this search." />
      ) : null}
      {visibleRules.length > 0 ? (
        <section className={componentStyles.tableWrapper}>
          <table className={componentStyles.table} aria-label="Alert rules">
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Metric</th>
                <th scope="col">Severity</th>
                <th scope="col">Cooldown</th>
                <th scope="col">Preview</th>
                <th scope="col">Status</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {visibleRules.map((rule) => (
                <tr key={rule.id}>
                  <th scope="row">{rule.name}</th>
                  <td>
                    <span className={styles.metricBadge}>{rule.metric.replaceAll('_', ' ')}</span>
                  </td>
                  <td>
                    <span className={`${styles.severityBadge} ${styles[rule.severity]}`}>
                      {rule.severity}
                    </span>
                  </td>
                  <td>{formatCooldown(rule.cooldown_seconds)}</td>
                  <td>{rule.preview}</td>
                  <td>{rule.enabled ? 'Enabled' : 'Disabled'}</td>
                  <td>
                    {canManage ? (
                      <div className={userStyles.actions}>
                        <button
                          className={userStyles.secondaryButton}
                          type="button"
                          onClick={() => openEdit(rule)}
                        >
                          Edit
                        </button>
                        <button
                          className={userStyles.secondaryButton}
                          type="button"
                          onClick={() => void handleEnable(rule, !rule.enabled)}
                        >
                          {rule.enabled ? 'Disable' : 'Enable'}
                        </button>
                        <button
                          className={userStyles.dangerButton}
                          type="button"
                          onClick={() => setDialog({ type: 'delete', rule })}
                        >
                          Delete
                        </button>
                      </div>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}

      {dialog?.type === 'create' || dialog?.type === 'edit' ? (
        <ModalDialog
          open
          wide
          title={dialog.type === 'edit' ? 'Edit alert rule' : 'Create alert rule'}
          onClose={() => setDialog(null)}
        >
          <form className={userStyles.form} onSubmit={(event) => void handleSave(event)}>
            <label className={userStyles.label} htmlFor="rule-name">
              Name
              <input
                className={userStyles.input}
                id="rule-name"
                required
                maxLength={100}
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
              />
            </label>
            <label className={userStyles.label} htmlFor="rule-description">
              Description
              <input
                className={userStyles.input}
                id="rule-description"
                maxLength={500}
                value={form.description}
                onChange={(event) => setForm({ ...form, description: event.target.value })}
              />
            </label>
            <label className={userStyles.label} htmlFor="rule-metric">
              Metric
              <select
                className={userStyles.input}
                id="rule-metric"
                value={form.metric}
                onChange={(event) => setForm({ ...form, metric: event.target.value as AlertMetric })}
              >
                {METRIC_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className={userStyles.label} htmlFor="rule-operator">
              Operator
              <select
                className={userStyles.input}
                id="rule-operator"
                value={form.operator}
                onChange={(event) =>
                  setForm({ ...form, operator: event.target.value as AlertOperator })
                }
              >
                {OPERATOR_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className={userStyles.label} htmlFor="rule-threshold">
              Threshold
              <input
                className={userStyles.input}
                id="rule-threshold"
                type="number"
                required
                value={form.threshold}
                onChange={(event) => setForm({ ...form, threshold: Number(event.target.value) })}
              />
            </label>
            <label className={userStyles.label} htmlFor="rule-severity">
              Severity
              <select
                className={userStyles.input}
                id="rule-severity"
                value={form.severity}
                onChange={(event) =>
                  setForm({ ...form, severity: event.target.value as AlertSeverity })
                }
              >
                {SEVERITY_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
            <label className={userStyles.label} htmlFor="rule-cooldown">
              Cooldown seconds
              <input
                className={userStyles.input}
                id="rule-cooldown"
                type="number"
                min={0}
                max={86400}
                value={form.cooldown_seconds}
                onChange={(event) =>
                  setForm({ ...form, cooldown_seconds: Number(event.target.value) })
                }
              />
            </label>
            <label className={userStyles.label} htmlFor="rule-applies">
              Applies to
              <select
                className={userStyles.input}
                id="rule-applies"
                value={form.applies_to}
                onChange={(event) =>
                  setForm({ ...form, applies_to: event.target.value as AlertAppliesTo })
                }
              >
                <option value="all">All agents</option>
                <option value="group">Group</option>
                <option value="agent">Agent</option>
              </select>
            </label>
            {form.applies_to === 'group' ? (
              <label className={userStyles.label} htmlFor="rule-group">
                Group
                <select
                  className={userStyles.input}
                  id="rule-group"
                  required
                  value={form.group_id ?? ''}
                  onChange={(event) => setForm({ ...form, group_id: event.target.value })}
                >
                  <option value="">Select a group</option>
                  {(groups.data ?? []).map((group) => (
                    <option key={group.id} value={group.id}>
                      {group.name}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            {form.applies_to === 'agent' ? (
              <label className={userStyles.label} htmlFor="rule-agent">
                Agent
                <select
                  className={userStyles.input}
                  id="rule-agent"
                  required
                  value={form.agent_id ?? ''}
                  onChange={(event) => setForm({ ...form, agent_id: event.target.value })}
                >
                  <option value="">Select an agent</option>
                  {(agents.data ?? []).map((agent) => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <label className={userStyles.checkbox} htmlFor="rule-enabled">
              <input
                id="rule-enabled"
                type="checkbox"
                checked={form.enabled}
                onChange={(event) => setForm({ ...form, enabled: event.target.checked })}
              />
              Enabled
            </label>
            <p className={styles.preview} role="status">
              {preview}
            </p>
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
                {dialog.type === 'edit' ? 'Save rule' : 'Create alert rule'}
              </button>
            </div>
          </form>
        </ModalDialog>
      ) : null}

      {dialog?.type === 'delete' ? (
        <ConfirmDialog
          open
          title="Delete alert rule"
          message={`Delete ${dialog.rule.name}? Evaluation will stop using this rule.`}
          confirmLabel="Delete rule"
          onClose={() => setDialog(null)}
          onConfirm={() => void handleDelete()}
        />
      ) : null}
    </section>
  )
}
