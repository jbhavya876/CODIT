import React, { useState, useEffect } from 'react'
import { api, useFetch } from '../api.js'
import { useHashRoute, parseRoute, navigate, href } from '../router.js'
import GraphPathInspector from '../components/GraphPathInspector.jsx'
import X402VerificationModal from '../components/X402VerificationModal.jsx'
import GuardDrawer from '../components/ui/GuardDrawer.jsx'
import OverviewPanel from '../components/audit/OverviewPanel.jsx'
import ProcessTab from '../components/process/ProcessTab.jsx'
import LicensesTab from '../components/licenses/LicensesTab.jsx'
import ReportsTab from '../components/reports/ReportsTab.jsx'
import AttestTab from '../components/attest/AttestTab.jsx'
import { Printer, Moon, Sun, Sparkles, Shield } from 'lucide-react'

const SUB_TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'process', label: 'Process' },
  { id: 'licenses', label: 'Licenses' },
  { id: 'reports', label: 'Reports' },
  { id: 'attest', label: 'Attest' },
]

export default function AuditPage({ onOpenGuard }) {
  const hash = useHashRoute()
  const route = parseRoute(hash)

  const [goal, setGoal] = useState('production')
  const [analyzing, setAnalyzing] = useState(false)
  const [selectedComponentId, setSelectedComponentId] = useState('')
  const [showConstellation, setShowConstellation] = useState(false)
  const [isDossier, setIsDossier] = useState(false)
  const [guardOpen, setGuardOpen] = useState(false)
  const [showX402Modal, setShowX402Modal] = useState(false)

  const [inspectingComponentId, setInspectingComponentId] = useState(route.inspectId || null)
  const [inspectorTab, setInspectorTab] = useState(route.tab || 'deps')
  const [inspectorPathTo, setInspectorPathTo] = useState(route.pathTo || '')

  const { data: report, loading, error, refetch } = useFetch(() => api.getReport(), [route.auditId])
  const effectiveAuditId = route.auditId || report?.audit_id || ''

  const { data: auditStatus } = useFetch(
    () => (effectiveAuditId ? api.getAudit(effectiveAuditId) : Promise.resolve(null)),
    [effectiveAuditId]
  )
  const { data: processData } = useFetch(
    () => (effectiveAuditId ? api.getAuditProcess(effectiveAuditId) : Promise.resolve(null)),
    [effectiveAuditId]
  )
  const { data: licensesData } = useFetch(
    () => (effectiveAuditId ? api.getAuditLicenses(effectiveAuditId) : Promise.resolve(null)),
    [effectiveAuditId]
  )
  const { data: blastRadiusData } = useFetch(
    () => (selectedComponentId ? api.getBlastRadiusDiagram(selectedComponentId) : Promise.resolve(null)),
    [selectedComponentId]
  )

  useEffect(() => {
    setInspectingComponentId(route.inspectId || null)
    if (route.tab) setInspectorTab(route.tab)
    if (route.pathTo) setInspectorPathTo(route.pathTo)
  }, [route.inspectId, route.tab, route.pathTo])

  useEffect(() => {
    if (!selectedComponentId && report?.criticality_leaderboard?.length > 0) {
      const topComp = report.criticality_leaderboard[0]
      const topId = topComp.component?.id || topComp.id
      if (topId) setSelectedComponentId(topId)
    }
  }, [report, selectedComponentId])

  const handleRunAnalysis = async (selectedGoal) => {
    setAnalyzing(true)
    try {
      await api.runAnalysis(selectedGoal)
      await refetch()
    } catch (err) {
      alert('Analysis error: ' + (err.message || 'Failed to complete analysis'))
    } finally {
      setAnalyzing(false)
    }
  }

  const openInspector = (compId, tab = 'deps', to = '') => {
    setInspectingComponentId(compId)
    setInspectorTab(tab)
    setInspectorPathTo(to)
    const params = new URLSearchParams()
    if (compId) params.set('inspect', compId)
    if (tab && tab !== 'deps') params.set('tab', tab)
    if (to) params.set('to', to)
    window.location.hash = params.toString() ? `#/audit?${params.toString()}` : '#/audit'
  }

  const handleCloseInspector = () => {
    setInspectingComponentId(null)
    window.location.hash = '#/audit'
  }

  if (loading && !report) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[420px] text-center space-y-3 font-mono">
        <div className="h-10 w-10 rounded-lg border border-[#2A2E35] bg-[#15171B] flex items-center justify-center text-laser-lime text-xs font-bold">
          AST
        </div>
        <p className="text-sm font-bold uppercase tracking-wider text-slate-100">Loading Audit Cockpit...</p>
      </div>
    )
  }

  if (error && !report) {
    return (
      <div className="rounded-xl border border-[#5A1C16] bg-[#2A0E0B] p-8 text-center max-w-lg mx-auto space-y-4">
        <div className="text-rose-200 font-bold text-sm uppercase tracking-wider font-mono">No Active Audit Report</div>
        <p className="text-xs text-slate-300 font-sans">{error.message || 'No audit is active.'}</p>
        <a href="#/ingest" className="inline-block rounded-lg border border-laser-lime bg-laser-lime px-4 py-2 font-mono text-xs font-bold uppercase text-black">
          Ingest Codebase
        </a>
      </div>
    )
  }

  const scorecard = report.scorecard || {}
  const activeTab = route.auditTab || 'overview'

  return (
    <div className={isDossier ? 'bg-[#EFEAE0] text-[#101114] p-6 md:p-8 rounded-2xl border border-[#D8D2C5] shadow-2xl space-y-6' : 'space-y-6'}>
      {/* Cockpit Header */}
      <div className={`flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 border-b pb-5 ${isDossier ? 'border-[#D8D2C5]' : 'border-[#2A2E35]'}`}>
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className={`text-2xl sm:text-3xl font-serif font-normal tracking-tight ${isDossier ? 'text-[#101114]' : 'text-slate-50'}`}>
              Audit Cockpit
            </h1>
            <span className="inline-flex items-center gap-1.5 rounded border border-laser-lime/40 bg-laser-lime/10 px-2.5 py-0.5 text-xs font-mono font-bold uppercase text-laser-lime">
              {scorecard.phase || 'Prototype'}
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded border border-[#2A2E35] bg-[#15171B] text-slate-400">
              DETERMINISTIC
            </span>
          </div>
          <p className={`mt-1.5 text-xs flex flex-wrap items-center gap-x-2 font-mono ${isDossier ? 'text-[#575A65]' : 'text-slate-400'}`}>
            <span>Target: <strong className={isDossier ? 'text-black' : 'text-slate-200'}>{report.target_name}</strong></span>
            <span>|</span>
            <span>Report: <span>{report.report_id}</span></span>
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => (onOpenGuard ? onOpenGuard() : setGuardOpen(true))}
            data-testid="open-guard-drawer-btn"
            className="rounded-lg border border-[#2A2E35] bg-[#15171B] px-3 py-1.5 font-mono text-xs font-bold text-laser-lime hover:border-laser-lime flex items-center gap-1.5"
          >
            <Shield className="w-3.5 h-3.5" aria-hidden="true" />
            <span>Guard CLI</span>
          </button>

          <button
            type="button"
            onClick={() => setIsDossier(!isDossier)}
            className={`rounded-lg border px-3 py-1.5 font-mono text-xs font-bold uppercase transition flex items-center gap-1.5 ${
              isDossier ? 'border-[#101114] bg-[#101114] text-[#EFEAE0]' : 'border-laser-lime/60 bg-laser-lime/10 text-laser-lime'
            }`}
          >
            {isDossier ? <Moon className="w-3.5 h-3.5" /> : <Sun className="w-3.5 h-3.5" />}
            <span>{isDossier ? 'Chamber View' : 'Dossier View'}</span>
          </button>

          <button
            type="button"
            onClick={() => setShowConstellation(!showConstellation)}
            className="rounded-lg border border-[#2A2E35] bg-[#15171B] px-3 py-1.5 font-mono text-xs font-semibold text-slate-300 flex items-center gap-1.5"
          >
            <Sparkles className="w-3.5 h-3.5 text-laser-lime" aria-hidden="true" />
            <span>{showConstellation ? 'Hide Graph' : 'Living Graph'}</span>
          </button>

          <div className="inline-flex rounded-lg border border-[#2A2E35] bg-[#15171B] p-0.5 font-mono text-xs">
            <button
              type="button"
              onClick={() => { setGoal('mvp'); handleRunAnalysis('mvp') }}
              disabled={analyzing}
              className={`px-3 py-1 font-bold uppercase rounded ${goal === 'mvp' ? 'bg-laser-lime text-black' : 'text-slate-400'}`}
            >
              Goal: MVP
            </button>
            <button
              type="button"
              onClick={() => { setGoal('production'); handleRunAnalysis('production') }}
              disabled={analyzing}
              className={`px-3 py-1 font-bold uppercase rounded ${goal === 'production' ? 'bg-laser-lime text-black' : 'text-slate-400'}`}
            >
              Goal: Production
            </button>
          </div>

          <a href={api.getMarkdownReportUrl()} target="_blank" rel="noreferrer" className="rounded-lg border border-[#2A2E35] bg-[#15171B] px-3 py-1.5 font-mono text-xs text-slate-300">
            Markdown
          </a>
          <a href={api.getHtmlReportUrl()} target="_blank" rel="noreferrer" className="rounded-lg border border-laser-lime bg-laser-lime px-3 py-1.5 font-mono text-xs font-bold text-black flex items-center gap-1">
            <Printer className="w-3.5 h-3.5" aria-hidden="true" />
            <span>PDF / Print</span>
          </a>
          <button
            type="button"
            onClick={() => setShowX402Modal(true)}
            data-testid="onchain-proof-btn"
            className="rounded-lg border border-amber-800 bg-amber-950/30 px-3 py-1.5 font-mono text-xs font-bold text-[#FFB020]"
          >
            On-Chain Proof
          </button>
        </div>
      </div>

      {/* Sub-navigation Tabs inside Audit Cockpit */}
      <nav aria-label="Audit Cockpit Sections" className="flex border-b border-[#2A2E35] font-mono text-xs overflow-x-auto whitespace-nowrap gap-1">
        {SUB_TABS.map((t) => {
          const isActive = activeTab === t.id
          return (
            <button
              key={t.id}
              type="button"
              data-testid={`audit-subtab-${t.id}`}
              onClick={() => navigate(href.auditTab(t.id, effectiveAuditId))}
              className={`px-4 py-2 font-bold uppercase tracking-wider border-b-2 transition ${
                isActive ? 'border-laser-lime text-laser-lime bg-[#15171B]' : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              {t.label}
            </button>
          )
        })}
      </nav>

      {activeTab === 'overview' && (
        <OverviewPanel
          report={report}
          isDossier={isDossier}
          showConstellation={showConstellation}
          blastRadiusData={blastRadiusData}
          selectedComponentId={selectedComponentId}
          setSelectedComponentId={setSelectedComponentId}
          openInspector={openInspector}
        />
      )}
      {activeTab === 'process' && <ProcessTab processData={processData} findings={report.findings || []} />}
      {activeTab === 'licenses' && <LicensesTab licensesData={licensesData} />}
      {activeTab === 'reports' && <ReportsTab auditId={effectiveAuditId} onOpenPayment={() => setShowX402Modal(true)} />}
      {activeTab === 'attest' && <AttestTab auditStatus={auditStatus} />}

      {inspectingComponentId && (
        <GraphPathInspector
          componentId={inspectingComponentId}
          initialTab={inspectorTab}
          initialPathTo={inspectorPathTo}
          onClose={handleCloseInspector}
        />
      )}

      <X402VerificationModal isOpen={showX402Modal} onClose={() => setShowX402Modal(false)} />
      <GuardDrawer isOpen={guardOpen} onClose={() => setGuardOpen(false)} />
    </div>
  )
}
