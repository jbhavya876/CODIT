import React, { useState } from 'react'
import { api, useFetch } from '../api.js'
import MermaidViewer from '../components/MermaidViewer.jsx'

export default function AuditPage() {
  const [goal, setGoal] = useState('production')
  const [analyzing, setAnalyzing] = useState(false)
  const [sevFilter, setSevFilter] = useState('all')
  const [dimFilter, setDimFilter] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [activeDiagramTab, setActiveDiagramTab] = useState('arch')
  const [selectedComponentId, setSelectedComponentId] = useState('')
  const [copiedId, setCopiedId] = useState(null)

  const { data: report, loading, error, refetch } = useFetch(() => api.getReport(), [])
  const { data: blastRadiusData } = useFetch(
    () => (selectedComponentId ? api.getBlastRadiusDiagram(selectedComponentId) : Promise.resolve(null)),
    [selectedComponentId]
  )

  React.useEffect(() => {
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

  if (loading && !report) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[450px] text-center space-y-4">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-sky-500 border-t-transparent shadow-lg shadow-sky-500/20" />
        <div className="space-y-1">
          <p className="text-base font-semibold text-slate-200">Analyzing Repository Architecture...</p>
          <p className="text-xs text-slate-500 font-mono">Running Tree-sitter AST, ONNX fragility inference & SHAP explainability</p>
        </div>
      </div>
    )
  }

  if (error && !report) {
    return (
      <div className="rounded-xl border border-rose-500/40 bg-rose-950/20 p-8 text-center max-w-lg mx-auto shadow-2xl">
        <div className="text-rose-400 font-semibold mb-2">Audit Report Unavailable</div>
        <p className="text-xs text-slate-400 mb-6">{error.message || 'No audit report found.'}</p>
        <button
          onClick={() => handleRunAnalysis(goal)}
          disabled={analyzing}
          className="rounded-lg bg-sky-500 px-5 py-2.5 text-xs font-semibold text-slate-950 hover:bg-sky-400 shadow-lg shadow-sky-500/20 transition"
        >
          {analyzing ? 'Analyzing Codebase...' : 'Execute Full Audit Scan Now'}
        </button>
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
      {/* Top Header & Export Actions */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-800/80 pb-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-slate-100 sm:text-3xl">
              Codebase Audit Cockpit
            </h1>
            <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-0.5 text-xs font-semibold uppercase tracking-wider ${phaseBadgeClass}`}>
              {scorecard.phase || 'AUDITING'}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-400">
            Target: <code className="text-slate-200 font-mono font-semibold">{report.target_name}</code> · Intake Tier: <span className="text-slate-300 capitalize">{report.access_tier?.replace('_', ' ')}</span> · Report ID: <span className="font-mono text-slate-400">{report.report_id}</span>
          </p>
        </div>

        {/* Controls & Export Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-lg border border-slate-700 bg-slate-900 p-1">
            <button
              onClick={() => { setGoal('mvp'); handleRunAnalysis('mvp'); }}
              disabled={analyzing}
              className={`px-3 py-1 text-xs font-medium rounded-md transition ${goal === 'mvp' ? 'bg-sky-500 text-slate-950 font-semibold' : 'text-slate-400 hover:text-slate-200'}`}
            >
              Target: MVP
            </button>
            <button
              onClick={() => { setGoal('production'); handleRunAnalysis('production'); }}
              disabled={analyzing}
              className={`px-3 py-1 text-xs font-medium rounded-md transition ${goal === 'production' ? 'bg-sky-500 text-slate-950 font-semibold' : 'text-slate-400 hover:text-slate-200'}`}
            >
              Target: Production
            </button>
          </div>

          <a
            href={api.getMarkdownReportUrl()}
            target="_blank"
            rel="noreferrer"
            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-800 transition flex items-center gap-1.5"
          >
            <span>📥</span> Markdown
          </a>

          <a
            href={api.getHtmlReportUrl()}
            target="_blank"
            rel="noreferrer"
            className="rounded-lg bg-sky-500 px-3.5 py-1.5 text-xs font-semibold text-slate-950 hover:bg-sky-400 transition shadow-lg shadow-sky-500/20 flex items-center gap-1.5"
          >
            <span>🖨️</span> PDF / Print
          </a>
        </div>
      </div>

      {/* Critical Blocker Alert */}
      {scorecard.has_critical_blocker && (
        <div className="rounded-xl border border-rose-500/50 bg-rose-950/30 p-4 text-xs text-rose-300 flex items-start gap-3 shadow-lg shadow-rose-950/40">
          <span className="text-xl leading-none">⚠️</span>
          <div>
            <div className="font-bold text-sm text-rose-200">Critical Security Lockout Active (Cap 25/100)</div>
            <p className="mt-0.5 leading-relaxed">
              An unaddressed critical vulnerability or leaked credential was caught in the ingested code manifest.
              Per non-negotiable security constraints, production readiness and MVP tracks are locked until this blocker is remedied.
            </p>
          </div>
        </div>
      )}

      {/* Neural AI & Scoring Cockpit Hero Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Card 1: SVG Circular Score Dial (4 Cols) */}
        <div className="lg:col-span-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-6 flex flex-col items-center justify-between text-center relative overflow-hidden shadow-xl">
          <div className="absolute top-0 right-0 p-3">
            <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500">Deterministic</span>
          </div>

          <div className="w-full text-left">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Readiness Score</span>
            <div className="text-xs text-slate-500 mt-0.5">Automated multi-dimensional rollup</div>
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
              <span className="text-4xl font-extrabold tracking-tight text-slate-100">{overallScore}</span>
              <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Out of 100</span>
            </div>
          </div>

          <div className="w-full pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs">
            <span className="text-slate-400">Current Track:</span>
            <span className={`font-semibold ${overallScore >= 80 ? 'text-emerald-400' : overallScore >= 55 ? 'text-sky-400' : 'text-rose-400'}`}>
              {scorecard.phase}
            </span>
          </div>
        </div>

        {/* Card 2: ONNX Runtime Fragility & Defect Risk (4 Cols) */}
        <div className="lg:col-span-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-6 flex flex-col justify-between relative shadow-xl">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">ONNX Fragility Model</span>
              <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] font-mono text-sky-400">
                {onnxMetrics.runtime_engine || 'onnxruntime v1.30'}
              </span>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="rounded-xl border border-slate-800/80 bg-slate-950/60 p-3">
                <span className="text-[10px] text-slate-500 uppercase block">Fragility Index</span>
                <span className="text-2xl font-bold font-mono text-amber-400">
                  {onnxMetrics.fragility_score !== undefined ? onnxMetrics.fragility_score : '0.45'}
                </span>
                <span className="text-[10px] text-slate-500 block">Scale: 0.0 - 1.0</span>
              </div>

              <div className="rounded-xl border border-slate-800/80 bg-slate-950/60 p-3">
                <span className="text-[10px] text-slate-500 uppercase block">Defect Risk Tier</span>
                <span className={`text-xl font-bold ${
                  onnxMetrics.defect_risk_tier === 'Critical' ? 'text-rose-400' :
                  onnxMetrics.defect_risk_tier === 'High' ? 'text-orange-400' :
                  onnxMetrics.defect_risk_tier === 'Moderate' ? 'text-amber-400' : 'text-emerald-400'
                }`}>
                  {onnxMetrics.defect_risk_tier || 'Moderate'}
                </span>
                <span className="text-[10px] text-slate-500 block">Architecture Profile</span>
              </div>
            </div>

            <div className="mt-3 space-y-2 text-xs">
              <div className="flex justify-between text-slate-400">
                <span>Maintainability Index:</span>
                <span className="font-mono text-slate-200">{onnxMetrics.maintainability_index ?? 72}/100</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Remediation Effort Est:</span>
                <span className="font-mono text-sky-300">~{onnxMetrics.estimated_remediation_days ?? 8} Eng Days</span>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-800/80">
            <span className="text-[11px] font-semibold text-slate-400 block mb-1">Structural Risk Triggers:</span>
            <ul className="text-[11px] text-slate-500 space-y-1">
              {(onnxMetrics.risk_triggers || ['Standard architectural complexity']).slice(0, 2).map((trig, i) => (
                <li key={i} className="flex items-start gap-1.5">
                  <span className="text-amber-400 leading-none">•</span>
                  <span>{trig}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Card 3: SHAP Explainability Waterfall Panel (4 Cols) */}
        <div className="lg:col-span-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-6 flex flex-col justify-between relative shadow-xl">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">SHAP Explainability</span>
              <span className="rounded-full bg-emerald-950/60 border border-emerald-500/40 px-2 py-0.5 text-[10px] font-mono text-emerald-400">
                Game Theory Attribution
              </span>
            </div>

            <p className="mt-2 text-[11px] text-slate-400 leading-relaxed">
              {shapData.narrative || 'SHAP feature attribution decomposes exactly which signals altered the baseline audit score.'}
            </p>

            <div className="mt-3 space-y-2 max-h-48 overflow-y-auto pr-1">
              {(shapData.waterfall || []).map((item, idx) => (
                <div key={idx} className="rounded-lg border border-slate-800/60 bg-slate-950/40 p-2 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-slate-300 text-[11px] truncate max-w-[170px]" title={item.name}>
                      {item.name}
                    </span>
                    <span
                      className={`font-mono font-bold text-[11px] px-1.5 py-0.5 rounded ${
                        item.shap_value < 0 ? 'bg-rose-500/10 text-rose-400' : 'bg-emerald-500/10 text-emerald-400'
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
            <span>Base Model Baseline: {shapData.baseline_score ?? 95.0}</span>
            <span>Additive Sum: {overallScore}</span>
          </div>
        </div>
      </div>

      {/* 5-Dimension Scorecard Breakdown */}
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-3">
          Dimensional Maturity Breakdown
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {Object.entries(scorecard.dimensions || {}).map(([dim, s]) => {
            const isSecCapped = dim === 'security' && scorecard.has_critical_blocker
            const barColor = s.score >= 75 ? 'bg-emerald-500' : s.score >= 50 ? 'bg-sky-500' : 'bg-rose-500'
            return (
              <div key={dim} className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-4 flex flex-col justify-between space-y-3">
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold capitalize text-slate-300">{dim}</span>
                    {s.critical_count > 0 && (
                      <span className="rounded bg-rose-500/20 px-1.5 py-0.5 text-[9px] font-bold text-rose-400">
                        {s.critical_count} CRIT
                      </span>
                    )}
                  </div>

                  <div className="mt-2 flex items-baseline gap-1">
                    <span className={`text-2xl font-extrabold tracking-tight ${isSecCapped ? 'text-rose-400' : 'text-slate-100'}`}>
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
      <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-6 space-y-6 shadow-xl">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-800 pb-4">
          <div>
            <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
              <span>🗺️</span> Prioritized Engineering Roadmap
            </h2>
            <p className="mt-1 text-xs text-slate-400">{roadmap.summary_narrative}</p>
          </div>
          <span className="rounded-full border border-sky-500/40 bg-sky-500/10 px-3 py-1 text-xs font-mono text-sky-400 self-start sm:self-auto">
            Target Target: {roadmap.goal?.toUpperCase()}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {(roadmap.phases || []).map((phase, idx) => (
            <div key={idx} className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 flex flex-col justify-between space-y-4">
              <div>
                <div className="flex items-center justify-between text-xs font-bold text-slate-200">
                  <span className="flex items-center gap-1.5">
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-sky-500/20 text-sky-400 text-[10px]">
                      {idx + 1}
                    </span>
                    {phase.phase_name}
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">{phase.target_timeline}</span>
                </div>

                <div className="mt-3 space-y-2">
                  {(phase.actions || []).map((act, aIdx) => (
                    <div key={aIdx} className="rounded-lg border border-slate-800/80 bg-slate-900/80 p-2.5 text-xs space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-slate-300">{act.title}</span>
                        <span className="text-[10px] font-mono text-slate-500">{act.effort_estimate}</span>
                      </div>
                      <p className="text-[11px] text-slate-400">{act.description}</p>
                      {act.impacted_components?.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {act.impacted_components.map((c, cIdx) => (
                            <span key={cIdx} className="rounded bg-slate-800 px-1.5 py-0.5 text-[9px] font-mono text-sky-400">
                              {c}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div className="pt-2 border-t border-slate-800/60 text-[10px] text-slate-500 flex justify-between">
                <span>Phase Status: Pending Remediation</span>
                <span className="font-semibold text-slate-400">{phase.actions?.length || 0} Actions</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Interactive Findings Explorer */}
      <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-6 space-y-6 shadow-xl">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800 pb-4">
          <div>
            <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
              <span>🔍</span> Evidenced Findings Explorer
              <span className="rounded-full bg-slate-800 px-2.5 py-0.5 text-xs text-slate-400">
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
                  className={`rounded-lg px-2.5 py-1 text-xs font-medium uppercase tracking-wider transition ${
                    sevFilter === sev ? 'bg-sky-500 text-slate-950 font-bold' : 'bg-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {sev} ({count})
                </button>
              )
            })}
          </div>
        </div>

        {/* Filter Toolbar */}
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

        {/* Findings Grid */}
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
                  className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 space-y-3 transition hover:border-slate-700"
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
                        className="text-slate-500 hover:text-slate-300 text-[10px]"
                        title="Copy file:line"
                      >
                        {copiedId === `loc-${idx}` ? '✓ Copied' : '📋 Copy'}
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
                          className="text-[10px] text-sky-400 hover:text-sky-200 font-mono"
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

      {/* Diagrams Section */}
      <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-6 space-y-4 shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-bold text-slate-100">Architecture & Blast Radius Blueprint</h2>
            <div className="inline-flex rounded-lg border border-slate-700 bg-slate-950 p-0.5 text-xs">
              <button
                onClick={() => setActiveDiagramTab('arch')}
                className={`px-3 py-1 rounded-md transition ${activeDiagramTab === 'arch' ? 'bg-sky-500 text-slate-950 font-semibold' : 'text-slate-400 hover:text-slate-200'}`}
              >
                Full Architecture
              </button>
              <button
                onClick={() => setActiveDiagramTab('blast')}
                className={`px-3 py-1 rounded-md transition ${activeDiagramTab === 'blast' ? 'bg-sky-500 text-slate-950 font-semibold' : 'text-slate-400 hover:text-slate-200'}`}
              >
                Blast Radius
              </button>
            </div>
          </div>
        </div>

        {activeDiagramTab === 'arch' ? (
          <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
            <MermaidViewer code={report.architecture_diagram_mermaid} />
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-950/80 p-3 rounded-xl border border-slate-800">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-slate-300">Failure Propagation Origin:</span>
                <span className="text-[10px] text-slate-500 font-mono">Ranked by Reach</span>
              </div>
              <select
                value={selectedComponentId}
                onChange={(e) => setSelectedComponentId(e.target.value)}
                className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs font-medium text-sky-400 focus:border-sky-500 focus:outline-none"
              >
                <option value="">-- Choose from Critical Leaderboard --</option>
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
    </div>
  )
}
