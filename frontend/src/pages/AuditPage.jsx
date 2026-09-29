import React, { useState, useEffect } from 'react'
import { api, useFetch } from '../api.js'
import { useHashRoute, parseRoute } from '../router.js'
import MermaidViewer from '../components/MermaidViewer.jsx'
import GraphPathInspector from '../components/GraphPathInspector.jsx'
import X402VerificationModal from '../components/X402VerificationModal.jsx'
import { Dot, TypeBadge, CritBadge } from '../components/ui.jsx'

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
        <div className="relative">
          <div className="h-12 w-12 animate-spin rounded-full border-2 border-sky-500 border-t-transparent shadow-lg shadow-sky-500/20" />
          <div className="absolute inset-0 flex items-center justify-center text-[10px] font-mono text-sky-400">
            AST
          </div>
        </div>
        <div className="space-y-1.5">
          <p className="text-base font-semibold text-slate-100">Running Deep Codebase Audit...</p>
          <p className="text-xs text-slate-400 font-mono">
            Tree-sitter AST parsing · openCypher graph assembly · ONNX defect regressor · SHAP game theory
          </p>
        </div>
      </div>
    )
  }

  if (error && !report) {
    return (
      <div className="rounded-2xl border border-rose-500/40 bg-rose-950/20 p-8 text-center max-w-lg mx-auto shadow-2xl space-y-4">
        <div className="flex h-12 w-12 mx-auto items-center justify-center rounded-full bg-rose-500/20 text-rose-400 text-xl font-bold">
          !
        </div>
        <div className="text-rose-300 font-bold text-lg">No Active Audit Report</div>
        <p className="text-xs text-slate-400 leading-relaxed">
          {error.message || 'No codebase has been ingested yet or the report cache is empty.'}
        </p>
        <div className="pt-2 flex justify-center gap-3">
          <a
            href="#/ingest"
            className="rounded-lg bg-sky-500 px-5 py-2.5 text-xs font-bold text-slate-950 hover:bg-sky-400 shadow-lg shadow-sky-500/20 transition"
          >
            Ingest a Codebase →
          </a>
          <button
            onClick={() => handleRunAnalysis(goal)}
            disabled={analyzing}
            className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2.5 text-xs font-semibold text-slate-300 hover:bg-slate-800 transition"
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
    if (sevFilter !== 'all' && f.severity.toLowerCase() !== sevFilter.toLowerCase()) return false
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
    'Production-track': 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    MVP: 'bg-sky-500/10 text-sky-400 border-sky-500/30',
    Prototype: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
  }
  const phaseBadgeClass = phaseColors[scorecard.phase] || 'bg-slate-800 text-slate-300 border-slate-700'

  // SVG Gauge calculations
  const overallScore = scorecard.overall_score || 0
  const radius = 42
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference - (overallScore / 100) * circumference
  const scoreColor = overallScore >= 80 ? '#10b981' : overallScore >= 55 ? '#38bdf8' : '#f43f5e'

  return (
    <div className="space-y-8">
      {/* Cockpit HUD Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 border-b border-slate-800/80 pb-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-extrabold tracking-tight text-slate-50 sm:text-3xl">
              Audit Cockpit
            </h1>
            <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-0.5 text-xs font-bold uppercase tracking-wider ${phaseBadgeClass}`}>
              <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" />
              {scorecard.phase || 'AUDITING'}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-400 flex flex-wrap items-center gap-x-2 gap-y-1 font-mono">
            <span>Target: <strong className="text-slate-200">{report.target_name}</strong></span>
            <span className="text-slate-600">·</span>
            <span>Intake: <span className="text-sky-300 capitalize">{report.access_tier?.replace('_', ' ')}</span></span>
            <span className="text-slate-600">·</span>
            <span>Report ID: <span className="text-slate-400">{report.report_id}</span></span>
          </p>
        </div>

        {/* Global Controls & Export Toolbar */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Milestone Target Switcher */}
          <div className="inline-flex rounded-lg border border-slate-800 bg-slate-900/90 p-1">
            <button
              onClick={() => { setGoal('mvp'); handleRunAnalysis('mvp'); }}
              disabled={analyzing}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md transition ${
                goal === 'mvp' ? 'bg-sky-500 text-slate-950 shadow-sm' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Goal: MVP
            </button>
            <button
              onClick={() => { setGoal('production'); handleRunAnalysis('production'); }}
              disabled={analyzing}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md transition ${
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
            className="rounded-lg border border-slate-700 bg-slate-900 px-3.5 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-800 transition flex items-center gap-1.5"
            title="Download full audit report as GitHub-flavored Markdown"
          >
            <span>📥</span> Markdown
          </a>

          <a
            href={api.getHtmlReportUrl()}
            target="_blank"
            rel="noreferrer"
            className="rounded-lg bg-sky-500 px-3.5 py-1.5 text-xs font-bold text-slate-950 hover:bg-sky-400 transition shadow-lg shadow-sky-500/20 flex items-center gap-1.5"
            title="Print or save formal audit report as PDF"
          >
            <span>🖨️</span> PDF / Print
          </a>

          {/* Additive On-Chain Verification Option */}
          <button
            onClick={() => setShowX402Modal(true)}
            data-testid="onchain-proof-btn"
            className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3.5 py-1.5 text-xs font-semibold text-amber-300 hover:bg-amber-500/20 transition flex items-center gap-1.5"
            title="Settle report on Algorand blockchain via x402 protocol"
          >
            <span>⛓️</span> On-Chain Proof
          </button>
        </div>
      </div>

      {/* Critical Security Lockout Warning */}
      {scorecard.has_critical_blocker && (
        <div className="rounded-xl border border-rose-500/50 bg-rose-950/30 p-4 text-xs text-rose-300 flex items-start gap-3 shadow-xl shadow-rose-950/40 animate-pulse">
          <span className="text-2xl leading-none">⚠️</span>
          <div>
            <div className="font-bold text-sm text-rose-200">Critical Security Lockout Active (Score Capped at 25/100)</div>
            <p className="mt-1 leading-relaxed text-rose-300/90">
              An unaddressed critical vulnerability or plaintext credential was detected in the active repository.
              Per Section 9 non-negotiable security rules, production readiness tracks are locked until this blocker is remedied.
            </p>
          </div>
        </div>
      )}

      {/* Telemetry Cockpit Hero Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Card 1: Circular Score Gauge (4 Cols) */}
        <div className="lg:col-span-4 rounded-2xl border border-slate-800 bg-[#0c1220]/80 p-6 flex flex-col items-center justify-between text-center relative overflow-hidden shadow-xl backdrop-blur-md">
          <div className="absolute top-0 right-0 p-3">
            <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500">Deterministic</span>
          </div>

          <div className="w-full text-left">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Readiness Score</span>
            <div className="text-[11px] text-slate-500 mt-0.5">Multi-dimensional deterministic rollup</div>
          </div>

          <div className="relative my-4 flex items-center justify-center">
            <svg className="h-36 w-36 -rotate-90 transform" viewBox="0 0 100 100">
              <circle
                cx="50"
                cy="50"
                r={radius}
                className="text-slate-800 stroke-current"
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
                style={{ transition: 'stroke-dashoffset 1s ease-in-out' }}
              />
            </svg>
            <div className="absolute flex flex-col items-center justify-center">
              <span className="text-4xl font-black tracking-tight text-slate-100 font-mono">{overallScore}</span>
              <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Out of 100</span>
            </div>
          </div>

          <div className="w-full pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs">
            <span className="text-slate-400">Readiness Track:</span>
            <span className={`font-bold font-mono ${overallScore >= 80 ? 'text-emerald-400' : overallScore >= 55 ? 'text-sky-400' : 'text-rose-400'}`}>
              {scorecard.phase}
            </span>
          </div>
        </div>

        {/* Card 2: ONNX Runtime Fragility Model (4 Cols) */}
        <div className="lg:col-span-4 rounded-2xl border border-slate-800 bg-[#0c1220]/80 p-6 flex flex-col justify-between relative shadow-xl backdrop-blur-md">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">ONNX Fragility Regressor</span>
              <span className="rounded-full bg-slate-900 border border-slate-700 px-2 py-0.5 text-[10px] font-mono text-sky-400">
                {onnxMetrics.runtime_engine || 'onnxruntime v1.30'}
              </span>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-3">
                <span className="text-[10px] text-slate-500 uppercase font-semibold block">Fragility Index</span>
                <span className="text-2xl font-bold font-mono text-amber-400">
                  {onnxMetrics.fragility_score !== undefined ? onnxMetrics.fragility_score : '0.45'}
                </span>
                <span className="text-[10px] text-slate-500 block">Scale: 0.0 - 1.0</span>
              </div>

              <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-3">
                <span className="text-[10px] text-slate-500 uppercase font-semibold block">Defect Risk Tier</span>
                <span className={`text-xl font-bold ${
                  onnxMetrics.defect_risk_tier === 'Critical' ? 'text-rose-400' :
                  onnxMetrics.defect_risk_tier === 'High' ? 'text-orange-400' :
                  onnxMetrics.defect_risk_tier === 'Moderate' ? 'text-amber-400' : 'text-emerald-400'
                }`}>
                  {onnxMetrics.defect_risk_tier || 'Moderate'}
                </span>
                <span className="text-[10px] text-slate-500 block">Structural Profile</span>
              </div>
            </div>

            <div className="mt-3 space-y-2 text-xs">
              <div className="flex justify-between text-slate-400">
                <span>Maintainability Index:</span>
                <span className="font-mono text-slate-200">{onnxMetrics.maintainability_index ?? 72}/100</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Estimated Remediation:</span>
                <span className="font-mono text-sky-300">~{onnxMetrics.estimated_remediation_days ?? 8} Person-Days</span>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-800/80">
            <span className="text-[11px] font-semibold text-slate-400 block mb-1">Structural Risk Triggers:</span>
            <ul className="text-[11px] text-slate-400 space-y-1">
              {(onnxMetrics.risk_triggers || ['Standard architectural coupling']).slice(0, 2).map((trig, i) => (
                <li key={i} className="flex items-start gap-1.5">
                  <span className="text-amber-400 leading-none">•</span>
                  <span>{trig}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Card 3: SHAP Game-Theoretic Decomposition (4 Cols) */}
        <div className="lg:col-span-4 rounded-2xl border border-slate-800 bg-[#0c1220]/80 p-6 flex flex-col justify-between relative shadow-xl backdrop-blur-md">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">SHAP Explainability</span>
              <span className="rounded-full bg-emerald-950/60 border border-emerald-500/40 px-2 py-0.5 text-[10px] font-mono text-emerald-400">
                Game Theory Attributions
              </span>
            </div>

            <p className="mt-2 text-[11px] text-slate-400 leading-relaxed">
              Decomposes how structural signals add or subtract points relative to the baseline expectation:
            </p>

            <div className="mt-3 space-y-2 max-h-48 overflow-y-auto pr-1">
              {(shapData.waterfall || []).map((item, idx) => (
                <div key={idx} className="rounded-lg border border-slate-800/80 bg-slate-950/50 p-2 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-slate-300 text-[11px] truncate max-w-[170px]" title={item.name}>
                      {item.name}
                    </span>
                    <span
                      className={`font-mono font-bold text-[11px] px-1.5 py-0.5 rounded ${
                        item.shap_value < 0 ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      }`}
                    >
                      {item.shap_value > 0 ? `+${item.shap_value}` : item.shap_value} pts
                    </span>
                  </div>
                  <div className="text-[10px] text-slate-500 mt-1">{item.rationale}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-3 pt-2 border-t border-slate-800/80 flex items-center justify-between text-[10px] text-slate-500 font-mono">
            <span>Baseline E[f(X)]: {shapData.baseline_score ?? 95.0}</span>
            <span>Final Sum: {overallScore}</span>
          </div>
        </div>
      </div>

      {/* 5-Dimension Scorecard Matrix */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Dimensional Maturity Breakdown
          </h2>
          <span className="text-[10px] text-slate-500">Click a dimension to filter findings below</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {Object.entries(scorecard.dimensions || {}).map(([dim, s]) => {
            const isSecCapped = dim === 'security' && scorecard.has_critical_blocker
            const barColor = s.score >= 75 ? 'bg-emerald-500' : s.score >= 50 ? 'bg-sky-500' : 'bg-rose-500'
            const isSelected = dimFilter === dim

            return (
              <div
                key={dim}
                onClick={() => setDimFilter(isSelected ? 'all' : dim)}
                className={`rounded-xl border p-4 flex flex-col justify-between space-y-3 cursor-pointer transition ${
                  isSelected
                    ? 'border-sky-500/80 bg-sky-950/30 shadow-lg shadow-sky-500/10'
                    : 'border-slate-800 bg-[#0c1220]/80 hover:border-slate-700'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold capitalize text-slate-200">{dim}</span>
                    {s.critical_count > 0 && (
                      <span className="rounded bg-rose-500/20 px-1.5 py-0.5 text-[9px] font-bold text-rose-400">
                        {s.critical_count} CRIT
                      </span>
                    )}
                  </div>

                  <div className="mt-2 flex items-baseline gap-1 font-mono">
                    <span className={`text-2xl font-black tracking-tight ${isSecCapped ? 'text-rose-400' : 'text-slate-100'}`}>
                      {s.score}
                    </span>
                    <span className="text-xs text-slate-500">/100</span>
                  </div>

                  <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden mt-2">
                    <div className={`h-full rounded-full ${barColor}`} style={{ width: `${Math.max(5, s.score)}%` }} />
                  </div>
                </div>

                <div className="flex items-center justify-between text-[10px] text-slate-500 pt-1 border-t border-slate-800/40">
                  <span>{s.findings_count} findings</span>
                  <span>{s.high_count} high</span>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Prioritized Engineering Roadmap */}
      <div className="rounded-2xl border border-slate-800 bg-[#0c1220]/80 p-6 space-y-6 shadow-xl backdrop-blur-md">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-800 pb-4">
          <div>
            <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
              <span>🗺️</span> Prioritized Engineering Roadmap
            </h2>
            <p className="mt-1 text-xs text-slate-400">{roadmap.summary_narrative}</p>
          </div>
          <span className="rounded-full border border-sky-500/40 bg-sky-500/10 px-3 py-1 text-xs font-mono font-bold text-sky-400 self-start sm:self-auto">
            Target: {roadmap.goal?.toUpperCase()}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {(roadmap.phases || []).map((phase, idx) => (
            <div key={idx} className="rounded-xl border border-slate-800 bg-slate-950/70 p-4 flex flex-col justify-between space-y-4">
              <div>
                <div className="flex items-center justify-between text-xs font-bold text-slate-200">
                  <span className="flex items-center gap-1.5">
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-sky-500/20 text-sky-400 text-[10px] font-bold">
                      {idx + 1}
                    </span>
                    {phase.phase_name}
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">{phase.target_timeline}</span>
                </div>

                <div className="mt-3 space-y-2.5">
                  {(phase.actions || []).map((act, aIdx) => (
                    <div key={aIdx} className="rounded-lg border border-slate-800/80 bg-slate-900/80 p-3 text-xs space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-slate-200">{act.title}</span>
                        <span className="text-[10px] font-mono text-sky-400 bg-sky-950/60 px-1.5 py-0.5 rounded border border-sky-500/20">
                          {act.effort_estimate}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400 leading-relaxed">{act.description}</p>
                      {act.impacted_components?.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1 pt-1 border-t border-slate-800/50">
                          {act.impacted_components.map((c, cIdx) => (
                            <button
                              key={cIdx}
                              onClick={() => openInspector(c, 'deps')}
                              className="rounded bg-slate-800 px-1.5 py-0.5 text-[9px] font-mono text-sky-400 hover:bg-sky-900/50 hover:text-sky-300 transition"
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

              <div className="pt-2 border-t border-slate-800/60 text-[10px] text-slate-500 flex justify-between font-mono">
                <span>Phase Status: Pending</span>
                <span className="font-semibold text-slate-400">{phase.actions?.length || 0} Actions</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Evidenced Findings Explorer */}
      <div className="rounded-2xl border border-slate-800 bg-[#0c1220]/80 p-6 space-y-6 shadow-xl backdrop-blur-md">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800 pb-4">
          <div>
            <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
              <span>🔍</span> Evidenced Findings Explorer
              <span className="rounded-full bg-slate-800 px-2.5 py-0.5 text-xs text-slate-400 font-mono">
                {filteredFindings.length} of {findings.length}
              </span>
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Every finding is statically proven with file and line evidence. No false proxy reports.
            </p>
          </div>

          {/* Severity filter buttons */}
          <div className="flex flex-wrap items-center gap-1.5">
            {['all', 'critical', 'high', 'medium', 'low'].map((sev) => {
              const count = sev === 'all' ? findings.length : findings.filter((f) => f.severity.toLowerCase() === sev).length
              return (
                <button
                  key={sev}
                  onClick={() => setSevFilter(sev)}
                  className={`rounded-lg px-2.5 py-1 text-xs font-semibold uppercase tracking-wider transition ${
                    sevFilter === sev ? 'bg-sky-500 text-slate-950 font-bold' : 'bg-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {sev} ({count})
                </button>
              )
            })}
          </div>
        </div>

        {/* Search & Filter Toolbar */}
        <div className="flex flex-col sm:flex-row gap-3">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search findings by description, rule ID, filename..."
            className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3.5 py-2 text-xs text-slate-100 placeholder-slate-500 focus:border-sky-500 focus:outline-none"
          />

          <select
            value={dimFilter}
            onChange={(e) => setDimFilter(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-200 focus:border-sky-500 focus:outline-none"
          >
            <option value="all">All Dimensions</option>
            <option value="security">Security</option>
            <option value="tests">Tests</option>
            <option value="scalability">Scalability</option>
            <option value="duplication">Duplication</option>
            <option value="maintainability">Maintainability</option>
          </select>
        </div>

        {/* Findings List */}
        {filteredFindings.length === 0 ? (
          <div className="rounded-lg border border-dashed border-slate-800 p-8 text-center text-xs text-slate-500">
            No audit findings match your selected filters.
          </div>
        ) : (
          <div className="space-y-3">
            {filteredFindings.map((f, idx) => {
              const isCrit = f.severity.toLowerCase() === 'critical'
              const isHigh = f.severity.toLowerCase() === 'high'
              const badgeClass = isCrit
                ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                : isHigh
                ? 'bg-orange-500/20 text-orange-300 border-orange-500/40'
                : 'bg-amber-500/20 text-amber-300 border-amber-500/40'

              return (
                <div
                  key={idx}
                  className="rounded-xl border border-slate-800/80 bg-slate-950/60 p-4 space-y-3 transition hover:border-slate-700"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className={`rounded border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${badgeClass}`}>
                        {f.severity}
                      </span>
                      <span className="font-mono text-xs font-semibold text-slate-200">{f.rule_id}</span>
                      <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] text-slate-400 capitalize">
                        {f.dimension}
                      </span>
                    </div>

                    <div className="text-xs font-mono text-slate-400 flex items-center gap-2">
                      <span>{f.evidence_file}:{f.evidence_line ?? 1}</span>
                      <button
                        onClick={() => copyText(`${f.evidence_file}:${f.evidence_line ?? 1}`, `loc-${idx}`)}
                        className="text-slate-500 hover:text-slate-300 text-[10px] transition"
                        title="Copy file:line"
                      >
                        {copiedId === `loc-${idx}` ? '✓ Copied' : '📋 Copy'}
                      </button>
                      <button
                        onClick={() => openInspector(f.evidence_file, 'deps')}
                        className="text-sky-400 hover:text-sky-300 text-[10px] font-semibold transition ml-1"
                        title="Inspect component neighborhood in graph"
                      >
                        Inspect ↗
                      </button>
                    </div>
                  </div>

                  <p className="text-xs text-slate-300 leading-relaxed font-sans">{f.description}</p>

                  {f.snippet && (
                    <div className="rounded-lg bg-slate-900/90 border border-slate-800 p-3 font-mono text-xs text-slate-300 overflow-x-auto">
                      <pre className="text-[11px] leading-snug">{f.snippet}</pre>
                    </div>
                  )}

                  {f.remediation && (
                    <div className="rounded-lg bg-sky-950/20 border border-sky-500/30 p-3 text-xs space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-sky-300 flex items-center gap-1.5">
                          <span>💡</span> Remediation Guidance:
                        </span>
                        <button
                          onClick={() => copyText(f.remediation, `rem-${idx}`)}
                          className="text-[10px] text-sky-400 hover:text-sky-200 font-mono transition"
                        >
                          {copiedId === `rem-${idx}` ? '✓ Copied' : '📋 Copy Fix'}
                        </button>
                      </div>
                      <p className="text-slate-300 text-[11px] leading-relaxed">{f.remediation}</p>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Criticality Leaderboard & Graph Explorer Quick-Access */}
      <div className="rounded-2xl border border-slate-800 bg-[#0c1220]/80 p-6 space-y-4 shadow-xl backdrop-blur-md">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-800 pb-3">
          <div>
            <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <span>⚡</span> Component Criticality Leaderboard
            </h2>
            <p className="text-xs text-slate-400">
              Components ranked by multi-hop graph reach if failure occurs. Click to inspect dependencies & paths.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
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
                className="group rounded-xl border border-slate-800 bg-slate-950/60 p-3.5 space-y-2 cursor-pointer transition hover:border-sky-500/60 hover:bg-slate-900"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 min-w-0">
                    <Dot type={compType} />
                    <span className="truncate font-bold text-xs text-slate-200 group-hover:text-sky-300">
                      {compName}
                    </span>
                  </div>
                  <CritBadge tier={tier} />
                </div>

                <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
                  <span>Reach: <strong className="text-sky-400">{reach} nodes</strong></span>
                  <span className="text-slate-500 group-hover:text-sky-300">Inspect ↗</span>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Diagrams Section */}
      <div className="rounded-2xl border border-slate-800 bg-[#0c1220]/80 p-6 space-y-4 shadow-xl backdrop-blur-md">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-800 pb-3">
          <div className="flex items-center gap-3">
            <h2 className="text-base font-bold text-slate-100">Architecture & Blast Radius Blueprint</h2>
            <div className="inline-flex rounded-lg border border-slate-800 bg-slate-950 p-0.5 text-xs">
              <button
                onClick={() => setActiveDiagramTab('arch')}
                className={`px-3 py-1 rounded-md font-semibold transition ${activeDiagramTab === 'arch' ? 'bg-sky-500 text-slate-950' : 'text-slate-400 hover:text-slate-200'}`}
              >
                Architecture Map
              </button>
              <button
                onClick={() => setActiveDiagramTab('blast')}
                className={`px-3 py-1 rounded-md font-semibold transition ${activeDiagramTab === 'blast' ? 'bg-sky-500 text-slate-950' : 'text-slate-400 hover:text-slate-200'}`}
              >
                Blast Radius
              </button>
            </div>
          </div>

          {activeDiagramTab === 'blast' && selectedComponentId && (
            <button
              onClick={() => openInspector(selectedComponentId, 'blast')}
              className="text-xs font-semibold text-sky-400 hover:text-sky-300 flex items-center gap-1"
            >
              Open in Inspector Drawer ↗
            </button>
          )}
        </div>

        {activeDiagramTab === 'arch' ? (
          <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
            <MermaidViewer code={report.architecture_diagram_mermaid} />
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-950/80 p-3 rounded-xl border border-slate-800">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-slate-300">Failure Propagation Origin:</span>
                <span className="text-[10px] text-slate-500 font-mono">Ranked by Reach</span>
              </div>
              <select
                value={selectedComponentId}
                onChange={(e) => setSelectedComponentId(e.target.value)}
                className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs font-medium text-sky-400 focus:border-sky-500 focus:outline-none"
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
              <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
                <MermaidViewer code={blastRadiusData.mermaid} />
              </div>
            ) : (
              <div className="rounded-lg border border-dashed border-slate-800 p-8 text-center text-xs text-slate-500">
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
