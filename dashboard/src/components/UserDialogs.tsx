import { useEffect, useRef, type FormEvent, type ReactNode } from 'react'
import styles from '../pages/UsersPage.module.css'

interface DialogProps {
  open: boolean
  title: string
  children: ReactNode
  onClose: () => void
  wide?: boolean
}

export function ModalDialog({ open, title, children, onClose, wide = false }: DialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const titleId = `user-dialog-${title.replaceAll(' ', '-').toLowerCase()}`

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) {
      return
    }
    if (open && !dialog.open) {
      dialog.showModal()
    }
    if (!open && dialog.open) {
      dialog.close()
    }
  }, [open])

  return (
    <dialog
      className={`${styles.dialog} ${wide ? styles.wideDialog : ''}`}
      ref={dialogRef}
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault()
        onClose()
      }}
    >
      {open ? (
        <>
          <h2 className={styles.dialogTitle} id={titleId}>
            {title}
          </h2>
          {children}
        </>
      ) : null}
    </dialog>
  )
}

interface ConfirmDialogProps {
  open: boolean
  title: string
  message: string
  confirmLabel: string
  onConfirm: () => void
  onClose: () => void
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  onConfirm,
  onClose,
}: ConfirmDialogProps) {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    onConfirm()
  }

  return (
    <ModalDialog open={open} title={title} onClose={onClose}>
      <form className={styles.form} onSubmit={handleSubmit}>
        <p className={styles.dialogMessage}>{message}</p>
        <div className={styles.dialogActions}>
          <button className={styles.secondaryButton} type="button" onClick={onClose}>
            Cancel
          </button>
          <button className={styles.dangerButton} type="submit">
            {confirmLabel}
          </button>
        </div>
      </form>
    </ModalDialog>
  )
}
