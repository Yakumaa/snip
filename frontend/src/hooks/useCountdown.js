import { useState, useEffect, useRef } from 'react'

/**
 * useCountdown — starts a decrementing second-by-second timer.
 *
 * @param {number} initialSeconds  Starting value (0 = inactive).
 * @returns {{ secondsLeft: number, start: (n: number) => void, isActive: boolean }}
 *
 * Usage:
 *   const { secondsLeft, start, isActive } = useCountdown(0)
 *   // When a 429 arrives:
 *   start(retryAfterSeconds)
 *   // secondsLeft ticks down to 0, then isActive becomes false.
 */
export function useCountdown(initialSeconds = 0) {
  const [secondsLeft, setSecondsLeft] = useState(initialSeconds)
  const intervalRef = useRef(null)

  const clear = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }

  const start = (seconds) => {
    clear()
    setSecondsLeft(seconds)

    if (seconds <= 0) return

    intervalRef.current = setInterval(() => {
      setSecondsLeft((prev) => {
        if (prev <= 1) {
          clear()
          return 0
        }
        return prev - 1
      })
    }, 1000)
  }

  useEffect(() => () => clear(), [])

  return {
    secondsLeft,
    start,
    isActive: secondsLeft > 0,
  }
}
