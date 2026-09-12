import React, { useEffect, useRef, useState } from 'react'

export default function MermaidViewer({ chart, className = '' }) {
  const containerRef = useRef(null)
  const [svgContent, setSvgContent] = useState('')
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    if (!chart) return

    const renderChart = async () => {
      try {
        if (!window.mermaid) {
          // Dynamically import if not already on window
          const m = await import('https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs')
          window.mermaid = m.default
          window.mermaid.initialize({ startOnLoad: false, theme: 'dark' })
        }
        const id = `mermaid_${Math.random().toString(36).substr(2, 9)}`
        const { svg } = await window.mermaid.render(id, chart)
        if (active) {
          setSvgContent(svg)
          setError(null)
        }
      } catch (err) {
        if (active) {
          console.warn('Mermaid render failure:', err)
          setError('Failed to render architecture diagram.')
        }
      }
    }

    renderChart()
    return () => {
      active = false
    }
  }, [chart])

  if (error) {
    return (
      <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4 text-center text-xs text-slate-400">
        {error}
        <pre className="mt-2 text-left font-mono text-[10px] text-slate-500 overflow-x-auto p-2 bg-slate-950 rounded">
          {chart}
        </pre>
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      className={`overflow-x-auto rounded-xl border border-slate-800/80 bg-slate-950/80 p-4 shadow-inner flex justify-center ${className}`}
      dangerouslySetInnerHTML={{ __html: svgContent }}
    />
  )
}
