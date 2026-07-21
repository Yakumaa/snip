import { useState } from 'react'
import { shortenUrl, ApiError } from '../services/api'
import { useCountdown } from '../hooks/useCountdown'
import styles from './UrlShortener.module.css'

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
    }
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      className={`${styles.copyBtn} ${copied ? styles.copyBtnSuccess : ''}`}
      aria-label="Copy short URL to clipboard"
    >
      {copied ? (
        <>
          <CheckIcon /> Copied
        </>
      ) : (
        <>
          <CopyIcon /> Copy
        </>
      )}
    </button>
  )
}

function ResultCard({ result }) {
  const formattedExpiry = result.expires_at
    ? new Date(result.expires_at).toLocaleString(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
      })
    : null

  return (
    <div className={styles.resultCard} role="status" aria-live="polite">
      <div className={styles.resultHeader}>
        <div className={styles.resultStatus}>
          <span className={styles.successDot} aria-hidden="true" />
          <span className={styles.resultLabel}>Link ready</span>
        </div>
      </div>

      {/* Signature element: the glowing alias pill */}
      <div className={styles.aliasPill}>
        <span className={styles.aliasBase}>Alias: /</span>
        <span className={styles.aliasCode}>{result.alias}</span>
      </div>

      <div className={styles.resultActions}>
        <a
          href={result.short_url}
          target="_blank"
          rel="noopener noreferrer"
          className={styles.shortUrl}
        >
          {result.short_url}
        </a>
        <CopyButton text={result.short_url} />
      </div>

      <p className={styles.originalUrl} title={result.original_url}>
        ↳ {result.original_url}
      </p>

      {formattedExpiry && (
        <div className={styles.expiryPill} title={`Expires ${formattedExpiry}`}>
          <ClockIcon aria-hidden="true" /> Expires {formattedExpiry}
        </div>
      )}
    </div>
  )
}

function RateLimitBanner({ secondsLeft }) {
  const mins = Math.floor(secondsLeft / 60)
  const secs = secondsLeft % 60
  const display = mins > 0
    ? `${mins}:${String(secs).padStart(2, '0')}`
    : `${secs}s`

  const progress = Math.min((secondsLeft / 60) * 100, 100)

  return (
    <div className={styles.rateLimitBanner} role="alert" aria-live="assertive">
      <div className={styles.rateLimitHeader}>
        <TimerIcon className={styles.timerIcon} aria-hidden="true" />
        <strong>Slow down — limit reached</strong>
      </div>
      <p className={styles.rateLimitMsg}>
        You've shortened 5 URLs in the last minute. Submissions unlock in{' '}
        <span className={styles.countdown}>{display}</span>.
      </p>
      <div className={styles.progressTrack} role="progressbar" aria-valuenow={secondsLeft} aria-label="Cooldown timer">
        <div
          className={styles.progressBar}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  )
}

// Main component
export default function UrlShortener({ onSuccess }) {
  const [url, setUrl]         = useState('')
  const [result, setResult]   = useState(null)
  const [customAlias, setCustomAlias] = useState("");
  const [aliasError, setAliasError] = useState("");
  const [error, setError]     = useState(null)
  const [expiresAt, setExpiresAt] = useState('')
  const [loading, setLoading] = useState(false)

  const { secondsLeft, start: startCountdown, isActive: isRateLimited } = useCountdown(0)

  const canSubmit = !loading && !isRateLimited && url.trim().length > 0

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!canSubmit) return

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const isoExpiry = expiresAt ? new Date(expiresAt).toISOString() : undefined
      const data = await shortenUrl(url.trim(), customAlias.trim(), isoExpiry)
      setResult(data)
      setUrl('')           
      setCustomAlias('')     
      setExpiresAt('')      
      onSuccess?.(data)
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 429) {
          const retryAfter = err.data?.retry_after_seconds ?? 60
          startCountdown(retryAfter)
        } else if (err.status === 409) {
          setAliasError(err.message)
        } else {
          setError(err.message)
        }
      } else {
        setError('Could not reach the server. Check your connection and try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className={styles.wrapper}>
      <header className={styles.header}>
        <h1 className={styles.title}>
          <span className={styles.titleAccent}>snip.</span>
        </h1>
        <p className={styles.subtitle}>
          Paste a long URL. Get a link that fits anywhere.
        </p>
      </header>

      <form onSubmit={handleSubmit} className={styles.form} noValidate>
        <div className={styles.inputRow}>
          <div className={`${styles.inputWrap} ${isRateLimited ? styles.inputDisabled : ''}`}>
            <LinkIcon className={styles.inputIcon} aria-hidden="true" />
            <input
              type="url"
              className={styles.input}
              placeholder="https://your-very-long-url.com/goes/here"
              value={url}
              onChange={(e) => {
                setUrl(e.target.value)
                if (error) setError(null)
                if (result) setResult(null)
              }}
              disabled={isRateLimited || loading}
              aria-label="Long URL to shorten"
              aria-describedby={error ? 'url-error' : undefined}
              autoComplete="url"
              spellCheck="false"
            />
          </div>

          <button
            type="submit"
            className={styles.submitBtn}
            disabled={!canSubmit}
            aria-busy={loading}
          >
            {loading ? (
              <>
                <Spinner className={styles.spinner} aria-hidden="true" />
                Shortening…
              </>
            ) : (
              'Shorten'
            )}
          </button>
        </div>

        <div className={styles.optionsRow}>
          <div className={styles.fieldGroup}>
            <label htmlFor="alias-input" className={styles.fieldLabel}>
              Custom alias <span className={styles.optionalTag}>(optional)</span>
            </label>
            <div className={styles.aliasFieldWrap}>
              <span className={styles.aliasSeparator} aria-hidden="true">/</span>
              <input
                id="alias-input"
                type="text"
                className={styles.aliasInput}
                placeholder="e.g. alias1"
                value={customAlias}
                onChange={(e) => {
                  setCustomAlias(e.target.value)
                  if (aliasError) setAliasError(null)
                }}
                disabled={isRateLimited || loading}
                maxLength={6}
              />
            </div>
          </div>

          <div className={styles.fieldGroup}>
            <label htmlFor="expiry-input" className={styles.fieldLabel}>
              Expires <span className={styles.optionalTag}>(optional)</span>
            </label>
            <div className={`${styles.expiryWrap} ${isRateLimited ? styles.inputDisabled : ''}`}>
              <ClockIcon className={styles.inputIcon} />
              <input
                id="expiry-input"
                type="datetime-local"
                className={styles.expiryInput}
                value={expiresAt}
                onChange={(e) => setExpiresAt(e.target.value)}
                min={new Date().toISOString().slice(0, 16)}
                disabled={isRateLimited || loading}
              />
            </div>
          </div>
        </div>

        {aliasError && (
          <p className={styles.errorMsg} role="alert">
            <ErrorIcon aria-hidden="true" /> {aliasError}
          </p>
        )}

        {error && (
          <p id="url-error" className={styles.errorMsg} role="alert">
            <ErrorIcon aria-hidden="true" /> {error}
          </p>
        )}
      </form>

      {isRateLimited && <RateLimitBanner secondsLeft={secondsLeft} />}

      {result && !isRateLimited && <ResultCard result={result} />}
    </section>
  )
}

function LinkIcon({ className }) {
  return (
    <svg className={className} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
    </svg>
  )
}

function CopyIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="20 6 9 17 4 12"/>
    </svg>
  )
}

function TimerIcon({ className }) {
  return (
    <svg className={className} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="9"/>
      <polyline points="12 6 12 12 16 14"/>
    </svg>
  )
}

function ClockIcon({ className }) {
  return (
    <svg className={className} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10"/>
      <polyline points="12 6 12 12 16 14"/>
    </svg>
  )
}

function ErrorIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{display:'inline',verticalAlign:'middle',marginRight:'4px'}}>
      <circle cx="12" cy="12" r="10"/>
      <line x1="12" y1="8" x2="12" y2="12"/>
      <line x1="12" y1="16" x2="12.01" y2="16"/>
    </svg>
  )
}

function Spinner({ className }) {
  return (
    <svg className={className} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
      <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
    </svg>
  )
}
