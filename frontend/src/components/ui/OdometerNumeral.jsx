import React, { useEffect, useState } from 'react'

/**
 * Animated rolling numeral with tabular figures and optional decimal precision
 */
export default function OdometerNumeral({
  value = 0,
  duration = 1200,
  decimals = 0,
  suffix = '',
  className = '',
}) {
  const [displayValue, setDisplayValue] = useState(0)

  useEffect(() => {
    // Check reduced motion preference
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setDisplayValue(value)
      return
    }

    let start = 0
    const end = parseFloat(value) || 0
    if (start === end) {
      setDisplayValue(end)
      return
    }

    const startTime = performance.now()
    let frameId

    const update = (now) => {
      const elapsed = now - startTime
      const progress = Math.min(elapsed / duration, 1)
      // Ease out cubic
      const ease = 1 - Math.pow(1 - progress, 3)
      const current = start + (end - start) * ease
      setDisplayValue(current)

      if (progress < 1) {
        frameId = requestAnimationFrame(update)
      }
    }

    frameId = requestAnimationFrame(update)
    return () => cancelAnimationFrame(frameId)
  }, [value, duration])

  return (
    <span className={`tabular-nums font-mono font-black ${className}`}>
      {decimals > 0 ? displayValue.toFixed(decimals) : Math.round(displayValue)}
      {suffix}
    </span>
  )
}
