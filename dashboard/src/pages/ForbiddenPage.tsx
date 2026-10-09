import { Link } from 'react-router-dom'
import styles from './Pages.module.css'

export function ForbiddenPage() {
  return (
    <section className={styles.forbidden} aria-labelledby="forbidden-title">
      <p className={styles.eyebrow}>403</p>
      <h1 className={styles.title} id="forbidden-title">
        Permission denied
      </h1>
      <p className={styles.description}>
        Your account does not have permission to open this page.
      </p>
      <p>
        <Link className={styles.backLink} to="/dashboard">
          Return to dashboard
        </Link>
      </p>
    </section>
  )
}
