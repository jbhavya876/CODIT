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

  const { data: report, loading, error, refetch } = useFetch(() => api.getReport(), [])
  const { data: blastRadiusData } = useFetch(
    () => (selectedComponentId ? api.getBlastRadiusDiagram(selectedComponentId) : Promise.resolve(null)),
    [selectedComponentId]
  )

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

  if (loading && !report) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] text-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-sky-500 border-t-transparent mb-4" />
        <p className="text-sm text-slate-400">Loading audit report & static analysis data...</p>
      </div>
    )
  }

  if (error && !report) {
    return (
      <div className="rounded-xl border border-rose-500/40 bg-rose-950/20 p-8 text-center max-w-lg mx-auto">
        <div className="text-rose-400 font-semibold mb-2">Audit Report Unavailable</div>
        <p className="text-xs text-slate-400 mb-6">{error.message || 'No audit report found.'}</p>
        <button
          onClick={() => handleRunAnalysis(goal)}
          disabled={analyzing}
          className="rounded-lg bg-sky-500 px-5 py-2.5 text-xs font-semibold text-slate-950 hover:bg-sky-400"
        >
          {analyzing ? 'Analyzing Codebase...' : 'Execute Full Audit Scan Now'}
        </button>
      </div>
    )
  }

  const scorecard = report?.scorecard || {}
  const roadmap = report?.roadmap || { phases: [] }
  const findings = report?.findings || []

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
            Target: <code className="text-slate-200">{report.target_name}</code> · Intake Tier: <span className="text-slate-300">{report.access_tier}</span> · Generated: {new Date(report.created_at * 1000).toLocaleString()}
          </p>
        </div>

        {/* Controls & Export Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-lg border border-slate-700 bg-slate-900 p-1">
            <button
              onClick={() => { setGoal('mvp'); handleRunAnalysis('mvp'); }}
              disabled={analyzing}
              className={`px-3 py-1 text-xs font-medium rounded-md transition ${goal === 'mvp' ? 'bg-sky-500 text-slate-950' : 'text-slate-400 hover:text-slate-200'}`}
            >
              Target: MVP
            </button>
            <button
              onClick={() => { setGoal('production'); handleRunAnalysis('production'); }}
              disabled={analyzing}
              className={`px-3 py-1 text-xs font-medium rounded-md transition ${goal === 'production' ? 'bg-sky-500 text-slate-950' : 'text-slate-400 hover:text-slate-200'}`}
            >
              Target: Production
            </button>
          </div>

          <a
            href={api.getMarkdownReportUrl()}
            target="_blank"
            rel="noreferrer"
            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-800 transition"
          >
            📥 Markdown
          </a>

          <a
            href={api.getHtmlReportUrl()}
            target="_blank"
            rel="noreferrer"
            className="rounded-lg bg-sky-500 px-3.5 py-1.5 text-xs font-semibold text-slate-950 hover:bg-sky-400 transition"
          >
            🖨️ Print / PDF
          </a>
        </div>
      </div>

      {/* Critical Blocker Alert */}
      {scorecard.has_critical_blocker && (
        <div className="rounded-xl border border-rose-500/50 bg-rose-950/30 p-4 text-xs text-rose-300 flex items-start gap-3">
          <span className="text-lg leading-none">⚠️</span>
          <div>
            <div className="font-bold text-sm text-rose-200">Hard Constraint Alert: Security Score Capped at 25/100</div>
            <p className="mt-0.5">
              An unaddressed critical vulnerability or leaked credential was caught in the codebase. Per Section 1 & 6a rules,
              the security score is locked at a fixed low value regardless of all other metrics until this blocker is resolved.
            </p>
          </div>
        </div>
      )}

      {/* Scorecard Overview Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-4 flex flex-col justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Overall Readiness</span>
          <div className="mt-2 flex items-baseline gap-1">
            <span className="text-3xl font-bold tracking-tight text-slate-100">{scorecard.overall_score}</span>
            <span className="text-xs text-slate-500">/100</span>
          </div>
          <div className="mt-2 text-[10px] text-slate-500">Weighted rollup across 5 dimensions</div>
        </div>

        {Object.entries(scorecard.dimensions || {}).map(([dim, s]) => {
          const isSecCapped = dim === 'security' && scorecard.has_critical_blocker
          return (
            <div key={dim} className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-4 flex flex-col justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">{dim}</span>
              <div className="mt-2 flex items-baseline gap-1">
                <span className={`text-2xl font-bold tracking-tight ${isSecCapped ? 'text-rose-400' : 'text-slate-200'}`}>
                  {s.score}
                </span>
                <span className="text-xs text-slate-500">/100</span>
              </div>
              <div className="mt-2 flex items-center justify-between text-[10px] text-slate-500">
                <span>{s.findings_count} findings</span>
                {s.critical_count > 0 && <span className="text-rose-400 font-bold">{s.critical_count} crit</span>}
              </div>
            </div>
          )
        })}
      </div>

      {/* Roadmap Section */}
      <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-6 space-y-6">
        <div>
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-slate-100">Prioritized Engineering Roadmap</h2>
            <span className="text-xs font-mono text-sky-400">Goal: {roadmap.goal?.toUpperCase()}</span>
          </div>
          <p className="mt-1 text-xs text-slate-400">{roadmap.summary_narrative}</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {(roadmap.phases || []).map((phase, idx) => (
            <div key={idx} className="rounded-lg border border-slate-800 bg-slate-950/60 p-4 flex flex-col justify-between space-y-3">
              <div>
                <div className="flex items-center justify-between text-xs font-bold text-slate-200">
                  <span>{phase.phase_name}</span>
                  <span className="text-[10px] text-slate-500 font-normal">{phase.target_timeline}</span>
                </div>
                <p className="mt-1 text-[11px] text-slate-400">{phase.objective}</p>
              </div>

              <div className="space-y-2 pt-2 border-t border-slate-850">
                {phase.action_items?.length === 0 ? (
                  <div className="text-[11px] text-slate-500 italic">No action items in this phase.</div>
                ) : (
                  phase.action_items?.map((item, i) => (
                    <div key={i} className="rounded border border-slate-800/80 bg-slate-900/80 p-2.5 text-xs space-y-1">
                      <div className="flex items-center justify-between">
                        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                          item.priority.includes('P0') ? 'bg-rose-950 text-rose-300 border border-rose-500/30' : 'bg-amber-950 text-amber-300 border border-amber-500/30'
                        }`}>
                          {item.priority}
                        </span>
                        <span className="text-[10px] font-mono text-slate-400 truncate max-w-[120px]">{item.evidence_file}</span>
                      </div>
                      <div className="font-medium text-slate-200 text-[11px]">{item.title}</div>
                      <div className="text-[10px] text-slate-400 line-clamp-2">{item.action}</div>
                    </div>
                  ))
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Diagrams Section */}
      <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-slate-100">Architecture & Dependency Traversal</h2>
            <p className="text-xs text-slate-400">Generated directly from the real assembled graph database.</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveDiagramTab('arch')}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg transition ${
                activeDiagramTab === 'arch' ? 'bg-sky-500 text-slate-950' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              Architecture Overview
            </button>
            <button
              onClick={() => setActiveDiagramTab('blast')}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg transition ${
                activeDiagramTab === 'blast' ? 'bg-sky-500 text-slate-950' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              Blast-Radius Traversal
            </button>
          </div>
        </div>

        {activeDiagramTab === 'arch' && (
          <MermaidViewer chart={report.architecture_diagram_mermaid} />
        )}

        {activeDiagramTab === 'blast' && (
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <label className="text-xs text-slate-400">Select Root Component to Inspect:</label>
              <select
                value={selectedComponentId}
                onChange={(e) => setSelectedComponentId(e.target.value)}
                className="rounded border border-slate-700 bg-slate-950 px-3 py-1 text-xs text-slate-200"
              >
                <option value="">-- Choose Component --</option>
                {(report.criticality_leaderboard || []).map((row) => (
                  <option key={row.component.id} value={row.component.id}>
                    {row.component.name || row.component.id} ({row.reach} reachable)
                  </option>
                ))}
              </select>
            </div>

            {selectedComponentId && blastRadiusData?.mermaid ? (
              <MermaidViewer chart={blastRadiusData.mermaid} />
            ) : (
              <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-8 text-center text-xs text-slate-500">
                Select any component above to trace its multi-hop blast radius impact tree.
              </div>
            )}
          </div>
        )}
      </div>

      {/* Evidenced Findings Catalog */}
      <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-slate-100">
              Evidenced Findings Catalog ({filteredFindings.length})
            </h2>
            <p className="text-xs text-slate-400">Every finding references a specific file and line number (Constraint 9).</p>
          </div>

          <input
            type="text"
            placeholder="Search findings or files..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-64 rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500"
          />
        </div>

        {/* Filter Pills */}
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <span className="text-[11px] text-slate-500">Severity:</span>
          {['all', 'critical', 'high', 'medium', 'low'].map((sev) => (
            <button
              key={sev}
              onClick={() => setSevFilter(sev)}
              className={`px-2.5 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider transition ${
                sevFilter === sev ? 'bg-sky-500 text-slate-950' : 'bg-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              {sev}
            </button>
          ))}

          <span className="ml-4 text-[11px] text-slate-500">Dimension:</span>
          {['all', 'security', 'tests', 'scalability', 'duplication'].map((dim) => (
            <button
              key={dim}
              onClick={() => setDimFilter(dim)}
              className={`px-2.5 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider transition ${
                dimFilter === dim ? 'bg-sky-500 text-slate-950' : 'bg-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              {dim}
            </button>
          ))}
        </div>

        {/* Findings Table */}
        <div className="overflow-x-auto rounded-lg border border-slate-800">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-950/60 text-[11px] text-slate-400 uppercase tracking-wider">
                <th className="p-3">Severity</th>
                <th className="p-3">Dimension</th>
                <th className="p-3">Evidence Citation</th>
                <th className="p-3">Description</th>
                <th className="p-3">Remediation</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-850">
              {filteredFindings.map((f, i) => {
                const sevBadge = {
                  critical: 'bg-rose-950 text-rose-300 border-rose-500/40',
                  high: 'bg-orange-950 text-orange-300 border-orange-500/40',
                  medium: 'bg-amber-950 text-amber-300 border-amber-500/40',
                  low: 'bg-slate-800 text-slate-300 border-slate-700',
                }[f.severity.toLowerCase()] || 'bg-slate-800 text-slate-300'

                return (
                  <tr key={i} className="hover:bg-slate-800/30 transition">
                    <td className="p-3 whitespace-nowrap">
                      <span className={`inline-block border px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${sevBadge}`}>
                        {f.severity}
                      </span>
                    </td>
                    <td className="p-3 font-medium text-slate-300 whitespace-nowrap">{f.dimension}</td>
                    <td className="p-3 whitespace-nowrap font-mono text-[11px] text-sky-400">
                      <code>{f.evidence_file}{f.evidence_line ? `:${f.evidence_line}` : ''}</code>
                    </td>
                    <td className="p-3 text-slate-300 max-w-md">{f.description}</td>
                    <td className="p-3 text-slate-400 max-w-xs">{f.remediation || '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
