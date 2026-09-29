import React, { useState } from 'react'
import { href } from '../router.js'

/** Shared visual language — two-channel severity metrology, AST citations, states. */

export const TYPE_META = {
  Service: { hex: '#38bdf8', text: 'text-sky-300', bg: 'bg-sky-400', border: 'border-sky-500/40' },
  Module: { hex: '#38bdf8', text: 'text-sky-300', bg: 'bg-sky-400', border: 'border-sky-500/40' },
  Database: { hex: '#34d399', text: 'text-emerald-300', bg: 'bg-emerald-400', border: 'border-emerald-500/40' },
  API: { hex: '#fbbf24', text: 'text-amber-300', bg: 'bg-amber-400', border: 'border-amber-500/40' },
  Library: { hex: '#a78bfa', text: 'text-violet-300', bg: 'bg-violet-400', border: 'border-violet-500/40' },
  Infrastructure: { hex: '#fb7185', text: 'text-rose-300', bg: 'bg-rose-400', border: 'border-rose-500/40' },
  Finding: { hex: '#f43f5e', text: 'text-rose-300', bg: 'bg-rose-400', border: 'border-rose-500/40' },
  Team: { hex: '#94a3b8', text: 'text-slate-300', bg: 'bg-slate-400', border: 'border-slate-500/40' },
}

export const REL_VERBS = {
  DEPENDS_ON: 'depends on',
  CALLS: 'calls',
  READS_FROM: 'reads from',
  WRITES_TO: 'writes to',
  USES: 'uses',
  DEPLOYED_ON: 'is deployed on',
  OWNED_BY: 'is owned by',
  IMPORTS: 'imports',
  FLAGGED_BY: 'flagged by',
}

export function Dot({ type, className = '' }) {
  const meta = TYPE_META[type] || TYPE_META.Team
  return <span className={`inline-block h-2 w-2 rounded-full ${meta.bg} ${className}`} />
}

export function TypeBadge({ type }) {
  const meta = TYPE_META[type] || TYPE_META.Team
  return (
    <span className={`inline-flex items-center gap-1.5 rounded border border-[#1A2438] bg-[#0E1420] px-2 py-0.5 text-[11px] font-mono ${meta.text}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${meta.bg}`} />
      {type}
    </span>
  )
}

export function RelBadge({ rel }) {
  return (
    <span className="rounded border border-[#1A2438] bg-[#111827] px-1.5 py-0.5 font-mono text-[10px] tracking-wide text-slate-400">
      {rel}
    </span>
  )
}

export function StatusPill({ status }) {
  const styles = {
    operational: 'text-emerald-400 border-emerald-900/60 bg-emerald-950/40',
    degraded: 'text-amber-400 border-amber-900/60 bg-amber-950/40',
    maintenance: 'text-slate-400 border-slate-800 bg-slate-900/60',
  }
  const dots = { operational: 'bg-emerald-400', degraded: 'bg-amber-400', maintenance: 'bg-slate-500' }
  const cls = styles[status] || styles.maintenance
  return (
    <span className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-[11px] font-mono uppercase tracking-wider ${cls}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dots[status] || dots.maintenance}`} />
      {status || 'unknown'}
    </span>
  )
}

/** Two-channel severity badge (Shape Glyph + Color + Text Label) */
export function CritBadge({ tier, size = 'sm' }) {
  const t = (tier || 'LOW').toUpperCase()
  let glyph = '●'
  let label = t
  let styleCls = 'text-sky-300 border-[#0C3852] bg-[#071927]'

  if (t === 'CRITICAL' || t === 'CRIT') {
    glyph = '◆'
    label = 'CRIT'
    styleCls = 'text-[#F43F5E] border-[#5C1220] bg-[#1E0A10]'
  } else if (t === 'HIGH') {
    glyph = '▲'
    label = 'HIGH'
    styleCls = 'text-[#FB923C] border-[#5C2805] bg-[#201205]'
  } else if (t === 'MEDIUM' || t === 'MED') {
    glyph = '■'
    label = 'MED'
    styleCls = 'text-[#FACC15] border-[#544405] bg-[#1D1805]'
  } else if (t === 'LOW') {
    glyph = '●'
    label = 'LOW'
    styleCls = 'text-[#38BDF8] border-[#0C3852] bg-[#071927]'
  } else if (t === 'INFO') {
    glyph = '○'
    label = 'INFO'
    styleCls = 'text-[#94A3B8] border-[#1E293B] bg-[#111827]'
  }

  const pad = size === 'xs' ? 'px-1.5 py-0.2 text-[10px]' : 'px-2 py-0.5 text-[11px]'

  return (
    <span
      className={`inline-flex items-center gap-1 rounded border font-mono font-bold tracking-wider ${pad} ${styleCls}`}
      title={`Severity: ${t}`}
    >
      <span aria-hidden="true" className="text-[10px] leading-none">{glyph}</span>
      <span>{label}</span>
    </span>
  )
}

/** 3-pip decoupled confidence metrology gauge */
export function ConfidenceGauge({ level = 'high', label = true }) {
  const norm = (level || 'high').toLowerCase()
  let pips = 3
  let title = 'Deterministic AST Proof (Tree-sitter syntactic node verification)'
  let color = 'text-emerald-400'

  if (norm === 'medium' || norm === 'med' || norm === 'heuristic') {
    pips = 2
    title = 'Graph Traversal Inference (Multi-hop reach & topological heuristic)'
    color = 'text-amber-400'
  } else if (norm === 'low' || norm === 'statistical' || norm === 'est') {
    pips = 1
    title = 'Statistical Estimation (ONNX fragility pattern correlation)'
    color = 'text-slate-400'
  }

  return (
    <span
      className={`inline-flex items-center gap-1 font-mono text-[11px] font-semibold ${color}`}
      title={title}
    >
      <span className="tracking-tighter font-bold">
        {pips === 3 && '[●●●]'}
        {pips === 2 && '[●●○]'}
        {pips === 1 && '[●○○]'}
      </span>
      {label && (
        <span className="text-[10px] text-slate-400 uppercase tracking-wider">
          {pips === 3 ? 'AST PROOF' : pips === 2 ? 'GRAPH HEUR' : 'ESTIMATE'}
        </span>
      )}
    </span>
  )
}

/** Monospaced AST Code Citation with interactive clipboard copy */
export function EvidenceCitation({ file, line, ruleId, onInspect }) {
  const [copied, setCopied] = useState(false)
  const citation = `${file}:${line ?? 1}`

  const handleCopy = (e) => {
    e.stopPropagation()
    navigator.clipboard.writeText(citation)
    setCopied(true)
    setTimeout(() => setCopied(false), 1800)
  }

  return (
    <div className="inline-flex items-center gap-1.5 font-mono text-xs text-slate-300">
      <code className="rounded bg-[#080B11] border border-[#1A2438] px-2 py-0.5 text-sky-300 font-semibold">
        {citation}
      </code>
      <button
        type="button"
        onClick={handleCopy}
        className="rounded border border-[#1A2438] bg-[#0E1420] px-1.5 py-0.5 text-[10px] text-slate-400 hover:text-slate-200 hover:border-slate-600 transition"
        title="Copy citation to clipboard"
      >
        {copied ? '✓ Copied' : 'Copy'}
      </button>
      {onInspect && (
        <button
          type="button"
          onClick={onInspect}
          className="rounded border border-[#0C3852] bg-[#071927] px-1.5 py-0.5 text-[10px] text-sky-400 hover:text-sky-200 hover:border-sky-500 transition font-semibold"
          title="Inspect file neighborhood in graph"
        >
          Inspect ↗
        </button>
      )}
    </div>
  )
}

export function Spinner({ label = 'Executing static analysis…' }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center" role="status">
      <div className="flex items-center gap-1.5 font-mono text-xs text-sky-400">
        <span className="inline-block h-2 w-2 bg-sky-400 animate-ping" />
        <span className="font-semibold uppercase tracking-widest text-[11px] text-slate-400">{label}</span>
      </div>
    </div>
  )
}

export function ErrorState({ error, onRetry }) {
  const isDb = error?.code === 'database_unavailable'
  return (
    <div className="mx-auto max-w-md rounded-xl border border-rose-900/60 bg-[#1E0A10] px-6 py-10 text-center">
      <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded border border-rose-700/60 bg-rose-950/40 text-rose-300 font-mono font-black text-sm">
        !
      </div>
      <h3 className="mb-1 text-sm font-bold text-rose-100 uppercase tracking-wider font-mono">
        {isDb ? 'Graph Database Unavailable' : 'Audit Pipeline Error'}
      </h3>
      <p className="mb-5 text-xs text-slate-300 leading-relaxed font-sans">
        {isDb ? 'CognoDB / openCypher Bolt socket connection could not be established.' : error?.message || 'Unexpected failure during static pass.'}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="rounded border border-[#1A2438] bg-[#0E1420] px-4 py-2 text-xs font-mono font-bold text-sky-300 transition hover:bg-slate-800"
        >
          Retry Diagnostic
        </button>
      )}
    </div>
  )
}

export function EmptyState({ icon, title, message, children }) {
  return (
    <div className="rounded-xl border border-[#1A2438] bg-[#0E1420]/60 px-6 py-10 text-center">
      <div className="mb-2 font-mono text-xl text-slate-500">{icon || '○'}</div>
      <h3 className="mb-1 text-xs font-bold uppercase tracking-wider font-mono text-slate-300">{title}</h3>
      {message && <p className="mx-auto max-w-sm text-xs text-slate-400 leading-relaxed font-sans">{message}</p>}
      {children}
    </div>
  )
}

export function Panel({ title, subtitle, actions, children, className = '' }) {
  return (
    <section className={`rounded-xl border border-[#1A2438] bg-[#0E1420] ${className}`}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 border-b border-[#1A2438] px-4 py-3">
          <div>
            <h2 className="text-xs font-bold uppercase tracking-wider font-mono text-slate-200">{title}</h2>
            {subtitle && <p className="mt-0.5 text-[11px] text-slate-400 font-sans">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  )
}

export function ComponentRow({ component, type, trailing, muted }) {
  const c = component
  return (
    <a
      href={href.component(c.id)}
      className="flex items-center justify-between gap-3 rounded border border-transparent px-3 py-2 transition hover:border-[#1A2438] hover:bg-[#111827]"
    >
      <div className="flex min-w-0 items-center gap-2.5">
        <Dot type={type || c.type} />
        <span className={`truncate font-mono text-xs ${muted ? 'text-slate-400' : 'text-slate-200 font-medium'}`}>{c.name}</span>
      </div>
      <div className="flex shrink-0 items-center gap-2">{trailing}</div>
    </a>
  )
}

export function BackLink({ to, label }) {
  return (
    <a href={to} className="mb-4 inline-flex items-center gap-1.5 font-mono text-xs text-slate-400 transition hover:text-sky-300">
      <span aria-hidden="true">←</span>
      {label}
    </a>
  )
}
