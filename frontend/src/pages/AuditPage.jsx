import React, { useState, useEffect } from 'react'
import { api, useFetch } from '../api.js'
import { useHashRoute, parseRoute } from '../router.js'
import MermaidViewer from '../components/MermaidViewer.jsx'
import GraphPathInspector from '../components/GraphPathInspector.jsx'
import X402VerificationModal from '../components/X402VerificationModal.jsx'
import { Dot, CritBadge, ConfidenceGauge, EvidenceCitation } from '../components/ui.jsx'

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
        <div className="flex h-12 w-12 items-center justify-center rounded border border-[#1A2438] bg-[#0E1420] text-sky-400 font-mono text-xs font-bold animate-pulse">
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
      <div className="rounded-xl border border-rose-900/60 bg-[#1E0A10] p-8 text-center max-w-lg mx-auto shadow-2xl space-y-4">
        <div className="flex h-10 w-10 mx-auto items-center justify-center rounded border border-rose-700/60 bg-rose-950/40 text-rose-300 font-mono font-black text-sm">
          !
        </div>
        <div className="text-rose-200 font-bold text-sm uppercase tracking-wider font-mono">No Active Audit Report</div>
        <p className="text-xs text-slate-300 leading-relaxed font-sans">
          {error.message || 'No codebase has been ingested yet or the report cache is empty.'}
        </p>
        <div className="pt-2 flex justify-center gap-3">
          <a
            href="#/ingest"
            className="rounded border border-sky-500 bg-sky-500 px-4 py-2 text-xs font-bold font-mono text-slate-950 hover:bg-sky-400 transition"
          >
            Ingest a Codebase →
          </a>
          <button
            onClick={() => handleRunAnalysis(goal)}
            disabled={analyzing}
            className="rounded border border-[#1A2438] bg-[#0E1420] px-4 py-2 text-xs font-semibold font-mono text-slate-300 hover:bg-[#111827] transition"
          >
            {analyzing ? 'Analyzing…' : 'Run Demo Analysis'}
          </button>
        </div>
      </div>
    )
  }

  const scorecard = report?.scorecard || {}
  const roadmap = report?.roadmap || { phases: [] }
  const findings = report?.findings || []
  const mlInsights = report?.ml_insights || {}
  const onnxMetrics = mlInsights.onnx_metrics || {}
  const shapData = mlInsights.shap_explainability || {}

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
    if (searchQuery) {
      const q = searchQuery.toLowerCase()
      const matchText = `${f.description} ${f.evidence_file} ${f.rule_id} ${f.remediation}`.toLowerCase()
      if (!matchText.includes(q)) return false
    }
    return true
  })

  // Phase color badge
  const phaseColors = {
    'Production-track': 'bg-emerald-950/40 text-emerald-400 border-emerald-900/60',
    MVP: 'bg-sky-950/40 text-sky-400 border-sky-900/60',
    Prototype: 'bg-rose-950/40 text-rose-400 border-rose-900/60',
  }
  const phaseBadgeClass = phaseColors[scorecard.phase] || 'bg-[#0E1420] text-slate-300 border-[#1A2438]'

  // SVG Gauge calculations
  const overallScore = scorecard.overall_score || 0
  const radius = 42
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference - (overallScore / 100) * circumference
  const scoreColor = overallScore >= 80 ? '#10b981' : overallScore >= 55 ? '#38bdf8' : '#f43f5e'

  return (
    <div className="space-y-6">
      {/* Cockpit HUD Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 border-b border-[#1A2438] pb-5">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl sm:text-2xl font-black tracking-tight text-slate-50 font-mono">
              Audit Cockpit
            </h1>
            <span className={`inline-flex items-center gap-1.5 rounded border px-2.5 py-0.5 text-xs font-mono font-bold uppercase tracking-wider ${phaseBadgeClass}`}>
              <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" />
              {scorecard.phase || 'AUDITING'}
            </span>
          </div>
          <p className="mt-1.5 text-xs text-slate-400 flex flex-wrap items-center gap-x-2 gap-y-1 font-mono">
            <span>Target: <strong className="text-slate-200">{report.target_name}</strong></span>
            <span className="text-[#1A2438]">|</span>
            <span>Intake: <span className="text-sky-300 uppercase">{report.access_tier?.replace('_', ' ')}</span></span>
            <span className="text-[#1A2438]">|</span>
            <span>Report ID: <span className="text-slate-400">{report.report_id}</span></span>
          </p>
        </div>

        {/* Global Controls & Export Toolbar */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Milestone Target Switcher */}
          <div className="inline-flex rounded border border-[#1A2438] bg-[#0E1420] p-0.5 font-mono">
            <button
              onClick={() => { setGoal('mvp'); handleRunAnalysis('mvp'); }}
              disabled={analyzing}
              className={`px-3 py-1 text-xs font-bold uppercase tracking-wider rounded transition ${
                goal === 'mvp' ? 'bg-sky-500 text-slate-950 shadow-sm' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Goal: MVP
            </button>
            <button
              onClick={() => { setGoal('production'); handleRunAnalysis('production'); }}
              disabled={analyzing}
              className={`px-3 py-1 text-xs font-bold uppercase tracking-wider rounded transition ${
                goal === 'production' ? 'bg-sky-500 text-slate-950 shadow-sm' : 'text-slate-400 hover:text-slate-200'
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
            className="rounded border border-[#1A2438] bg-[#0E1420] px-3 py-1.5 font-mono text-xs font-semibold text-slate-300 hover:bg-[#111827] hover:border-slate-600 transition flex items-center gap-1.5"
            title="Download full audit report as GitHub-flavored Markdown"
          >
            <span>[MD]</span> Markdown
          </a>

          <a
            href={api.getHtmlReportUrl()}
            target="_blank"
            rel="noreferrer"
            className="rounded border border-sky-500 bg-sky-500 px-3 py-1.5 font-mono text-xs font-bold text-slate-950 hover:bg-sky-400 transition shadow-sm flex items-center gap-1.5"
            title="Print or save formal audit report as PDF"
          >
            <span>[PDF]</span> PDF / Print
          </a>

          {/* Additive On-Chain Verification Option */}
          <button
            onClick={() => setShowX402Modal(true)}
            data-testid="onchain-proof-btn"
            className="rounded border border-amber-900/60 bg-amber-950/30 px-3 py-1.5 font-mono text-xs font-bold text-amber-300 hover:bg-amber-950/60 transition flex items-center gap-1.5"
            title="Settle report on Algorand blockchain via x402 protocol"
          >
            <span>[⛓]</span> On-Chain Proof
          </button>
        </div>
      </div>

      {/* Critical Security Lockout Warning */}
      {scorecard.has_critical_blocker && (
        <div className="rounded-xl border border-rose-900/80 bg-[#1E0A10] p-4 text-xs text-rose-300 flex items-start gap-3 shadow-lg">
          <span className="font-mono font-black text-rose-400 text-base leading-none">◆</span>
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
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Card 1: Circular Score Gauge (4 Cols) */}
        <div className="lg:col-span-4 rounded-xl border border-[#1A2438] bg-[#0E1420] p-5 flex flex-col items-center justify-between text-center relative overflow-hidden">
          <div className="absolute top-0 right-0 p-3">
            <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500 font-bold">
              DETERMINISTIC
            </span>
          </div>

          <div className="w-full text-left">
            <span className="text-xs font-bold uppercase tracking-wider font-mono text-slate-400">Readiness Score</span>
            <div className="text-[11px] text-slate-500 mt-0.5 font-sans">Multi-dimensional deterministic rollup</div>
          </div>

          <div className="relative my-4 flex items-center justify-center">
            <svg className="h-32 w-32 -rotate-90 transform" viewBox="0 0 100 100">
              <circle
                cx="50"
                cy="50"
                r={radius}
                className="text-[#1A2438] stroke-current"
                strokeWidth="7"
                fill="transparent"
              />
              <circle
                cx="50"
                cy="50"
                r={radius}
                stroke={scoreColor}
                strokeWidth="7"
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                fill="transparent"
                style={{ transition: 'stroke-dashoffset 0.8s ease-in-out' }}
              />
            </svg>
            <div className="absolute flex flex-col items-center justify-center">
              <span className="text-3xl font-black tracking-tight text-slate-100 font-mono tabular-nums">{overallScore}</span>
              <span className="text-[9px] font-mono text-slate-400 uppercase tracking-widest">OUT OF 100</span>
            </div>
          </div>

          <div className="w-full pt-3 border-t border-[#1A2438] flex items-center justify-between text-xs font-mono">
            <span className="text-slate-400">READINESS TRACK:</span>
            <span className={`font-bold tracking-wider ${overallScore >= 80 ? 'text-emerald-400' : overallScore >= 55 ? 'text-sky-400' : 'text-rose-400'}`}>
              {scorecard.phase}
            </span>
          </div>
        </div>

        {/* Card 2: ONNX Runtime Fragility Model (4 Cols) */}
        <div className="lg:col-span-4 rounded-xl border border-[#1A2438] bg-[#0E1420] p-5 flex flex-col justify-between relative">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider font-mono text-slate-300">
                ONNX FRAGILITY REGRESSOR
              </span>
              <span className="rounded border border-[#1A2438] bg-[#111827] px-2 py-0.5 text-[10px] font-mono text-sky-400">
                {onnxMetrics.runtime_engine || 'onnxruntime v1.30'}
              </span>
            </div>

            <div className="mt-3.5 grid grid-cols-2 gap-2.5">
              <div className="rounded border border-[#1A2438] bg-[#111827] p-3">
                <span className="text-[10px] text-slate-500 uppercase font-mono font-semibold block">Fragility Index</span>
                <span className="text-xl font-bold font-mono text-amber-400 tabular-nums">
                  {onnxMetrics.fragility_score !== undefined ? onnxMetrics.fragility_score : '0.45'}
                </span>
                <span className="text-[9px] text-slate-500 font-mono block">Scale: 0.0 - 1.0</span>
              </div>

              <div className="rounded border border-[#1A2438] bg-[#111827] p-3">
                <span className="text-[10px] text-slate-500 uppercase font-mono font-semibold block">Defect Risk Tier</span>
                <span className={`text-base font-bold font-mono uppercase ${
                  onnxMetrics.defect_risk_tier === 'Critical' ? 'text-rose-400' :
                  onnxMetrics.defect_risk_tier === 'High' ? 'text-orange-400' :
                  onnxMetrics.defect_risk_tier === 'Moderate' ? 'text-amber-400' : 'text-emerald-400'
                }`}>
                  {onnxMetrics.defect_risk_tier || 'Moderate'}
                </span>
                <span className="text-[9px] text-slate-500 font-mono block">Structural Profile</span>
              </div>
            </div>

            <div className="mt-3 space-y-1.5 text-xs font-mono">
              <div className="flex justify-between text-slate-400">
                <span>Maintainability Index:</span>
                <span className="text-slate-200 tabular-nums">{onnxMetrics.maintainability_index ?? 72}/100</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Estimated Remediation:</span>
                <span className="text-sky-300">~{onnxMetrics.estimated_remediation_days ?? 8} Person-Days</span>
              </div>
            </div>
          </div>

          <div className="mt-3 pt-3 border-t border-[#1A2438]">
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
        <div className="lg:col-span-4 rounded-xl border border-[#1A2438] bg-[#0E1420] p-5 flex flex-col justify-between relative">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider font-mono text-slate-300">
                SHAP EXPLAINABILITY
              </span>
              <span className="rounded border border-emerald-900/60 bg-emerald-950/40 px-2 py-0.5 text-[10px] font-mono text-emerald-400">
                GAME THEORY
              </span>
            </div>

            <p className="mt-1.5 text-[11px] text-slate-400 leading-snug font-sans">
              Decomposes how structural AST signals add or subtract points from expected baseline:
            </p>

            <div className="mt-3 space-y-1.5 max-h-40 overflow-y-auto pr-1">
              {(shapData.waterfall || []).map((item, idx) => (
                <div key={idx} className="rounded border border-[#1A2438] bg-[#111827] p-2 text-xs">
                  <div className="flex items-center justify-between font-mono">
                    <span className="font-semibold text-slate-300 text-[11px] truncate max-w-[170px]" title={item.name}>
                      {item.name}
                    </span>
                    <span
                      className={`text-[10px] font-bold px-1.5 py-0.2 rounded border ${
                        item.shap_value < 0 ? 'bg-[#1E0A10] text-[#F43F5E] border-[#5C1220]' : 'bg-emerald-950/40 text-emerald-400 border-emerald-900/60'
                      }`}
                    >
                      {item.shap_value > 0 ? `+${item.shap_value}` : item.shap_value} pts
                    </span>
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5 font-sans leading-tight">{item.rationale}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-3 pt-2.5 border-t border-[#1A2438] flex items-center justify-between text-[10px] text-slate-500 font-mono">
            <span>Baseline E[f(X)]: {shapData.baseline_score ?? 95.0}</span>
            <span>Final Sum: {overallScore}</span>
          </div>
        </div>
      </div>

      {/* 5-Dimension Scorecard Matrix */}
      <div>
        <div className="flex items-center justify-between mb-2.5">
          <h2 className="text-xs font-bold uppercase tracking-wider font-mono text-slate-400">
            Dimensional Maturity Breakdown
          </h2>
          <span className="text-[10px] text-slate-500 font-mono">Click dimension to filter ledger</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5">
          {['security', 'tests', 'scalability', 'duplication', 'maintainability'].map((dim) => {
            const s = (scorecard.dimensions || {})[dim] || { score: 70, findings_count: 0, high_count: 0, critical_count: 0 }
            const isSecCapped = dim === 'security' && scorecard.has_critical_blocker
            const barColor = s.score >= 75 ? 'bg-emerald-500' : s.score >= 50 ? 'bg-sky-500' : 'bg-[#F43F5E]'
            const isSelected = dimFilter === dim

            return (
              <div
                key={dim}
                onClick={() => setDimFilter(isSelected ? 'all' : dim)}
                className={`rounded-lg border p-3 flex flex-col justify-between space-y-2.5 cursor-pointer transition ${
                  isSelected
                    ? 'border-sky-500 bg-[#151E30]'
                    : 'border-[#1A2438] bg-[#0E1420] hover:border-[#2A3B57]'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold uppercase tracking-wider font-mono text-slate-200">{dim}</span>
                    {s.critical_count > 0 && (
                      <span className="rounded border border-[#5C1220] bg-[#1E0A10] px-1.5 py-0.2 text-[9px] font-bold font-mono text-[#F43F5E]">
                        {s.critical_count} CRIT
                      </span>
                    )}
                  </div>

                  <div className="mt-1.5 flex items-baseline gap-1 font-mono">
                    <span className={`text-xl font-black tracking-tight ${isSecCapped ? 'text-rose-400' : 'text-slate-100'} tabular-nums`}>
                      {s.score}
                    </span>
                    <span className="text-[10px] text-slate-500">/100</span>
                  </div>

                  <div className="w-full bg-[#111827] h-1 rounded-full overflow-hidden mt-2">
                    <div className={`h-full rounded-full ${barColor}`} style={{ width: `${Math.max(5, s.score)}%` }} />
                  </div>
                </div>

                <div className="flex items-center justify-between text-[10px] text-slate-500 pt-1 border-t border-[#1A2438] font-mono">
                  <span>{s.findings_count} findings</span>
                  <span>{s.high_count} high</span>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Prioritized Engineering Roadmap */}
      <div className="rounded-xl border border-[#1A2438] bg-[#0E1420] p-5 space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-[#1A2438] pb-3">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wider font-mono text-slate-100 flex items-center gap-2">
              <span className="text-sky-400">🗺️</span> Prioritized Engineering Roadmap
            </h2>
            <p className="mt-0.5 text-xs text-slate-400 font-sans">{roadmap.summary_narrative}</p>
          </div>
          <span className="rounded border border-sky-900/60 bg-sky-950/40 px-2.5 py-0.5 text-[11px] font-mono font-bold text-sky-400 self-start sm:self-auto">
            TARGET: {roadmap.goal?.toUpperCase() || 'PRODUCTION'}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {(roadmap.phases || [
            { phase_name: 'Phase 1 - Immediate', target_timeline: 'Week 1', actions: [] },
            { phase_name: 'Phase 2 - Hardening', target_timeline: 'Week 2-3', actions: [] },
            { phase_name: 'Phase 3 - Scale', target_timeline: 'Month 1', actions: [] },
          ]).map((phase, idx) => (
            <div key={idx} className="rounded-lg border border-[#1A2438] bg-[#111827] p-3.5 flex flex-col justify-between space-y-3">
              <div>
                <div className="flex items-center justify-between text-xs font-bold font-mono text-slate-200">
                  <span className="flex items-center gap-1.5 uppercase">
                    <span className="flex h-4 w-4 items-center justify-center rounded bg-[#1A2438] text-sky-400 text-[9px] font-bold">
                      {idx + 1}
                    </span>
                    {phase.phase_name}
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">{phase.target_timeline}</span>
                </div>

                <div className="mt-2.5 space-y-2">
                  {(phase.actions || []).map((act, aIdx) => (
                    <div key={aIdx} className="rounded border border-[#1A2438] bg-[#0E1420] p-2.5 text-xs space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-slate-200 font-mono text-[11px] truncate max-w-[160px]">{act.title}</span>
                        <span className="text-[9px] font-mono text-sky-400 bg-sky-950/40 px-1 py-0.2 rounded border border-sky-900/40">
                          {act.effort_estimate || (idx === 0 ? 'P0 - Critical' : idx === 1 ? 'P1 - High' : 'P2 - Medium')}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400 leading-snug font-sans">{act.description}</p>
                      {act.impacted_components?.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1 pt-1 border-t border-[#1A2438]">
                          {act.impacted_components.map((c, cIdx) => (
                            <button
                              key={cIdx}
                              onClick={() => openInspector(c, 'deps')}
                              className="rounded bg-[#111827] border border-[#1A2438] px-1.5 py-0.2 text-[9px] font-mono text-sky-400 hover:text-sky-300 transition"
                              title="Click to inspect component graph & paths"
                            >
                              {c} ↗
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                  {(!phase.actions || phase.actions.length === 0) && (
                    <div className="rounded border border-[#1A2438] bg-[#0E1420] p-2.5 text-xs font-mono">
                      <span className="text-[10px] text-slate-500 block">P{idx} - Status Verification</span>
                      <p className="text-[11px] text-slate-400 mt-1">Milestone governance review underway.</p>
                    </div>
                  )}
                </div>
              </div>

              <div className="pt-2 border-t border-[#1A2438] text-[10px] text-slate-500 flex justify-between font-mono">
                <span>STATUS: PENDING</span>
                <span className="font-semibold text-slate-400">{phase.actions?.length || 0} Actions</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Evidenced Findings Ledger */}
      <div className="rounded-xl border border-[#1A2438] bg-[#0E1420] p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-[#1A2438] pb-3">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wider font-mono text-slate-100 flex items-center gap-2">
              <span>🔍</span> Evidenced Findings Catalog
              <span className="rounded border border-[#1A2438] bg-[#111827] px-2 py-0.5 text-[10px] text-slate-400 font-mono">
                {filteredFindings.length} OF {findings.length}
              </span>
            </h2>
            <p className="text-xs text-slate-400 mt-0.5 font-sans">
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
                      ? 'bg-sky-500 text-slate-950'
                      : 'bg-[#111827] border border-[#1A2438] text-slate-400 hover:text-slate-200'
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
            className="w-full rounded border border-[#1A2438] bg-[#080B11] px-3.5 py-2 text-xs text-slate-100 placeholder-slate-500 focus:border-sky-500 focus:outline-none"
          />

          <select
            value={dimFilter}
            onChange={(e) => setDimFilter(e.target.value)}
            className="rounded border border-[#1A2438] bg-[#080B11] px-3 py-2 text-xs text-slate-200 focus:border-sky-500 focus:outline-none uppercase"
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
          <div className="rounded border border-dashed border-[#1A2438] p-8 text-center text-xs text-slate-500 font-mono">
            No audit findings match your selected filters.
          </div>
        ) : (
          <div className="overflow-x-auto rounded border border-[#1A2438]">
            <table className="w-full text-left text-xs font-mono">
              <thead className="border-b border-[#1A2438] bg-[#111827] text-slate-400 text-[10px] uppercase tracking-wider">
                <tr>
                  <th scope="col" className="px-3.5 py-2.5">SEVERITY</th>
                  <th scope="col" className="px-3.5 py-2.5">RULE ID</th>
                  <th scope="col" className="px-3.5 py-2.5">AST CITATION</th>
                  <th scope="col" className="px-3.5 py-2.5">CONFIDENCE</th>
                  <th scope="col" className="px-3.5 py-2.5">DESCRIPTION</th>
                  <th scope="col" className="px-3.5 py-2.5 text-right">ACTION</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1A2438] bg-[#0E1420]">
                {filteredFindings.map((f, idx) => {
                  const isExpanded = expandedFinding === idx
                  const confidenceLevel = f.confidence || (f.severity.toLowerCase() === 'critical' ? 'high' : 'medium')
                  return (
                    <React.Fragment key={idx}>
                      <tr
                        onClick={() => setExpandedFinding(isExpanded ? null : idx)}
                        className={`cursor-pointer transition hover:bg-[#111827] ${isExpanded ? 'bg-[#151E30]' : ''}`}
                      >
                        <td className="px-3.5 py-3 whitespace-nowrap">
                          <CritBadge tier={f.severity} />
                        </td>
                        <td className="px-3.5 py-3 whitespace-nowrap text-sky-400 font-bold">
                          {f.rule_id}
                        </td>
                        <td className="px-3.5 py-3 whitespace-nowrap">
                          <code className="rounded bg-[#080B11] border border-[#1A2438] px-2 py-0.5 text-slate-200">
                            {f.evidence_file}:{f.evidence_line ?? 1}
                          </code>
                        </td>
                        <td className="px-3.5 py-3 whitespace-nowrap">
                          <ConfidenceGauge level={confidenceLevel} label={true} />
                        </td>
                        <td className="px-3.5 py-3 max-w-md">
                          <p className="truncate text-slate-200 font-sans" title={f.description}>
                            {f.description}
                          </p>
                        </td>
                        <td className="px-3.5 py-3 text-right whitespace-nowrap space-x-1.5" onClick={(e) => e.stopPropagation()}>
                          <button
                            type="button"
                            onClick={() => copyText(`${f.evidence_file}:${f.evidence_line ?? 1}`, `cit-${idx}`)}
                            className="rounded border border-[#1A2438] bg-[#111827] px-2 py-0.5 text-[10px] text-slate-400 hover:text-slate-200 transition"
                          >
                            {copiedId === `cit-${idx}` ? '✓ Copied' : 'Copy'}
                          </button>
                          <button
                            type="button"
                            onClick={() => openInspector(f.evidence_file, 'deps')}
                            className="rounded border border-[#0C3852] bg-[#071927] px-2 py-0.5 text-[10px] font-bold text-sky-400 hover:text-sky-300 transition"
                            title="Inspect component in openCypher graph drawer"
                          >
                            Inspect ↗
                          </button>
                        </td>
                      </tr>

                      {/* Expandable Evidence Detail Row */}
                      {isExpanded && (
                        <tr className="bg-[#080B11]">
                          <td colSpan="6" className="p-4 border-b border-[#1A2438]">
                            <div className="space-y-3 font-sans">
                              <div>
                                <span className="font-mono text-[10px] uppercase tracking-wider text-slate-400 block mb-1">
                                  Full Diagnostic Summary:
                                </span>
                                <p className="text-xs text-slate-200 leading-relaxed">{f.description}</p>
                              </div>

                              {f.snippet && (
                                <div>
                                  <span className="font-mono text-[10px] uppercase tracking-wider text-slate-400 block mb-1">
                                    AST Evidence Snippet ({f.evidence_file}:{f.evidence_line ?? 1}):
                                  </span>
                                  <div className="rounded border border-[#1A2438] bg-[#0E1420] p-3 font-mono text-xs text-slate-300 overflow-x-auto">
                                    <pre className="text-[11px] leading-snug">{f.snippet}</pre>
                                  </div>
                                </div>
                              )}

                              {f.remediation && (
                                <div className="rounded border border-[#1A2438] bg-[#0E1420] p-3 space-y-1.5">
                                  <div className="flex items-center justify-between font-mono">
                                    <span className="text-[11px] font-bold text-sky-300 flex items-center gap-1.5">
                                      <span>💡</span> Remediation Guidance:
                                    </span>
                                    <button
                                      type="button"
                                      onClick={() => copyText(f.remediation, `rem-${idx}`)}
                                      className="rounded border border-[#1A2438] bg-[#111827] px-2 py-0.5 text-[10px] text-sky-400 hover:text-sky-200 transition"
                                    >
                                      {copiedId === `rem-${idx}` ? '✓ Copied' : 'Copy Fix'}
                                    </button>
                                  </div>
                                  <p className="text-slate-300 text-xs leading-relaxed font-sans">{f.remediation}</p>
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
      <div className="rounded-xl border border-[#1A2438] bg-[#0E1420] p-5 space-y-3.5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-[#1A2438] pb-3">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wider font-mono text-slate-100 flex items-center gap-2">
              <span className="text-amber-400">⚡</span> Component Criticality Leaderboard
            </h2>
            <p className="text-xs text-slate-400 font-sans">
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
                className="group rounded-lg border border-[#1A2438] bg-[#111827] p-3 space-y-2 cursor-pointer transition hover:border-sky-500/60 hover:bg-[#151E30]"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 min-w-0">
                    <Dot type={compType} />
                    <span className="truncate font-mono font-bold text-xs text-slate-200 group-hover:text-sky-300">
                      {compName}
                    </span>
                  </div>
                  <CritBadge tier={tier} size="xs" />
                </div>

                <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
                  <span>Reach: <strong className="text-sky-400">{reach} nodes</strong></span>
                  <span className="text-slate-500 group-hover:text-sky-300 font-semibold">Neighborhood ↗</span>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Diagrams Section */}
      <div className="rounded-xl border border-[#1A2438] bg-[#0E1420] p-5 space-y-3.5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-[#1A2438] pb-3">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-bold uppercase tracking-wider font-mono text-slate-100">
              Architecture & Blast Radius Blueprint
            </h2>
            <div className="inline-flex rounded border border-[#1A2438] bg-[#080B11] p-0.5 text-xs font-mono">
              <button
                onClick={() => setActiveDiagramTab('arch')}
                className={`px-3 py-1 rounded font-bold uppercase transition ${activeDiagramTab === 'arch' ? 'bg-sky-500 text-slate-950' : 'text-slate-400 hover:text-slate-200'}`}
              >
                Architecture Overview
              </button>
              <button
                onClick={() => setActiveDiagramTab('blast')}
                className={`px-3 py-1 rounded font-bold uppercase transition ${activeDiagramTab === 'blast' ? 'bg-sky-500 text-slate-950' : 'text-slate-400 hover:text-slate-200'}`}
              >
                Blast-Radius Traversal
              </button>
            </div>
          </div>

          {activeDiagramTab === 'blast' && selectedComponentId && (
            <button
              onClick={() => openInspector(selectedComponentId, 'blast')}
              className="text-xs font-mono font-semibold text-sky-400 hover:text-sky-300 flex items-center gap-1"
            >
              Open in Inspector Drawer ↗
            </button>
          )}
        </div>

        {activeDiagramTab === 'arch' ? (
          <div className="rounded border border-[#1A2438] bg-[#080B11] p-4 overflow-x-auto">
            <MermaidViewer code={report.architecture_diagram_mermaid} />
          </div>
        ) : (
          <div className="space-y-3 font-mono">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 bg-[#080B11] p-2.5 rounded border border-[#1A2438]">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-slate-300 uppercase">Failure Propagation Origin:</span>
                <span className="text-[10px] text-slate-500">Ranked by Reach</span>
              </div>
              <select
                value={selectedComponentId}
                onChange={(e) => setSelectedComponentId(e.target.value)}
                className="rounded border border-[#1A2438] bg-[#111827] px-3 py-1.5 text-xs font-medium text-sky-400 focus:border-sky-500 focus:outline-none"
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
              <div className="rounded border border-[#1A2438] bg-[#080B11] p-4 overflow-x-auto">
                <MermaidViewer code={blastRadiusData.mermaid} />
              </div>
            ) : (
              <div className="rounded border border-dashed border-[#1A2438] p-8 text-center text-xs text-slate-500">
                Select a component above to render its multi-hop blast radius impact tree.
              </div>
            )}
          </div>
        )}
      </div>

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
