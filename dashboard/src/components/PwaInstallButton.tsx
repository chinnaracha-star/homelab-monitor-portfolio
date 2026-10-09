import { memo } from 'react'
import { useOptionalPwa } from '../pwa/PwaProvider'
import userStyles from '../pages/UsersPage.module.css'

export const PwaInstallButton = memo(function PwaInstallButton({
  label = 'Install HomeLab Monitor',
}: {
  label?: string
}) {
  const pwa = useOptionalPwa()
  if (!pwa?.canInstall || pwa.installed) {
    return null
  }

  return (
    <button className={userStyles.secondaryButton} type="button" onClick={() => void pwa.install()}>
      {label}
    </button>
  )
})
