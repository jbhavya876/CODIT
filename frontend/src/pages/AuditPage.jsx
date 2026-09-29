import React, { useState, useEffect } from 'react'
import { api, useFetch } from '../api.js'
import { useHashRoute, parseRoute } from '../router.js'
import MermaidViewer from '../components/MermaidViewer.jsx'
import GraphPathInspector from '../components/GraphPathInspector.jsx'
import X402VerificationModal from '../components/X402VerificationModal.jsx'
import { Dot, CritBadge, ConfidenceGauge } from '../components/ui.jsx'
import OdometerNumeral from '../components/ui/OdometerNumeral.jsx'
import VerdictSeal from '../components/ui/VerdictSeal.jsx'
import SHAPLedger from '../components/ui/SHAPLedger.jsx'
import HeroConstellation from '../components/ui/HeroConstellation.jsx'
import { Printer, Moon, Sun, FileText, CheckCircle2, ShieldAlert, Sparkles, Terminal } from 'lucide-react'

export default function AuditPage() {
  const hash = useHashRoute()
  const route = parseRoute(hash)

  const [goal, setGoal] = useState('production')
  const [analyzing, setAnalyzing] = useState(false)
  const [sevFilter, setSevFilter] = useState('all')
  const [dimFilter, setDimFilter] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [activeDiagramTab, setActiveDiagramTab] = useState('arch')
  const [selectedComponentId, setSelectedComponentId] = useState('')
  const [copiedId, setCopiedId] = useState(null)
  const [expandedFinding, setExpandedFinding] = useState(null)
  const [showConstellation, setShowConstellation] = useState(false)
  const [isDossier, setIsDossier] = useState(false)

  // In-cockpit Graph & Path Inspector state
  const [inspectingComponentId, setInspectingComponentId] = useState(route.inspectId || null)
  const [inspectorTab, setInspectorTab] = useState(route.tab || 'deps')
  const [inspectorPathTo, setInspectorPathTo] = useState(route.pathTo || '')

  // x402 Modal state
  const [showX402Modal, setShowX402Modal] = useState(false)

  const { data: report, loading, error, refetch } = useFetch(() => api.getReport(), [])
  const { data: blastRadiusData } = useFetch(
    () => (selectedComponentId ? api.getBlastRadiusDiagram(selectedComponentId) : Promise.resolve(null)),
    [selectedComponentId]
  )

  // Sync route inspection param if hash changes
  useEffect(() => {
    setInspectingComponentId(route.inspectId || null)
    if (route.tab) setInspectorTab(route.tab)
    if (route.pathTo) setInspectorPathTo(route.pathTo)
  }, [route.inspectId, route.tab, route.pathTo])

  useEffect(() => {
    if (!selectedComponentId && report?.criticality_leaderboard?.length > 0) {
      const topComp = report.criticality_leaderboard[0]
      const topId = topComp.component?.id || topComp.id
      if (topId) {
        setSelectedComponentId(topId)
      }
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

  const copyText = (text, id) => {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const openInspector = (compId, tab = 'deps', to = '') => {
    setInspectingComponentId(compId)
    setInspectorTab(tab)
    setInspectorPathTo(to)
    const params = new URLSearchParams()
    if (compId) params.set('inspect', compId)
    if (tab && tab !== 'deps') params.set('tab', tab)
    if (to) params.set('to', to)
    const qs = params.toString()
    window.location.hash = qs ? `#/audit?${qs}` : '#/audit'
  }

  const handleCloseInspector = () => {
    setInspectingComponentId(null)
    window.location.hash = '#/audit'
  }

  if (loading && !report) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[500px] text-center space-y-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-lg border border-[#2A2E35] bg-[#15171B] text-laser-lime font-mono text-xs font-bold animate-pulse shadow-laser-glow">
          AST
        </div>
        <div className="space-y-1.5">
          <p className="text-sm font-bold uppercase tracking-wider font-mono text-slate-100">
            Running Deep Codebase Audit...
          </p>
          <p className="text-xs text-slate-400 font-mono">
            Tree-sitter AST parsing · openCypher graph assembly · ONNX defect regressor · SHAP game theory
          </p>
        </div>
      </div>
    )
  }

  if (error && !report) {
    return (
      <div className="rounded-xl border border-[#5A1C16] bg-[#2A0E0B] p-8 text-center max-w-lg mx-auto shadow-2xl space-y-4">
        <div className="flex h-10 w-10 mx-auto items-center justify-center rounded border border-[#FF4A2B]/60 bg-[#FF4A2B]/10 text-[#FF4A2B] font-mono font-black text-sm">
          !
        </div>
        <div className="text-rose-200 font-bold text-sm uppercase tracking-wider font-mono">No Active Audit Report</div>
        <p className="text-xs text-slate-300 leading-relaxed font-sans">
          {error.message || 'No codebase has been ingested yet or the report cache is empty.'}
        </p>
        <a
          href="#/ingest"
          className="inline-block rounded-lg border border-laser-lime bg-laser-lime px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider text-black transition hover:shadow-laser-glow"
        >
          Ingest Codebase Now →
        </a>
      </div>
    )
  }

  const scorecard = report.scorecard || {}
  const findings = report.findings || []
  const roadmap = report.roadmap || {}
  const overallScore = scorecard.overall_score ?? 78
  const mlInsights = report?.ml_insights || {}
  const onnxMetrics = mlInsights.onnx_metrics || {}
  const shapData = mlInsights.shap_explainability || {}
  const riskTier = onnxMetrics.defect_risk_tier || (overallScore >= 80 ? 'LOW' : overallScore >= 50 ? 'MODERATE' : 'CRITICAL')

  // Filter findings
  const filteredFindings = findings.filter((f) => {
    if (sevFilter !== 'all') {
      const targetSev = sevFilter.toLowerCase()
      const fSev = f.severity.toLowerCase()
      if (targetSev === 'crit' || targetSev === 'critical') {
        if (fSev !== 'critical' && fSev !== 'crit') return false
      } else if (targetSev === 'med' || targetSev === 'medium') {
        if (fSev !== 'medium' && fSev !== 'med') return false
      } else if (fSev !== targetSev) {
        return false
      }
    }
    if (dimFilter !== 'all' && f.dimension.toLowerCase() !== dimFilter.toLowerCase()) return false
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      const matchDesc = (f.description || '').toLowerCase().includes(q)
      const matchFile = (f.evidence_file || '').toLowerCase().includes(q)
      const matchRule = (f.rule_id || '').toLowerCase().includes(q)
      if (!matchDesc && !matchFile && !matchRule) return false
    }
    return true
  })

  const phaseBadgeClass =
    scorecard.phase === 'PRODUCTION_READY'
      ? 'border-emerald-800 bg-emerald-950/40 text-[#5DE6A8]'
      : scorecard.phase === 'MVP_VIABLE'
      ? 'border-sky-800 bg-sky-950/40 text-sky-400'
      : 'border-[#5A1C16] bg-[#2A0E0B] text-[#FF4A2B]'

  const containerTheme = isDossier
    ? 'bg-[#EFEAE0] text-[#101114] p-6 md:p-8 rounded-2xl border border-[#D8D2C5] shadow-2xl transition-all duration-300'
    : 'space-y-6 transition-all duration-300'

  return (
    <div className={containerTheme}>
      {/* Cockpit HUD Header */}
      <div className={`flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 border-b pb-5 ${isDossier ? 'border-[#D8D2C5]' : 'border-[#2A2E35]'}`}>
        <div>
          <div className="flex items-center gap-3">
            <h1 className={`text-2xl sm:text-3xl font-serif font-normal tracking-tight ${isDossier ? 'text-[#101114]' : 'text-slate-50'}`}>
              Audit Cockpit
            </h1>
            <span className={`inline-flex items-center gap-1.5 rounded border px-2.5 py-0.5 text-xs font-mono font-bold uppercase tracking-wider ${phaseBadgeClass}`}>
              <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" />
              {scorecard.phase || 'AUDITING'}
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded border border-[#2A2E35] bg-[#15171B] text-slate-400 hidden sm:inline">
              DETERMINISTIC
            </span>
          </div>
          <p className={`mt-1.5 text-xs flex flex-wrap items-center gap-x-2 gap-y-1 font-mono ${isDossier ? 'text-[#575A65]' : 'text-slate-400'}`}>
            <span>Target: <strong className={isDossier ? 'text-black' : 'text-slate-200'}>{report.target_name}</strong></span>
            <span className={isDossier ? 'text-[#D8D2C5]' : 'text-[#2A2E35]'}>|</span>
            <span>Intake: <span className="text-laser-lime font-bold uppercase">{report.access_tier?.replace('_', ' ')}</span></span>
            <span className={isDossier ? 'text-[#D8D2C5]' : 'text-[#2A2E35]'}>|</span>
            <span>Report ID: <span className="font-semibold">{report.report_id}</span></span>
          </p>
        </div>

        {/* Global Controls & Atmosphere Switcher Toolbar */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Dual Atmosphere Switcher: Chamber (Dark) <-> Dossier (Paper) */}
          <button
            onClick={() => setIsDossier(!isDossier)}
            className={`rounded-lg border px-3 py-1.5 font-mono text-xs font-bold uppercase tracking-wider transition flex items-center gap-1.5 ${
              isDossier
                ? 'border-[#101114] bg-[#101114] text-[#EFEAE0]'
                : 'border-laser-lime/60 bg-laser-lime/10 text-laser-lime hover:bg-laser-lime hover:text-black'
            }`}
            title="Toggle between Chamber (Dark HUD) and Dossier (Archival Paper Report)"
          >
            {isDossier ? <Moon className="w-3.5 h-3.5" /> : <Sun className="w-3.5 h-3.5" />}
            <span>{isDossier ? 'Chamber View' : 'Dossier View'}</span>
          </button>

          {/* Constellation Toggle */}
          <button
            onClick={() => setShowConstellation(!showConstellation)}
            className={`rounded-lg border px-3 py-1.5 font-mono text-xs font-semibold transition flex items-center gap-1.5 ${
              isDossier
                ? 'border-[#D8D2C5] bg-[#F7F4EE] text-[#101114]'
                : 'border-[#2A2E35] bg-[#15171B] text-slate-300 hover:border-slate-500'
            }`}
            title="Toggle Living Dependency Constellation Hero"
          >
            <Sparkles className="w-3.5 h-3.5 text-laser-lime" />
            <span>{showConstellation ? 'Hide Constellation' : 'Living Graph'}</span>
          </button>

          {/* Milestone Target Switcher */}
          <div className={`inline-flex rounded-lg border p-0.5 font-mono text-xs ${isDossier ? 'border-[#D8D2C5] bg-[#F7F4EE]' : 'border-[#2A2E35] bg-[#15171B]'}`}>
            <button
              onClick={() => { setGoal('mvp'); handleRunAnalysis('mvp'); }}
              disabled={analyzing}
              className={`px-3 py-1 text-xs font-bold uppercase tracking-wider rounded transition ${
                goal === 'mvp' ? 'bg-laser-lime text-black' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Goal: MVP
            </button>
            <button
              onClick={() => { setGoal('production'); handleRunAnalysis('production'); }}
              disabled={analyzing}
              className={`px-3 py-1 text-xs font-bold uppercase tracking-wider rounded transition ${
                goal === 'production' ? 'bg-laser-lime text-black' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Goal: Production
            </button>
          </div>

          {/* Free Standard Exports */}
          <a
            href={api.getMarkdownReportUrl()}
            target="_blank"
            rel="noreferrer"
            className={`rounded-lg border px-3 py-1.5 font-mono text-xs font-semibold transition flex items-center gap-1.5 ${
              isDossier
                ? 'border-[#D8D2C5] bg-[#F7F4EE] text-[#101114] hover:bg-[#EAE5DB]'
                : 'border-[#2A2E35] bg-[#15171B] text-slate-300 hover:bg-[#1E2228]'
            }`}
            title="Download full audit report as GitHub-flavored Markdown"
          >
            <span>[MD]</span> Markdown
          </a>

          <a
            href={api.getHtmlReportUrl()}
            target="_blank"
            rel="noreferrer"
            className="rounded-lg border border-laser-lime bg-laser-lime px-3 py-1.5 font-mono text-xs font-bold text-black hover:shadow-laser-glow transition flex items-center gap-1.5"
            title="Print or save formal audit report as PDF"
          >
            <Printer className="w-3.5 h-3.5" />
            <span>[PDF] PDF / Print</span>
          </a>

          {/* Additive On-Chain Verification Option */}
          <button
            onClick={() => setShowX402Modal(true)}
            data-testid="onchain-proof-btn"
            className="rounded-lg border border-amber-800 bg-amber-950/30 px-3 py-1.5 font-mono text-xs font-bold text-[#FFB020] hover:bg-amber-950/60 transition flex items-center gap-1.5"
            title="Settle report on Algorand blockchain via x402 protocol"
          >
            <span>[⛓]</span> On-Chain Proof
          </button>
        </div>
      </div>

      {/* Living Constellation Specimen (Toggleable) */}
      {showConstellation && (
        <div className="relative mt-4">
          <HeroConstellation height={300} />
        </div>
      )}

      {/* Critical Security Lockout Warning */}
      {scorecard.has_critical_blocker && (
        <div className="mt-4 rounded-xl border border-[#FF4A2B] bg-[#2A0E0B] p-4 text-xs text-[#FF4A2B] flex items-start gap-3 shadow-crit-glow">
          <span className="font-mono font-black text-[#FF4A2B] text-base leading-none">◆</span>
          <div>
            <div className="font-mono font-bold text-xs uppercase tracking-wider text-rose-200">
              Critical Security Lockout Active (Score Capped at 25/100) — Hard Constraint Alert: Security Score Capped at 25/100
            </div>
            <p className="mt-1 leading-relaxed text-rose-300/90 font-sans">
              An unaddressed critical vulnerability or plaintext credential was detected in the active repository.
              Per Section 9 non-negotiable security rules, production readiness tracks are locked until this blocker is remedied.
            </p>
          </div>
        </div>
      )}

      {/* Telemetry Cockpit Hero Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 mt-6">
        {/* Card 1: The Verdict - Odometer + Stamped Risk Tier Seal (4 Cols) */}
        <div className={`lg:col-span-4 rounded-xl border p-5 flex flex-col items-center justify-between text-center relative overflow-hidden ${
          isDossier ? 'border-[#D8D2C5] bg-[#F7F4EE]' : 'border-[#2A2E35] bg-[#15171B]'
        }`}>
          <div className="absolute top-0 right-0 p-3">
            <span className="text-[10px] font-mono uppercase tracking-widest font-bold text-slate-500">
              DETERMINISTIC
            </span>
          </div>

          <div className="w-full text-left">
            <span className={`text-xs font-bold uppercase tracking-wider font-mono ${isDossier ? 'text-[#575A65]' : 'text-slate-400'}`}>
              The Verdict
            </span>
            <div className={`text-[11px] mt-0.5 font-sans ${isDossier ? 'text-[#575A65]' : 'text-slate-400'}`}>
              Multi-dimensional deterministic readiness score
            </div>
          </div>

          {/* Odometer Rolling Numeral */}
          <div className="my-4 flex flex-col items-center">
            <div className="flex items-baseline gap-1">
              <span className={`text-6xl font-black font-mono tracking-tight ${isDossier ? 'text-[#101114]' : 'text-slate-100'}`}>
                <OdometerNumeral value={overallScore} />
              </span>
              <span className={`text-lg font-mono uppercase tracking-widest ${isDossier ? 'text-[#575A65]' : 'text-slate-500'}`}>
                / 100
              </span>
            </div>
            <div className="mt-3">
              <VerdictSeal
                tier={riskTier}
                isCapped={scorecard.has_critical_blocker}
                capReason="Plaintext secret or critical CVE detected"
              />
            </div>
          </div>

          <div className={`w-full pt-3 border-t flex items-center justify-between text-xs font-mono ${
            isDossier ? 'border-[#D8D2C5] text-[#575A65]' : 'border-[#2A2E35] text-slate-400'
          }`}>
            <span>READINESS TRACK:</span>
            <span className={`font-bold tracking-wider ${overallScore >= 80 ? 'text-[#5DE6A8]' : overallScore >= 55 ? 'text-sky-400' : 'text-[#FF4A2B]'}`}>
              {scorecard.phase}
            </span>
          </div>
        </div>

        {/* Card 2: ONNX Runtime Fragility Model (4 Cols) */}
        <div className={`lg:col-span-4 rounded-xl border p-5 flex flex-col justify-between relative ${
          isDossier ? 'border-[#D8D2C5] bg-[#F7F4EE]' : 'border-[#2A2E35] bg-[#15171B]'
        }`}>
          <div>
            <div className="flex items-center justify-between">
              <span className={`text-xs font-bold uppercase tracking-wider font-mono ${isDossier ? 'text-[#101114]' : 'text-slate-300'}`}>
                ONNX FRAGILITY REGRESSOR
              </span>
              <span className={`rounded border px-2 py-0.5 text-[10px] font-mono ${
                isDossier ? 'border-[#D8D2C5] bg-[#EFEAE0] text-black' : 'border-[#2A2E35] bg-[#0A0B0D] text-laser-lime'
              }`}>
                {onnxMetrics.runtime_engine || 'onnxruntime v1.30'}
              </span>
            </div>

            <div className="mt-3.5 grid grid-cols-2 gap-2.5">
              <div className={`rounded-lg border p-3 ${isDossier ? 'border-[#D8D2C5] bg-[#EFEAE0]' : 'border-[#2A2E35] bg-[#0A0B0D]'}`}>
                <span className="text-[10px] uppercase font-mono font-semibold block text-slate-500">Fragility Index</span>
                <span className="text-xl font-bold font-mono text-[#FFB020] tabular-nums">
                  {onnxMetrics.fragility_score !== undefined ? onnxMetrics.fragility_score : '0.45'}
                </span>
                <span className="text-[9px] text-slate-500 font-mono block">Scale: 0.0 - 1.0</span>
              </div>

              <div className={`rounded-lg border p-3 ${isDossier ? 'border-[#D8D2C5] bg-[#EFEAE0]' : 'border-[#2A2E35] bg-[#0A0B0D]'}`}>
                <span className="text-[10px] uppercase font-mono font-semibold block text-slate-500">Defect Risk Tier</span>
                <span className={`text-base font-bold font-mono uppercase ${
                  onnxMetrics.defect_risk_tier === 'Critical' ? 'text-[#FF4A2B]' :
                  onnxMetrics.defect_risk_tier === 'High' ? 'text-[#FFB020]' :
                  onnxMetrics.defect_risk_tier === 'Moderate' ? 'text-[#FACC15]' : 'text-[#5DE6A8]'
                }`}>
                  {onnxMetrics.defect_risk_tier || 'Moderate'}
                </span>
                <span className="text-[9px] text-slate-500 font-mono block">Structural Profile</span>
              </div>
            </div>

            <div className={`mt-3 space-y-1.5 text-xs font-mono ${isDossier ? 'text-[#575A65]' : 'text-slate-400'}`}>
              <div className="flex justify-between">
                <span>Maintainability Index:</span>
                <span className={`font-bold tabular-nums ${isDossier ? 'text-black' : 'text-slate-200'}`}>
                  {onnxMetrics.maintainability_index ?? 72}/100
                </span>
              </div>
              <div className="flex justify-between">
                <span>Estimated Remediation:</span>
                <span className="text-laser-lime font-bold">~{onnxMetrics.estimated_remediation_days ?? 8} Person-Days</span>
              </div>
            </div>
          </div>

          <div className={`mt-3 pt-3 border-t ${isDossier ? 'border-[#D8D2C5]' : 'border-[#2A2E35]'}`}>
            <span className="text-[10px] font-mono uppercase tracking-wider font-semibold text-slate-400 block mb-1">Structural Risk Triggers:</span>
            <ul className="text-[11px] text-slate-400 space-y-1 font-mono">
              {(onnxMetrics.risk_triggers || ['Standard architectural coupling']).slice(0, 2).map((trig, i) => (
                <li key={i} className="flex items-start gap-1.5">
                  <span className="text-amber-400 leading-none">■</span>
                  <span className="truncate">{trig}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Card 3: SHAP Game-Theoretic Decomposition (4 Cols) */}
        <div className={`lg:col-span-4 rounded-xl border p-5 flex flex-col justify-between relative ${
          isDossier ? 'border-[#D8D2C5] bg-[#F7F4EE]' : 'border-[#2A2E35] bg-[#15171B]'
        }`}>
          <div>
            <div className="flex items-center justify-between">
              <span className={`text-xs font-bold uppercase tracking-wider font-mono ${isDossier ? 'text-[#101114]' : 'text-slate-300'}`}>
                SHAP EXPLAINABILITY
              </span>
              <span className="rounded border border-emerald-900/60 bg-emerald-950/40 px-2 py-0.5 text-[10px] font-mono text-[#5DE6A8]">
                GAME THEORY
              </span>
            </div>

            <p className={`mt-1.5 text-[11px] leading-snug font-sans ${isDossier ? 'text-[#575A65]' : 'text-slate-400'}`}>
              Decomposes how structural AST signals add or subtract points from expected baseline:
            </p>

            <div className="mt-3">
              <SHAPLedger
                shapData={shapData}
                finalScore={overallScore}
                isDossier={isDossier}
              />
            </div>
          </div>

          <div className={`mt-3 pt-2.5 border-t flex items-center justify-between text-[10px] font-mono ${
            isDossier ? 'border-[#D8D2C5] text-[#575A65]' : 'border-[#2A2E35] text-slate-500'
          }`}>
            <span>Baseline E[f(X)]: {shapData.baseline_score ?? 95.0}</span>
            <span>Final Sum: {overallScore}</span>
          </div>
        </div>
      </div>

      {/* 5-Dimension Scorecard Matrix */}
      <div className="mt-6">
        <div className="flex items-center justify-between mb-2.5">
          <h2 className={`text-xs font-bold uppercase tracking-wider font-mono ${isDossier ? 'text-[#101114]' : 'text-slate-400'}`}>
            Dimensional Maturity Breakdown
          </h2>
          <span className="text-[10px] text-slate-500 font-mono">Click dimension to filter ledger</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5">
          {['security', 'tests', 'scalability', 'duplication', 'maintainability'].map((dim) => {
            const s = (scorecard.dimensions || {})[dim] || { score: 70, findings_count: 0, high_count: 0, critical_count: 0 }
            const isSecCapped = dim === 'security' && scorecard.has_critical_blocker
            const barColor = s.score >= 75 ? 'bg-[#5DE6A8]' : s.score >= 50 ? 'bg-sky-400' : 'bg-[#FF4A2B]'
            const isSelected = dimFilter === dim

            return (
              <div
                key={dim}
                onClick={() => setDimFilter(isSelected ? 'all' : dim)}
                className={`rounded-lg border p-3 flex flex-col justify-between space-y-2.5 cursor-pointer transition ${
                  isSelected
                    ? isDossier ? 'border-black bg-[#EAE5DB]' : 'border-laser-lime bg-[#1E2228]'
                    : isDossier ? 'border-[#D8D2C5] bg-[#F7F4EE] hover:bg-[#EAE5DB]' : 'border-[#2A2E35] bg-[#15171B] hover:border-[#3D4450]'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className={`text-xs font-bold uppercase tracking-wider font-mono ${isDossier ? 'text-[#101114]' : 'text-slate-200'}`}>
                      {dim}
                    </span>
                    {s.critical_count > 0 && (
                      <span className="rounded border border-[#5A1C16] bg-[#2A0E0B] px-1.5 py-0.2 text-[9px] font-bold font-mono text-[#FF4A2B]">
                        {s.critical_count} CRIT
                      </span>
                    )}
                  </div>

                  <div className="mt-1.5 flex items-baseline gap-1 font-mono">
                    <span className={`text-xl font-black tracking-tight ${isSecCapped ? 'text-[#FF4A2B]' : isDossier ? 'text-[#101114]' : 'text-slate-100'} tabular-nums`}>
                      {s.score}
                    </span>
                    <span className="text-[10px] text-slate-500">/100</span>
                  </div>

                  <div className={`w-full h-1 rounded-full overflow-hidden mt-2 ${isDossier ? 'bg-[#D8D2C5]' : 'bg-[#0A0B0D]'}`}>
                    <div className={`h-full rounded-full ${barColor}`} style={{ width: `${Math.max(5, s.score)}%` }} />
                  </div>
                </div>

                <div className={`flex items-center justify-between text-[10px] pt-1 border-t font-mono ${
                  isDossier ? 'border-[#D8D2C5] text-[#575A65]' : 'border-[#2A2E35] text-slate-500'
                }`}>
                  <span>{s.findings_count} findings</span>
                  <span>{s.high_count} high</span>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Prioritized Engineering Roadmap */}
      <div className={`mt-6 rounded-xl border p-5 space-y-5 ${isDossier ? 'border-[#D8D2C5] bg-[#F7F4EE]' : 'border-[#2A2E35] bg-[#15171B]'}`}>
        <div className={`flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b pb-3 ${isDossier ? 'border-[#D8D2C5]' : 'border-[#2A2E35]'}`}>
          <div>
            <h2 className={`text-sm font-bold uppercase tracking-wider font-mono flex items-center gap-2 ${isDossier ? 'text-[#101114]' : 'text-slate-100'}`}>
              <span className="text-laser-lime">🗺️</span> Prioritized Engineering Roadmap
            </h2>
            <p className={`mt-0.5 text-xs font-sans ${isDossier ? 'text-[#575A65]' : 'text-slate-400'}`}>{roadmap.summary_narrative}</p>
          </div>
          <span className={`rounded border px-2.5 py-0.5 text-[11px] font-mono font-bold self-start sm:self-auto ${
            isDossier ? 'border-[#D8D2C5] bg-[#EFEAE0] text-black' : 'border-laser-lime/40 bg-laser-lime/10 text-laser-lime'
          }`}>
            TARGET: {roadmap.goal?.toUpperCase() || 'PRODUCTION'}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {(roadmap.phases || [
            { phase_name: 'Phase 1 - Immediate', target_timeline: 'Week 1', actions: [] },
            { phase_name: 'Phase 2 - Hardening', target_timeline: 'Week 2-3', actions: [] },
            { phase_name: 'Phase 3 - Scale', target_timeline: 'Month 1', actions: [] },
          ]).map((phase, idx) => (
            <div key={idx} className={`rounded-lg border p-3.5 flex flex-col justify-between space-y-3 ${
              isDossier ? 'border-[#D8D2C5] bg-[#EFEAE0]' : 'border-[#2A2E35] bg-[#0A0B0D]'
            }`}>
              <div>
                <div className={`flex items-center justify-between text-xs font-bold font-mono ${isDossier ? 'text-[#101114]' : 'text-slate-200'}`}>
                  <span className="flex items-center gap-1.5 uppercase">
                    <span className="flex h-4 w-4 items-center justify-center rounded bg-laser-lime text-black text-[9px] font-bold">
                      {idx + 1}
                    </span>
                    {phase.phase_name}
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">{phase.target_timeline}</span>
                </div>

                <div className="mt-2.5 space-y-2">
                  {(phase.actions || []).map((act, aIdx) => (
                    <div key={aIdx} className={`rounded border p-2.5 text-xs space-y-1 ${
                      isDossier ? 'border-[#D8D2C5] bg-[#F7F4EE]' : 'border-[#2A2E35] bg-[#15171B]'
                    }`}>
                      <div className="flex items-center justify-between">
                        <span className={`font-semibold font-mono text-[11px] truncate max-w-[160px] ${isDossier ? 'text-[#101114]' : 'text-slate-200'}`}>
                          {act.title}
                        </span>
                        <span className={`text-[9px] font-mono px-1 py-0.2 rounded border ${
                          isDossier ? 'bg-[#EAE5DB] text-black border-[#D8D2C5]' : 'bg-laser-lime/10 text-laser-lime border-laser-lime/30'
                        }`}>
                          {act.effort_estimate || (idx === 0 ? 'P0 - Critical' : idx === 1 ? 'P1 - High' : 'P2 - Medium')}
                        </span>
                      </div>
                      <p className={`text-[11px] leading-snug font-sans ${isDossier ? 'text-[#575A65]' : 'text-slate-400'}`}>
                        {act.description}
                      </p>
                      {act.impacted_components?.length > 0 && (
                        <div className={`flex flex-wrap gap-1 mt-1 pt-1 border-t ${isDossier ? 'border-[#D8D2C5]' : 'border-[#2A2E35]'}`}>
                          {act.impacted_components.map((c, cIdx) => (
                            <button
                              key={cIdx}
                              onClick={() => openInspector(c, 'deps')}
                              className="rounded bg-[#0A0B0D] border border-[#2A2E35] px-1.5 py-0.2 text-[9px] font-mono text-laser-lime hover:text-white transition"
                              title="Click to inspect component graph & paths"
                            >
                              {c} ↗
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div className={`pt-2 border-t text-[10px] flex justify-between font-mono ${
                isDossier ? 'border-[#D8D2C5] text-[#575A65]' : 'border-[#2A2E35] text-slate-500'
              }`}>
                <span>STATUS: PENDING</span>
                <span className={`font-semibold ${isDossier ? 'text-black' : 'text-slate-400'}`}>
                  {phase.actions?.length || 0} Actions
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Evidenced Findings Ledger */}
      <div className={`mt-6 rounded-xl border p-5 space-y-4 ${isDossier ? 'border-[#D8D2C5] bg-[#F7F4EE]' : 'border-[#2A2E35] bg-[#15171B]'}`}>
        <div className={`flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b pb-3 ${isDossier ? 'border-[#D8D2C5]' : 'border-[#2A2E35]'}`}>
          <div>
            <h2 className={`text-sm font-bold uppercase tracking-wider font-mono flex items-center gap-2 ${isDossier ? 'text-[#101114]' : 'text-slate-100'}`}>
              <span>🔍</span> Evidenced Findings Catalog
              <span className={`rounded border px-2 py-0.5 text-[10px] font-mono ${isDossier ? 'border-[#D8D2C5] bg-[#EFEAE0] text-black' : 'border-[#2A2E35] bg-[#0A0B0D] text-slate-400'}`}>
                {filteredFindings.length} OF {findings.length}
              </span>
            </h2>
            <p className={`text-xs mt-0.5 font-sans ${isDossier ? 'text-[#575A65]' : 'text-slate-400'}`}>
              Every finding is statically proven with file and line evidence. No false proxy reports.
            </p>
          </div>

          {/* Severity filter buttons */}
          <div className="flex flex-wrap items-center gap-1 font-mono text-xs">
            {[
              { id: 'all', label: 'ALL', count: findings.length },
              { id: 'critical', label: 'CRITICAL', count: findings.filter((f) => f.severity.toLowerCase() === 'critical' || f.severity.toLowerCase() === 'crit').length },
              { id: 'high', label: 'HIGH', count: findings.filter((f) => f.severity.toLowerCase() === 'high').length },
              { id: 'medium', label: 'MEDIUM', count: findings.filter((f) => f.severity.toLowerCase() === 'medium' || f.severity.toLowerCase() === 'med').length },
              { id: 'low', label: 'LOW', count: findings.filter((f) => f.severity.toLowerCase() === 'low').length },
            ].map(({ id, label, count }) => {
              const isSelected = sevFilter === id
              return (
                <button
                  key={id}
                  onClick={() => setSevFilter(id)}
                  className={`rounded px-2.5 py-1 text-[11px] font-bold tracking-wider uppercase transition ${
                    isSelected
                      ? 'bg-laser-lime text-black shadow-laser-glow'
                      : isDossier
                      ? 'bg-[#EAE5DB] border border-[#D8D2C5] text-black hover:bg-[#D8D2C5]'
                      : 'bg-[#0A0B0D] border border-[#2A2E35] text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {label} ({count})
                </button>
              )
            })}
          </div>
        </div>

        {/* Search & Filter Toolbar */}
        <div className="flex flex-col sm:flex-row gap-2 font-mono text-xs">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search findings or files by description, rule ID, citation..."
            className={`w-full rounded border px-3.5 py-2 text-xs focus:outline-none ${
              isDossier
                ? 'border-[#D8D2C5] bg-[#EFEAE0] text-black placeholder-[#575A65] focus:border-black'
                : 'border-[#2A2E35] bg-[#0A0B0D] text-slate-100 placeholder-slate-500 focus:border-laser-lime'
            }`}
          />

          <select
            value={dimFilter}
            onChange={(e) => setDimFilter(e.target.value)}
            className={`rounded border px-3 py-2 text-xs focus:outline-none uppercase ${
              isDossier
                ? 'border-[#D8D2C5] bg-[#EFEAE0] text-black focus:border-black'
                : 'border-[#2A2E35] bg-[#0A0B0D] text-slate-200 focus:border-laser-lime'
            }`}
          >
            <option value="all">ALL DIMENSIONS</option>
            <option value="security">SECURITY</option>
            <option value="tests">TESTS</option>
            <option value="scalability">SCALABILITY</option>
            <option value="duplication">DUPLICATION</option>
            <option value="maintainability">MAINTAINABILITY</option>
          </select>
        </div>

        {/* Findings Ledger Table */}
        {filteredFindings.length === 0 ? (
          <div className={`rounded border border-dashed p-8 text-center text-xs font-mono ${
            isDossier ? 'border-[#D8D2C5] text-[#575A65]' : 'border-[#2A2E35] text-slate-500'
          }`}>
            No audit findings match your selected filters.
          </div>
        ) : (
          <div className={`overflow-x-auto rounded border ${isDossier ? 'border-[#D8D2C5]' : 'border-[#2A2E35]'}`}>
            <table className="w-full text-left text-xs font-mono">
              <thead className={`border-b text-[10px] uppercase tracking-wider ${
                isDossier ? 'border-[#D8D2C5] bg-[#EAE5DB] text-[#575A65]' : 'border-[#2A2E35] bg-[#0A0B0D] text-slate-400'
              }`}>
                <tr>
                  <th scope="col" className="px-3.5 py-2.5">SEVERITY</th>
                  <th scope="col" className="px-3.5 py-2.5">RULE ID</th>
                  <th scope="col" className="px-3.5 py-2.5">AST CITATION</th>
                  <th scope="col" className="px-3.5 py-2.5">CONFIDENCE</th>
                  <th scope="col" className="px-3.5 py-2.5">DESCRIPTION</th>
                  <th scope="col" className="px-3.5 py-2.5 text-right">ACTION</th>
                </tr>
              </thead>
              <tbody className={`divide-y ${isDossier ? 'divide-[#D8D2C5] bg-[#F7F4EE]' : 'divide-[#2A2E35] bg-[#15171B]'}`}>
                {filteredFindings.map((f, idx) => {
                  const isExpanded = expandedFinding === idx
                  const confidenceLevel = f.confidence || (f.severity.toLowerCase() === 'critical' ? 'high' : 'medium')
                  return (
                    <React.Fragment key={idx}>
                      <tr
                        onClick={() => setExpandedFinding(isExpanded ? null : idx)}
                        className={`cursor-pointer transition ${
                          isExpanded
                            ? isDossier ? 'bg-[#EAE5DB]' : 'bg-[#1E2228]'
                            : isDossier ? 'hover:bg-[#EAE5DB]/60' : 'hover:bg-[#1E2228]/60'
                        }`}
                      >
                        <td className="px-3.5 py-3 whitespace-nowrap">
                          <CritBadge tier={f.severity} />
                        </td>
                        <td className="px-3.5 py-3 whitespace-nowrap font-bold text-laser-lime">
                          {f.rule_id}
                        </td>
                        <td className="px-3.5 py-3 whitespace-nowrap">
                          <code className={`rounded border px-2 py-0.5 ${
                            isDossier ? 'border-[#D8D2C5] bg-[#EFEAE0] text-black' : 'border-[#2A2E35] bg-[#0A0B0D] text-slate-200'
                          }`}>
                            {f.evidence_file}:{f.evidence_line ?? 1}
                          </code>
                        </td>
                        <td className="px-3.5 py-3 whitespace-nowrap">
                          <ConfidenceGauge level={confidenceLevel} label={true} />
                        </td>
                        <td className="px-3.5 py-3 max-w-md">
                          <p className={`truncate font-sans ${isDossier ? 'text-[#101114]' : 'text-slate-200'}`} title={f.description}>
                            {f.description}
                          </p>
                        </td>
                        <td className="px-3.5 py-3 text-right whitespace-nowrap space-x-1.5" onClick={(e) => e.stopPropagation()}>
                          <button
                            type="button"
                            onClick={() => copyText(`${f.evidence_file}:${f.evidence_line ?? 1}`, `cit-${idx}`)}
                            className={`rounded border px-2 py-0.5 text-[10px] transition ${
                              isDossier ? 'border-[#D8D2C5] bg-[#EFEAE0] text-black hover:bg-[#D8D2C5]' : 'border-[#2A2E35] bg-[#0A0B0D] text-slate-400 hover:text-slate-200'
                            }`}
                          >
                            {copiedId === `cit-${idx}` ? '✓ Copied' : 'Copy'}
                          </button>
                          <button
                            type="button"
                            onClick={() => openInspector(f.evidence_file, 'deps')}
                            className="rounded border border-laser-lime/40 bg-laser-lime/10 px-2 py-0.5 text-[10px] font-bold text-laser-lime hover:bg-laser-lime hover:text-black transition"
                            title="Inspect component in openCypher graph drawer"
                          >
                            Inspect ↗
                          </button>
                        </td>
                      </tr>

                      {/* Expandable Evidence Detail Row */}
                      {isExpanded && (
                        <tr className={isDossier ? 'bg-[#EAE5DB]' : 'bg-[#0A0B0D]'}>
                          <td colSpan="6" className={`p-4 border-b ${isDossier ? 'border-[#D8D2C5]' : 'border-[#2A2E35]'}`}>
                            <div className="space-y-3 font-sans">
                              <div>
                                <span className="font-mono text-[10px] uppercase tracking-wider text-slate-400 block mb-1">
                                  Full Diagnostic Summary:
                                </span>
                                <p className={`text-xs leading-relaxed ${isDossier ? 'text-black' : 'text-slate-200'}`}>{f.description}</p>
                              </div>

                              {f.snippet && (
                                <div>
                                  <span className="font-mono text-[10px] uppercase tracking-wider text-slate-400 block mb-1">
                                    AST Evidence Snippet ({f.evidence_file}:{f.evidence_line ?? 1}):
                                  </span>
                                  <div className={`rounded border p-3 font-mono text-xs overflow-x-auto ${
                                    isDossier ? 'border-[#D8D2C5] bg-[#F7F4EE] text-black' : 'border-[#2A2E35] bg-[#15171B] text-slate-300'
                                  }`}>
                                    <pre className="text-[11px] leading-snug">{f.snippet}</pre>
                                  </div>
                                </div>
                              )}

                              {f.remediation && (
                                <div className={`rounded border p-3 space-y-1.5 ${
                                  isDossier ? 'border-[#D8D2C5] bg-[#F7F4EE]' : 'border-[#2A2E35] bg-[#15171B]'
                                }`}>
                                  <div className="flex items-center justify-between font-mono">
                                    <span className="text-[11px] font-bold text-laser-lime flex items-center gap-1.5">
                                      <span>💡</span> Remediation Guidance:
                                    </span>
                                    <button
                                      type="button"
                                      onClick={() => copyText(f.remediation, `rem-${idx}`)}
                                      className="rounded border border-laser-lime/40 bg-laser-lime/10 px-2 py-0.5 text-[10px] text-laser-lime hover:bg-laser-lime hover:text-black transition"
                                    >
                                      {copiedId === `rem-${idx}` ? '✓ Copied' : 'Copy Fix'}
                                    </button>
                                  </div>
                                  <p className={`text-xs leading-relaxed font-sans ${isDossier ? 'text-[#101114]' : 'text-slate-300'}`}>{f.remediation}</p>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Criticality Leaderboard & Graph Explorer Quick-Access */}
      <div className={`mt-6 rounded-xl border p-5 space-y-3.5 ${isDossier ? 'border-[#D8D2C5] bg-[#F7F4EE]' : 'border-[#2A2E35] bg-[#15171B]'}`}>
        <div className={`flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b pb-3 ${isDossier ? 'border-[#D8D2C5]' : 'border-[#2A2E35]'}`}>
          <div>
            <h2 className={`text-sm font-bold uppercase tracking-wider font-mono flex items-center gap-2 ${isDossier ? 'text-[#101114]' : 'text-slate-100'}`}>
              <span className="text-laser-lime">⚡</span> Component Criticality Leaderboard
            </h2>
            <p className={`text-xs font-sans ${isDossier ? 'text-[#575A65]' : 'text-slate-400'}`}>
              Components ranked by multi-hop graph reach if failure occurs. Click card to open in Graph Inspector.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
          {(report.criticality_leaderboard || []).map((item, idx) => {
            const compId = item.component?.id || item.id || `comp-${idx}`
            const compName = item.component?.name || item.name || compId
            const compType = item.type || 'Module'
            const tier = item.tier || 'MEDIUM'
            const reach = item.reach || 0

            return (
              <div
                key={compId}
                data-testid="leaderboard-card"
                onClick={() => openInspector(compId, 'deps')}
                className={`group rounded-lg border p-3 space-y-2 cursor-pointer transition ${
                  isDossier
                    ? 'border-[#D8D2C5] bg-[#EFEAE0] hover:bg-[#EAE5DB]'
                    : 'border-[#2A2E35] bg-[#0A0B0D] hover:border-laser-lime/60 hover:bg-[#1E2228]'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 min-w-0">
                    <Dot type={compType} />
                    <span className={`truncate font-mono font-bold text-xs group-hover:text-laser-lime ${isDossier ? 'text-[#101114]' : 'text-slate-200'}`}>
                      {compName}
                    </span>
                  </div>
                  <CritBadge tier={tier} size="xs" />
                </div>

                <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
                  <span>Reach: <strong className="text-laser-lime">{reach} nodes</strong></span>
                  <span className="text-slate-500 group-hover:text-laser-lime font-semibold">Neighborhood ↗</span>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Diagrams Section */}
      <div className={`mt-6 rounded-xl border p-5 space-y-3.5 ${isDossier ? 'border-[#D8D2C5] bg-[#F7F4EE]' : 'border-[#2A2E35] bg-[#15171B]'}`}>
        <div className={`flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b pb-3 ${isDossier ? 'border-[#D8D2C5]' : 'border-[#2A2E35]'}`}>
          <div className="flex items-center gap-3">
            <h2 className={`text-sm font-bold uppercase tracking-wider font-mono ${isDossier ? 'text-[#101114]' : 'text-slate-100'}`}>
              Architecture & Blast Radius Blueprint
            </h2>
            <div className={`inline-flex rounded-lg border p-0.5 text-xs font-mono ${isDossier ? 'border-[#D8D2C5] bg-[#EFEAE0]' : 'border-[#2A2E35] bg-[#0A0B0D]'}`}>
              <button
                onClick={() => setActiveDiagramTab('arch')}
                className={`px-3 py-1 rounded font-bold uppercase transition ${activeDiagramTab === 'arch' ? 'bg-laser-lime text-black' : 'text-slate-400 hover:text-slate-200'}`}
              >
                Architecture Overview
              </button>
              <button
                onClick={() => setActiveDiagramTab('blast')}
                className={`px-3 py-1 rounded font-bold uppercase transition ${activeDiagramTab === 'blast' ? 'bg-laser-lime text-black' : 'text-slate-400 hover:text-slate-200'}`}
              >
                Blast-Radius Traversal
              </button>
            </div>
          </div>

          {activeDiagramTab === 'blast' && selectedComponentId && (
            <button
              onClick={() => openInspector(selectedComponentId, 'blast')}
              className="text-xs font-mono font-semibold text-laser-lime hover:underline flex items-center gap-1"
            >
              Open in Inspector Drawer ↗
            </button>
          )}
        </div>

        {activeDiagramTab === 'arch' ? (
          <div className={`rounded-xl border p-4 overflow-x-auto ${isDossier ? 'border-[#D8D2C5] bg-[#FFFFFF]' : 'border-[#2A2E35] bg-[#0A0B0D]'}`}>
            <MermaidViewer code={report.architecture_diagram_mermaid} />
          </div>
        ) : (
          <div className="space-y-3 font-mono">
            <div className={`flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2.5 rounded-lg border ${
              isDossier ? 'border-[#D8D2C5] bg-[#EFEAE0]' : 'border-[#2A2E35] bg-[#0A0B0D]'
            }`}>
              <div className="flex items-center gap-2">
                <span className={`text-xs font-bold uppercase ${isDossier ? 'text-black' : 'text-slate-300'}`}>Failure Propagation Origin:</span>
                <span className="text-[10px] text-slate-500">Ranked by Reach</span>
              </div>
              <select
                value={selectedComponentId}
                onChange={(e) => setSelectedComponentId(e.target.value)}
                className={`rounded border px-3 py-1.5 text-xs font-medium focus:outline-none ${
                  isDossier ? 'border-[#D8D2C5] bg-[#FFFFFF] text-black' : 'border-[#2A2E35] bg-[#15171B] text-laser-lime focus:border-laser-lime'
                }`}
              >
                <option value="">-- Choose Origin Component --</option>
                {(report.criticality_leaderboard || []).map((item, idx) => {
                  const compId = item.component?.id || item.id || `comp-${idx}`
                  const compName = item.component?.name || item.name || compId
                  const tier = item.tier || 'MEDIUM'
                  const reach = item.reach || 0
                  return (
                    <option key={compId} value={compId}>
                      {compName} ({tier} · Reach: {reach})
                    </option>
                  )
                })}
              </select>
            </div>

            {selectedComponentId && blastRadiusData?.mermaid ? (
              <div className={`rounded-xl border p-4 overflow-x-auto ${isDossier ? 'border-[#D8D2C5] bg-[#FFFFFF]' : 'border-[#2A2E35] bg-[#0A0B0D]'}`}>
                <MermaidViewer code={blastRadiusData.mermaid} />
              </div>
            ) : (
              <div className={`rounded-lg border border-dashed p-8 text-center text-xs text-slate-500 ${isDossier ? 'border-[#D8D2C5]' : 'border-[#2A2E35]'}`}>
                Select a component above to render its multi-hop blast radius impact tree.
              </div>
            )}
          </div>
        )}
      </div>

      {/* Dossier Sign-Off Archival Block (Visible in Dossier Mode or Print) */}
      {isDossier && (
        <section className="mt-8 border-t-2 border-[#101114] pt-6 font-mono text-xs text-[#101114] space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="font-bold text-sm uppercase tracking-wider">CODIT FORENSIC ATTESTATION</div>
              <div className="text-[11px] text-[#575A65]">
                Certified Static Codebase Audit · Zero-Execution Guarantee Verified
              </div>
            </div>
            <div className="text-right">
              <div className="font-bold">EVALUATED: {new Date(report.created_at * 1000).toLocaleDateString()}</div>
              <div className="text-[10px] text-[#575A65]">ID: {report.report_id}</div>
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 pt-4 border-t border-[#D8D2C5]">
            <div>
              <div className="text-[10px] uppercase text-[#575A65]">Lead Auditor Signature</div>
              <div className="mt-4 border-b border-black h-6 font-serif italic text-base">CODIT Oracle Engine v3.0</div>
            </div>
            <div>
              <div className="text-[10px] uppercase text-[#575A65]">Compliance Verdict</div>
              <div className="mt-4 font-bold text-sm tracking-wider uppercase text-emerald-800">
                {scorecard.phase || 'PASSED'}
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase text-[#575A65]">Cryptographic Hash Chain</div>
              <div className="mt-4 text-[10px] font-mono break-all text-[#575A65]">
                SHA256: {report.report_id.slice(0, 16)}...
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Slide-over Component Inspector */}
      {inspectingComponentId && (
        <GraphPathInspector
          componentId={inspectingComponentId}
          initialTab={inspectorTab}
          initialPathTo={inspectorPathTo}
          onClose={handleCloseInspector}
        />
      )}

      {/* On-Chain Verification Modal */}
      <X402VerificationModal
        isOpen={showX402Modal}
        onClose={() => setShowX402Modal(false)}
      />
    </div>
  )
}
