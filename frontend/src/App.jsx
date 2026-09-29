import React, { useState } from 'react'
import { api, useFetch } from './api.js'
import { useHashRoute, parseRoute, href } from './router.js'
import IngestPage from './pages/IngestPage.jsx'
import AuditPage from './pages/AuditPage.jsx'
import { usePeraWallet } from './wallet.js'
import X402VerificationModal from './components/X402VerificationModal.jsx'

function Logo() {
  return (
    <a href={href.audit()} className="flex items-center gap-3 group focus-visible:outline-none">
      <div className="flex h-8 w-8 items-center justify-center rounded border border-[#1A2438] bg-[#0E1420] text-sky-400 group-hover:border-sky-500/60 transition">
        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <polyline points="16 18 22 12 16 6" />
          <polyline points="8 6 2 12 8 18" />
          <line x1="12" y1="2" x2="12" y2="22" strokeDasharray="2 2" />
        </svg>
      </div>
      <div className="leading-tight">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-black tracking-widest text-slate-100">CODIT</span>
          <span className="rounded border border-[#1A2438] bg-[#111827] px-1.5 py-0.2 font-mono text-[9px] font-bold text-sky-400">
            v2.0
          </span>
        </div>
        <div className="font-mono text-[10px] text-slate-500 tracking-tight uppercase">Static Codebase Oracle</div>
      </div>
    </a>
  )
}

function ModePill() {
  const { data, error } = useFetch(() => api.health(), [])
  let cls = 'border-[#1A2438] bg-[#0E1420] text-slate-400'
  let dot = 'bg-slate-500'
  let label = 'CONNECTING'
  if (error) {
    cls = 'border-[#5C1220] bg-[#1E0A10] text-[#F43F5E]'
    dot = 'bg-[#F43F5E]'
    label = 'GRAPH OFFLINE'
  } else if (data?.mode === 'cognodb') {
    cls = 'border-emerald-900/60 bg-emerald-950/40 text-emerald-400'
    dot = 'bg-emerald-400'
    label = 'BOLT / COGNODB'
  } else if (data?.mode === 'demo') {
    cls = 'border-amber-900/60 bg-amber-950/40 text-amber-400'
    dot = 'bg-amber-400'
    label = data?.is_custom ? 'CUSTOM GRAPH' : 'DEMO GRAPH'
  }
  return (
    <span
      title={data?.mode === 'demo'
        ? 'In-memory graph engine actively modeling ingested repository.'
        : 'Live openCypher property graph connected to CognoDB/Neo4j via official Bolt driver.'}
      className={`hidden md:inline-flex items-center gap-1.5 rounded border px-2 py-0.5 font-mono text-[10px] font-semibold tracking-wider ${cls}`}
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
      <span className="hidden sm:inline-flex items-center gap-1.5 rounded border border-[#1A2438] bg-[#0E1420] px-2 py-0.5 font-mono text-[10px] text-slate-400">
        <span className="text-slate-500">TARGET:</span> DEMO SYSTEM
      </span>
    )
  }
  const cleanTarget = data.active_target.replace('https://github.com/', '')
  return (
    <span
      title={`Active Target: ${data.active_target} (${data.file_count} files)`}
      className="hidden sm:inline-flex items-center gap-1.5 rounded border border-sky-900/60 bg-sky-950/40 px-2 py-0.5 font-mono text-[10px] text-sky-300"
    >
      <span className="h-1.5 w-1.5 rounded-full bg-sky-400 animate-pulse" />
      <span className="text-sky-400/80">TARGET:</span> {cleanTarget}
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
    <div className="min-h-screen bg-[#080B11] text-slate-200 font-sans flex flex-col justify-between selection:bg-sky-500/30 selection:text-sky-200">
      {/* Precision Instrument Top Flight-Bar */}
      <header className="sticky top-0 z-40 border-b border-[#1A2438] bg-[#080B11]/95 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2 px-3 py-2 sm:px-6 sm:py-2.5">
          <Logo />

          {/* Two-Pillar Instrument Mode Switcher */}
          <nav aria-label="Primary Navigation" className="flex items-center gap-1 bg-[#0E1420] p-0.5 sm:p-1 rounded border border-[#1A2438]">
            <a
              href="#/audit"
              className={`rounded px-2 sm:px-3 py-1 font-mono text-[11px] sm:text-xs font-bold tracking-wider uppercase transition ${
                route.name === 'audit'
                  ? 'bg-sky-500 text-slate-950 shadow-sm'
                  : 'text-slate-400 hover:text-slate-100 hover:bg-[#111827]'
              }`}
            >
              [1] Audit Cockpit
            </a>
            <a
              href="#/ingest"
              className={`rounded px-2 sm:px-3 py-1 font-mono text-[11px] sm:text-xs font-bold tracking-wider uppercase transition ${
                route.name === 'ingest'
                  ? 'bg-sky-500 text-slate-950 shadow-sm'
                  : 'text-slate-400 hover:text-slate-100 hover:bg-[#111827]'
              }`}
            >
              [2] Ingest Repo
            </a>
          </nav>

          {/* Right Status & Actions */}
          <div className="flex items-center gap-2">
            <CodebaseTargetPill />
            <ModePill />
            
            <button
              onClick={() => setShowX402Modal(true)}
              data-testid="x402-settle-btn"
              className={`inline-flex items-center gap-1.5 rounded border px-2 sm:px-2.5 py-1 font-mono text-[10px] font-bold tracking-wider uppercase transition ${
                wallet.connected
                  ? 'border-emerald-800 bg-emerald-950/30 text-emerald-300 hover:bg-emerald-950/60'
                  : 'border-amber-800 bg-amber-950/30 text-amber-300 hover:bg-amber-950/60'
              }`}
              title="On-Chain Settlement via Algorand x402"
            >
              <span className={`h-1.5 w-1.5 rounded-full ${wallet.connected ? 'bg-emerald-400' : 'bg-amber-400'}`} />
              <span className="hidden xs:inline">{wallet.connected ? shortAddress : 'x402 Settle'}</span>
              <span className="xs:hidden">{wallet.connected ? 'Connected' : 'x402'}</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="relative mx-auto max-w-7xl px-4 pb-16 pt-6 sm:px-6 flex-1 w-full">
        {page}
      </main>

      {/* Flight-Instrument Footer */}
      <footer className="border-t border-[#1A2438] py-4 bg-[#080B11]">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 text-xs text-slate-500 sm:px-6">
          <div className="flex items-center gap-2 font-mono text-[11px]">
            <span className="font-bold text-slate-400">CODIT ENGINE</span>
            <span className="text-[#1A2438]">|</span>
            <span>Static Codebase Intelligence & Production-Readiness Oracle</span>
          </div>
          <div className="font-mono text-[10px] text-slate-500 flex items-center gap-3">
            <span>FastAPI</span>
            <span className="text-[#1A2438]">•</span>
            <span>openCypher</span>
            <span className="text-[#1A2438]">•</span>
            <span>ONNX Runtime</span>
            <span className="text-[#1A2438]">•</span>
            <span>Tree-sitter</span>
            <span className="text-[#1A2438]">•</span>
            <span>Algorand x402</span>
          </div>
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
