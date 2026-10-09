import { Link } from 'react-router-dom'
import type { GroupSummary } from '../types/dashboard'
import styles from '../pages/GroupsPage.module.css'

interface GroupCardProps {
  group: GroupSummary
}

export function GroupCard({ group }: GroupCardProps) {
  return (
    <article className={styles.groupCard} aria-label={`${group.name} group`}>
      <h3 className={styles.groupName}>
        <Link className={styles.groupLink} to={`/groups/${group.id}`}>
          {group.name}
        </Link>
      </h3>
      {group.description ? <p className={styles.groupDescription}>{group.description}</p> : null}
      <dl className={styles.groupStats}>
        <div>
          <dt>Agents</dt>
          <dd>{group.agents}</dd>
        </div>
        <div>
          <dt>Online</dt>
          <dd>{group.online}</dd>
        </div>
      </dl>
    </article>
  )
}
