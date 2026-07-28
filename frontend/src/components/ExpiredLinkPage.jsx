import { useEffect } from 'react'
import {  useNavigate } from 'react-router-dom'
import styles from './ExpiredLinkPage.module.css'

export default function ExpiredLinkPage() {
  const navigate = useNavigate()

  useEffect(() => {
    document.title = 'Link expired · snip'
  }, [])

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <div className={styles.eyebrow}>⚠ Link expired</div>
        <h1>This short link is no longer available.</h1>
        <p>
          The link you tried to open, has expired and can no longer be redirected.
        </p>
        <div className={styles.actions}>
          <button type="button" className={styles.primaryBtn} onClick={() => navigate('/')}>
            Back home
          </button>
        </div>
      </div>
    </div>
  )
}
