import React from 'react'
import { api, useFetch } from './api.js'
import { useHashRoute, parseRoute, href } from './router.js'
import Dashboard from './pages/Dashboard.jsx'
import ComponentPage from './pages/Component.jsx'
import ImpactPage from './pages/Impact.jsx'
import PathPage from './pages/Path.jsx'
import IngestPage from './pages/IngestPage.jsx'
import AuditPage from './pages/AuditPage.jsx'

function Logo() {
  return (
    <a href={href.audit()} className="flex items-center gap-3">
      <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden>
        <circle cx="16" cy="7" r="4" fill="#38bdf8" />
        <circle cx="7" cy="24" r="4" fill="#34d399" />
        <circle cx="25" cy="24" r="4" fill="#fbbf24" />
        <path d="M16 11 8.5 21M16 11l7.5 10M11 24h10" stroke="#64748b" strokeWidth="1.6" fill="none" />
      </svg>
      <div className="leading-tight">
        <div className="text-base font-extrabold tracking-wider text-slate-50 flex items-center gap-2">
          <span className="tracking-widest">CODIT</span>
          <span className="rounded bg-sky-500/20 text-sky-400 text-[10px] font-mono px-1.5 py-0.5 border border-sky-500/30 font-semibold">v2.0</span>
        </div>
        <div className="text-[11px] text-slate-400">Intelligent Codebase Audit & Architecture Platform</div>
      </div>
    </a>
  )
}

function ModePill() {
  const { data, error } = useFetch(() => api.health(), [])
  let cls = 'border-slate-600 text-slate-400'
  let dot = 'bg-slate-500'
  let label = 'connecting…'
  if (error) {
    cls = 'border-rose-500/50 text-rose-300'
    dot = 'bg-rose-400'
    label = 'graph db unavailable'
  } else if (data?.mode === 'cognodb') {
    cls = 'border-emerald-500/40 text-emerald-300'
    dot = 'bg-emerald-400'
    label = 'CognoDB connected'
  } else if (data?.mode === 'demo') {
    cls = 'border-amber-500/40 text-amber-300'
    dot = 'bg-amber-400'
    label = data?.is_custom ? 'Active Ingested Graph' : 'Embedded Demo Graph'
  }
  return (
    <span
      title={data?.mode === 'demo'
        ? 'In-memory graph backend actively analyzing ingested repository graph.'
        : 'Live data served from your CognoDB instance via official Neo4j Bolt driver.'}
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] font-medium ${cls}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {label}
    </span>
  )
}

function CodebaseTargetPill() {
  const { data } = useFetch(() => api.ingestStatus(), [])
  if (!data?.active_target || data.active_target === 'demo') {
    return (
      <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full border border-slate-800 bg-slate-900/80 px-2.5 py-1 text-[11px] font-mono text-slate-400">
        <span className="text-slate-500">Target:</span> Demo Codebase
      </span>
    )
  }
  const cleanTarget = data.active_target.replace('https://github.com/', '')
  return (
    <span
      title={`Active Ingested Codebase: ${data.active_target} (${data.file_count} files)`}
      className="hidden sm:inline-flex items-center gap-1.5 rounded-full border border-sky-500/40 bg-sky-950/40 px-2.5 py-1 text-[11px] font-mono text-sky-300 shadow-sm shadow-sky-500/10"
    >
      <span className="h-1.5 w-1.5 rounded-full bg-sky-400 animate-pulse" />
      <span className="text-sky-400/70">Target:</span> {cleanTarget}
      <span className="rounded bg-sky-900/60 px-1 py-0.2 text-[9px] text-sky-200">{data.file_count} files</span>
    </span>
  )
}

export default function App() {
  const hash = useHashRoute()
  const route = parseRoute(hash)

  let page
  switch (route.name) {
    case 'audit':
      page = <AuditPage />
      break
    case 'ingest':
      page = <IngestPage />
      break
    case 'dashboard':
      page = <Dashboard />
      break
    case 'component':
      page = <ComponentPage key={route.id} id={route.id} />
      break
    case 'impact':
      page = <ImpactPage key={route.id} id={route.id} />
      break
    case 'path':
      page = <PathPage key={`${route.from}-${route.to}`} from={route.from} to={route.to} />
      break
    default:
      page = <AuditPage />
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(80%_50%_at_50%_-10%,rgba(56,189,248,0.08),transparent)]" />
      <header className="sticky top-0 z-40 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <Logo />
          <nav className="flex items-center gap-1 text-sm">
            <a
              href="#/audit"
              className={`rounded-lg px-3 py-1.5 transition ${
                route.name === 'audit'
                  ? 'bg-slate-800/90 text-sky-400 font-medium'
                  : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-100'
              }`}
            >
              Audit Cockpit
            </a>
            <a
              href="#/ingest"
              className={`rounded-lg px-3 py-1.5 transition ${
                route.name === 'ingest'
                  ? 'bg-slate-800/90 text-sky-400 font-medium'
                  : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-100'
              }`}
            >
              Ingest Repo
            </a>
            <a
              href="#/"
              className={`rounded-lg px-3 py-1.5 transition ${
                route.name === 'dashboard'
                  ? 'bg-slate-800/90 text-sky-400 font-medium'
                  : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-100'
              }`}
            >
              Graph Explorer
            </a>
            <a
              href="#/path"
              className={`rounded-lg px-3 py-1.5 transition ${
                route.name === 'path'
                  ? 'bg-slate-800/90 text-sky-400 font-medium'
                  : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-100'
              }`}
            >
              Path Finder
            </a>
            <span className="mx-2 hidden h-4 w-px bg-slate-800 sm:block" />
            <CodebaseTargetPill />
            <ModePill />
          </nav>
        </div>
      </header>

      <main className="relative mx-auto max-w-7xl px-4 pb-16 pt-6 sm:px-6">{page}</main>

      <footer className="border-t border-slate-800/80 py-6">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2 px-4 text-xs text-slate-500 sm:px-6">
          <span>CODIT · Intelligent Codebase Audit & Architecture Intelligence Platform</span>
          <span className="font-mono text-[11px] text-slate-600">FastAPI · Neo4j / CognoDB Bolt · Tree-sitter · Claude Roadmap</span>
        </div>
      </footer>
    </div>
  )
}
