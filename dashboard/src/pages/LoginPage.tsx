import { type FormEvent, useEffect, useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { getErrorMessage } from '../utils/errors'
import styles from './LoginPage.module.css'

export function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname

  useEffect(() => {
    if (!('serviceWorker' in navigator)) {
      return
    }
    void navigator.serviceWorker.getRegistrations().then((registrations) => {
      void Promise.all(registrations.map((registration) => registration.unregister()))
    })
  }, [])

  if (user) {
    return <Navigate replace to={from && from !== '/login' ? from : '/dashboard'} />
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await login(username, password)
      void navigate(from && from !== '/login' ? from : '/dashboard', { replace: true })
    } catch (requestError) {
      setError(getErrorMessage(requestError))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className={styles.screen}>
      <section className={styles.card} aria-labelledby="login-title">
        <p className={styles.eyebrow}>HomeLab Monitor</p>
        <h1 className={styles.title} id="login-title">
          Sign in
        </h1>
        <p className={styles.description}>Use your dashboard account to continue.</p>
        <form className={styles.form} onSubmit={handleSubmit}>
          <label className={styles.label} htmlFor="username">
            Username
            <input
              autoComplete="username"
              className={styles.input}
              id="username"
              name="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
            />
          </label>
          <label className={styles.label} htmlFor="password">
            Password
            <input
              autoComplete="current-password"
              className={styles.input}
              id="password"
              name="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
          {error ? (
            <p className={styles.error} role="alert">
              {error}
            </p>
          ) : null}
          <button className={styles.submit} disabled={submitting} type="submit">
            {submitting ? 'Signing in…' : 'Login'}
          </button>
        </form>
      </section>
    </main>
  )
}
