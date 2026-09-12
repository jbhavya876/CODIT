import React from 'react'
import { href } from '../router.js'

/** Shared visual language — badges, states, typing metadata. */

export const TYPE_META = {
  Service: { hex: '#38bdf8', text: 'text-sky-300', bg: 'bg-sky-400' },
  Module: { hex: '#38bdf8', text: 'text-sky-300', bg: 'bg-sky-400' },
  Database: { hex: '#34d399', text: 'text-emerald-300', bg: 'bg-emerald-400' },
  API: { hex: '#fbbf24', text: 'text-amber-300', bg: 'bg-amber-400' },
  Library: { hex: '#a78bfa', text: 'text-violet-300', bg: 'bg-violet-400' },
  Infrastructure: { hex: '#fb7185', text: 'text-rose-300', bg: 'bg-rose-400' },
  Finding: { hex: '#f43f5e', text: 'text-rose-300', bg: 'bg-rose-400' },
  Team: { hex: '#94a3b8', text: 'text-slate-300', bg: 'bg-slate-400' },
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
  return <span className={`inline-block h-2.5 w-2.5 rounded-full ${meta.bg} ${className}`} />
}

export function TypeBadge({ type }) {
  const meta = TYPE_META[type] || TYPE_META.Team
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-md border border-slate-700/80 bg-slate-800/60 px-2 py-0.5 text-[11px] font-medium ${meta.text}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${meta.bg}`} />
      {type}
    </span>
  )
}

export function RelBadge({ rel }) {
  return (
    <span className="rounded border border-slate-700 bg-slate-800/70 px-1.5 py-0.5 font-mono text-[10px] tracking-wide text-slate-400">
      {rel}
    </span>
  )
}

export function StatusPill({ status }) {
  const styles = {
    operational: 'text-emerald-300 border-emerald-500/30 bg-emerald-500/10',
    degraded: 'text-amber-300 border-amber-500/30 bg-amber-500/10',
    maintenance: 'text-slate-300 border-slate-500/30 bg-slate-500/10',
  }
  const dots = { operational: 'bg-emerald-400', degraded: 'bg-amber-400', maintenance: 'bg-slate-400' }
  const cls = styles[status] || styles.maintenance
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium capitalize ${cls}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dots[status] || dots.maintenance}`} />
      {status || 'unknown'}
    </span>
  )
}

export function CritBadge({ tier }) {
  const styles = {
    HIGH: 'text-rose-300 border-rose-500/40 bg-rose-500/10',
    MEDIUM: 'text-amber-300 border-amber-500/40 bg-amber-500/10',
    LOW: 'text-slate-300 border-slate-600 bg-slate-800/60',
  }
  return (
    <span className={`rounded-md border px-2 py-0.5 text-[11px] font-bold tracking-wider ${styles[tier] || styles.LOW}`}>
      {tier}
    </span>
  )
}

export function Spinner({ label = 'Loading…' }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center" role="status">
      <div className="flex gap-1.5">
        <span className="dd-dot h-2 w-2 rounded-full bg-sky-400" />
        <span className="dd-dot h-2 w-2 rounded-full bg-sky-400" />
        <span className="dd-dot h-2 w-2 rounded-full bg-sky-400" />
      </div>
      <p className="text-sm text-slate-400">{label}</p>
    </div>
  )
}

export function ErrorState({ error, onRetry }) {
  const isDb = error?.code === 'database_unavailable'
  return (
    <div className="mx-auto max-w-md rounded-xl border border-rose-500/30 bg-rose-500/5 px-6 py-10 text-center">
      <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full border border-rose-500/40 bg-rose-500/10">
        <svg viewBox="0 0 24 24" className="h-6 w-6 text-rose-300" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
        </svg>
      </div>
      <h3 className="mb-1 text-base font-semibold text-slate-100">
        {isDb ? 'Unable to connect to the dependency database' : 'Something went wrong'}
      </h3>
      <p className="mb-5 text-sm text-slate-400">
        {isDb ? 'Please try again.' : error?.message || 'Please try again.'}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="rounded-lg bg-sky-500 px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-sky-400"
        >
          Retry
        </button>
      )}
    </div>
  )
}

export function EmptyState({ icon, title, message, children }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-700 bg-slate-900/40 px-6 py-10 text-center">
      <div className="mb-3 text-2xl">{icon || '○'}</div>
      <h3 className="mb-1 text-sm font-semibold text-slate-200">{title}</h3>
      {message && <p className="mx-auto max-w-sm text-sm text-slate-400">{message}</p>}
      {children}
    </div>
  )
}

export function Panel({ title, subtitle, actions, children, className = '' }) {
  return (
    <section className={`rounded-xl border border-slate-800 bg-slate-900/60 ${className}`}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 border-b border-slate-800 px-5 py-3.5">
          <div>
            <h2 className="text-sm font-semibold text-slate-100">{title}</h2>
            {subtitle && <p className="mt-0.5 text-xs text-slate-400">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      <div className="p-5">{children}</div>
    </section>
  )
}

export function ComponentRow({ component, type, trailing, muted }) {
  const c = component
  return (
    <a
      href={href.component(c.id)}
      className="flex items-center justify-between gap-3 rounded-lg border border-transparent px-3 py-2 transition hover:border-slate-700 hover:bg-slate-800/50"
    >
      <div className="flex min-w-0 items-center gap-3">
        <Dot type={type || c.type} />
        <span className={`truncate text-sm ${muted ? 'text-slate-400' : 'text-slate-200'}`}>{c.name}</span>
      </div>
      <div className="flex shrink-0 items-center gap-2">{trailing}</div>
    </a>
  )
}

export function BackLink({ to, label }) {
  return (
    <a href={to} className="mb-4 inline-flex items-center gap-1.5 text-sm text-slate-400 transition hover:text-sky-300">
      <svg viewBox="0 0 20 20" className="h-4 w-4" fill="currentColor">
        <path fillRule="evenodd" d="M17 10a.75.75 0 0 1-.75.75H5.61l4.22 3.87a.75.75 0 1 1-1.04 1.08l-5.5-5.038a.75.75 0 0 1 0-1.08l5.5-5.062a.75.75 0 0 1 1.04 1.08L5.61 9.25h10.64A.75.75 0 0 1 17 10Z" clipRule="evenodd" />
      </svg>
      {label}
    </a>
  )
}
