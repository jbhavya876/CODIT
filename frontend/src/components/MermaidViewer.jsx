import React, { useEffect, useRef, useState } from 'react'
import mermaid from 'mermaid'

// Initialize Mermaid once with sleek dark cyber theme
mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  securityLevel: 'loose',
  fontFamily: 'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  themeVariables: {
    darkMode: true,
    background: '#020617',
    primaryColor: '#0ea5e9',
    primaryTextColor: '#f8fafc',
    primaryBorderColor: '#38bdf8',
    lineColor: '#64748b',
    secondaryColor: '#1e293b',
    tertiaryColor: '#0f172a',
  },
})

export default function MermaidViewer({ chart, code, className = '' }) {
  const containerRef = useRef(null)
  const [svgContent, setSvgContent] = useState('')
  const [error, setError] = useState(null)
  const [showRaw, setShowRaw] = useState(false)
  const [copied, setCopied] = useState(false)
  const [loading, setLoading] = useState(false)

  const diagramCode = (chart || code || '').trim()

  useEffect(() => {
    let active = true
    if (!diagramCode) {
      setSvgContent('')
      setError(null)
      return
    }

    setLoading(true)
    setError(null)

    const renderChart = async () => {
      try {
        const id = `mmd_${Math.random().toString(36).substring(2, 9)}`
        // Clean out any stale temp elements created by mermaid if any
        const existingEl = document.getElementById(id)
        if (existingEl) existingEl.remove()

        const { svg } = await mermaid.render(id, diagramCode)
        if (active) {
          setSvgContent(svg)
          setError(null)
          setLoading(false)
        }
      } catch (err) {
        if (active) {
          console.warn('Mermaid render error:', err)
          setError(err.message || 'Failed to parse and render Mermaid diagram.')
          setLoading(false)
        }
      }
    }

    renderChart()

    return () => {
      active = false
    }
  }, [diagramCode])

  const handleCopy = () => {
    navigator.clipboard.writeText(diagramCode)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (!diagramCode) {
    return (
      <div className="rounded-xl border border-dashed border-slate-800 bg-slate-950/40 p-8 text-center text-xs text-slate-500">
        No diagram code generated for this component or architecture view.
      </div>
    )
  }

  return (
    <div className={`space-y-3 ${className}`}>
      {/* Top Diagram Controls */}
      <div className="flex items-center justify-between text-xs px-1">
        <div className="flex items-center gap-2 text-slate-400">
          <span className="inline-block h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="font-mono text-[11px]">Interactive SVG Diagram</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowRaw(!showRaw)}
            className="rounded px-2 py-1 text-[11px] font-mono text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
          >
            {showRaw ? 'Hide Raw Code' : 'View Raw Code'}
          </button>
          <button
            type="button"
            onClick={handleCopy}
            className="rounded bg-slate-800 px-2.5 py-1 text-[11px] font-medium text-slate-300 hover:bg-slate-700 transition"
          >
            {copied ? '✓ Copied' : '📋 Copy Source'}
          </button>
        </div>
      </div>

      {showRaw && (
        <pre className="rounded-xl border border-slate-800 bg-slate-950 p-4 font-mono text-[11px] text-slate-300 overflow-x-auto max-h-64 leading-relaxed">
          {diagramCode}
        </pre>
      )}

      {loading && (
        <div className="flex items-center justify-center p-12 text-center text-xs text-slate-400 gap-2">
          <div className="h-4 w-4 rounded-full border-2 border-sky-400 border-t-transparent animate-spin" />
          <span>Rendering Architecture Blueprint...</span>
        </div>
      )}

      {error ? (
        <div className="rounded-xl border border-rose-500/40 bg-rose-950/20 p-5 space-y-3">
          <div className="text-rose-400 text-xs font-semibold flex items-center gap-2">
            <span>⚠️</span> Mermaid Syntax Warning
          </div>
          <p className="text-[11px] text-slate-400">{error}</p>
          <pre className="rounded-lg bg-slate-950 p-3 font-mono text-[10px] text-slate-500 overflow-x-auto max-h-48">
            {diagramCode}
          </pre>
        </div>
      ) : (
        <div
          ref={containerRef}
          className="overflow-x-auto rounded-xl border border-slate-800/80 bg-slate-950/90 p-6 shadow-2xl flex justify-center items-center min-h-[220px]"
          dangerouslySetInnerHTML={{ __html: svgContent }}
        />
      )}
    </div>
  )
}
