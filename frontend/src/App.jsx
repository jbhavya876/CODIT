import React, { useState } from 'react'
import { api, useFetch } from './api.js'
import { useHashRoute, parseRoute, href } from './router.js'
import IngestPage from './pages/IngestPage.jsx'
import AuditPage from './pages/AuditPage.jsx'
import { usePeraWallet } from './wallet.js'
import X402VerificationModal from './components/X402VerificationModal.jsx'

function Logo() {
  return (
    <a href={href.audit()} className="flex items-center gap-3 group">
      <div className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-sky-500/20 to-indigo-500/20 border border-sky-500/40 shadow-lg shadow-sky-500/10 group-hover:border-sky-400 transition">
        <svg viewBox="0 0 32 32" className="h-5 w-5" aria-hidden>
          <circle cx="16" cy="7" r="3.5" fill="#38bdf8" />
          <circle cx="7" cy="24" r="3.5" fill="#34d399" />
          <circle cx="25" cy="24" r="3.5" fill="#fbbf24" />
          <path d="M16 11 8.5 21M16 11l7.5 10M11 24h10" stroke="#64748b" strokeWidth="1.8" fill="none" />
        </svg>
      </div>
      <div className="leading-tight">
        <div className="text-base font-black tracking-wider text-slate-50 flex items-center gap-2">
          <span className="tracking-widest">CODIT</span>
          <span className="rounded bg-sky-500/20 text-sky-400 text-[10px] font-mono px-1.5 py-0.5 border border-sky-500/30 font-bold">
            v2.0
          </span>
        </div>
        <div className="text-[11px] text-slate-400 font-medium">Intelligent Codebase Audit Oracle</div>
      </div>
    </a>
  )
}

function ModePill() {
  const { data, error } = useFetch(() => api.health(), [])
  let cls = 'border-slate-800 bg-slate-900/60 text-slate-400'
  let dot = 'bg-slate-500'
  let label = 'connecting…'
  if (error) {
    cls = 'border-rose-500/40 bg-rose-950/20 text-rose-300'
    dot = 'bg-rose-400'
    label = 'graph offline'
  } else if (data?.mode === 'cognodb') {
    cls = 'border-emerald-500/40 bg-emerald-950/20 text-emerald-300'
    dot = 'bg-emerald-400'
    label = 'CognoDB Bolt'
  } else if (data?.mode === 'demo') {
    cls = 'border-amber-500/40 bg-amber-950/20 text-amber-300'
    dot = 'bg-amber-400'
    label = data?.is_custom ? 'Active Ingest' : 'Demo Graph'
  }
  return (
    <span
      title={data?.mode === 'demo'
        ? 'In-memory graph engine actively modeling ingested repository.'
        : 'Live openCypher property graph connected to CognoDB/Neo4j via official Bolt driver.'}
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-mono font-medium ${cls}`}
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
        <span className="text-slate-500">Target:</span> Demo System
      </span>
    )
  }
  const cleanTarget = data.active_target.replace('https://github.com/', '')
  return (
    <span
      title={`Active Target: ${data.active_target} (${data.file_count} files)`}
      className="hidden sm:inline-flex items-center gap-1.5 rounded-full border border-sky-500/40 bg-sky-950/40 px-2.5 py-1 text-[11px] font-mono text-sky-300 shadow-sm shadow-sky-500/10"
    >
      <span className="h-1.5 w-1.5 rounded-full bg-sky-400 animate-pulse" />
      <span className="text-sky-400/80">Target:</span> {cleanTarget}
      <span className="rounded bg-sky-900/60 px-1 py-0.2 text-[9px] text-sky-200">{data.file_count} files</span>
    </span>
  )
}

export default function App() {
  const hash = useHashRoute()
  const route = parseRoute(hash)
  const [showX402Modal, setShowX402Modal] = useState(false)
  const wallet = usePeraWallet()

  const shortAddress = wallet.accountAddress
    ? `${wallet.accountAddress.slice(0, 5)}…${wallet.accountAddress.slice(-4)}`
    : null

  let page
  switch (route.name) {
    case 'ingest':
      page = <IngestPage />
      break
    case 'audit':
    default:
      page = <AuditPage />
      break
  }

  return (
    <div className="min-h-screen bg-[#060911] text-slate-100 font-sans flex flex-col justify-between selection:bg-sky-500/30 selection:text-sky-200">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(80%_50%_at_50%_-10%,rgba(56,189,248,0.06),transparent)]" />
      
      {/* Precision Top Navbar */}
      <header className="sticky top-0 z-40 border-b border-slate-800/80 bg-[#060911]/85 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <Logo />

          {/* Center Two-Pillar Switcher */}
          <nav className="flex items-center gap-1 text-sm bg-slate-950/70 p-1 rounded-xl border border-slate-800/80">
            <a
              href="#/audit"
              className={`rounded-lg px-3.5 py-1.5 text-xs font-bold transition ${
                route.name === 'audit'
                  ? 'bg-sky-500 text-slate-950 shadow-md shadow-sky-500/20'
                  : 'text-slate-400 hover:text-slate-100 hover:bg-slate-900/60'
              }`}
            >
              Audit Cockpit
            </a>
            <a
              href="#/ingest"
              className={`rounded-lg px-3.5 py-1.5 text-xs font-bold transition ${
                route.name === 'ingest'
                  ? 'bg-sky-500 text-slate-950 shadow-md shadow-sky-500/20'
                  : 'text-slate-400 hover:text-slate-100 hover:bg-slate-900/60'
              }`}
            >
              Ingest Repo
            </a>
          </nav>

          {/* Right Status & Actions */}
          <div className="flex items-center gap-2">
            <CodebaseTargetPill />
            <ModePill />
            
            <button
              onClick={() => setShowX402Modal(true)}
              className={`hidden sm:inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[11px] font-mono font-semibold transition ${
                wallet.connected
                  ? 'border-emerald-500/40 bg-emerald-950/20 text-emerald-300 hover:bg-emerald-950/40'
                  : 'border-amber-500/40 bg-amber-950/20 text-amber-300 hover:bg-amber-950/40'
              }`}
              title="On-Chain Settlement via Algorand x402"
            >
              <span className={`h-1.5 w-1.5 rounded-full ${wallet.connected ? 'bg-emerald-400' : 'bg-amber-400'}`} />
              {wallet.connected ? shortAddress : 'x402 Settle'}
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="relative mx-auto max-w-7xl px-4 pb-16 pt-6 sm:px-6 flex-1 w-full">
        {page}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 py-6 bg-[#060911]/90">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2 px-4 text-xs text-slate-500 sm:px-6">
          <span>CODIT · Production-Readiness Oracle & Static Codebase Intelligence</span>
          <span className="font-mono text-[11px] text-slate-600">FastAPI · openCypher · ONNX Runtime · Tree-sitter · SHAP</span>
        </div>
      </footer>

      {/* Global x402 Modal */}
      <X402VerificationModal
        isOpen={showX402Modal}
        onClose={() => setShowX402Modal(false)}
      />
    </div>
  )
}
