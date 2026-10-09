import { Link } from 'react-router-dom'
import type { AgentSummary } from '../types/dashboard'
import { StatusBadge } from './StatusBadge'
import styles from '../pages/GroupsPage.module.css'

interface AgentCardProps {
  agent: AgentSummary
}

export function AgentCard({ agent }: AgentCardProps) {
  return (
    <article className={styles.memberCard} aria-label={`${agent.name} agent`}>
      <h3 className={styles.groupName}>
        <Link className={styles.groupLink} to={`/agents/${agent.id}`}>
          {agent.name}
        </Link>
      </h3>
      <p className={styles.groupDescription}>{agent.hostname}</p>
      <StatusBadge status={agent.status} />
    </article>
  )
}
