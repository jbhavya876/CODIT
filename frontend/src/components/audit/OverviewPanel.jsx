import React, { useState } from 'react'
import { CritBadge, ConfidenceGauge, Dot } from '../ui.jsx'
import OdometerNumeral from '../ui/OdometerNumeral.jsx'
import VerdictSeal from '../ui/VerdictSeal.jsx'
import SHAPLedger from '../ui/SHAPLedger.jsx'
import HeroConstellation from '../ui/HeroConstellation.jsx'
import MermaidViewer from '../MermaidViewer.jsx'

const ALL_DIMS = [
  'security',
  'tests',
  'agent_integrity',
  'scalability',
  'licenses',
  'duplication',
  'maintainability',
]

export default function OverviewPanel({
  report,
  isDossier,
  showConstellation,
  blastRadiusData,
  selectedComponentId,
  setSelectedComponentId,
  openInspector,
}) {
  const [sevFilter, setSevFilter] = useState('all')
  const [dimFilter, setDimFilter] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [activeDiagramTab, setActiveDiagramTab] = useState('arch')
  const [copiedId, setCopiedId] = useState(null)
  const [expandedFinding, setExpandedFinding] = useState(null)

  const scorecard = report.scorecard || {}
  const findings = report.findings || []
  const roadmap = report.roadmap || {}
  const overallScore = scorecard.overall ?? scorecard.overall_score ?? 0
  const mlInsights = report.ml_insights || {}
  const onnxMetrics = mlInsights.onnx_metrics || {}
  const shapData = mlInsights.shap_explainability || {}
  const effort = report.effort || null
  const riskTier = onnxMetrics.defect_risk_tier || (overallScore >= 80 ? 'LOW' : overallScore >= 55 ? 'MODERATE' : 'CRITICAL')

  const copyText = (text, id) => {
    navigator.clipboard?.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 1800)
  }

  const filteredFindings = findings.filter((f) => {
    if (sevFilter !== 'all') {
      const target = sevFilter.toLowerCase()
      const fSev = (f.severity || '').toLowerCase()
      if (target === 'critical' ? !['critical', 'crit'].includes(fSev) : target === 'medium' ? !['medium', 'med'].includes(fSev) : fSev !== target) {
        return false
      }
    }
    if (dimFilter !== 'all' && (f.dimension || '').toLowerCase() !== dimFilter.toLowerCase()) return false
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      if (
        !(f.description || '').toLowerCase().includes(q) &&
        !(f.evidence_file || '').toLowerCase().includes(q) &&
        !(f.rule_id || '').toLowerCase().includes(q) &&
        !(f.fingerprint || '').toLowerCase().includes(q)
      ) {
        return false
      }
    }
    return true
  })

  return (
    <div className="space-y-6">
      {showConstellation && (
        <div className="relative">
          <HeroConstellation height={280} />
        </div>
      )}

      {/* Critical Security / Blockers Banner */}
      {(scorecard.has_critical_blocker || (scorecard.blockers || []).length > 0) && (
        <div className="rounded-xl border border-[#FF4A2B] bg-[#2A0E0B] p-4 text-xs text-[#FF4A2B] flex items-start gap-3">
          <span className="font-mono font-black text-[#FF4A2B] text-base leading-none" aria-hidden="true">◆</span>
          <div>
            <div className="font-mono font-bold text-xs uppercase tracking-wider text-rose-200">
              Release Blockers Active {scorecard.has_critical_blocker ? '(Security Score Capped at 25/100)' : ''}
            </div>
            <p className="mt-1 leading-relaxed text-rose-200/90 font-sans">
              Active blockers: {(scorecard.blockers || ['critical_security']).join(', ')}. Production-track stays locked until resolved.
            </p>
          </div>
        </div>
      )}

      {/* Hero Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className={`lg:col-span-4 rounded-xl border p-5 flex flex-col items-center justify-between text-center relative ${isDossier ? 'border-[#D8D2C5] bg-[#F7F4EE]' : 'border-[#2A2E35] bg-[#15171B]'}`}>
          <div className="w-full flex justify-between items-start">
            <div className="text-left">
              <span className={`text-xs font-bold uppercase tracking-wider font-mono ${isDossier ? 'text-[#575A65]' : 'text-slate-400'}`}>
                The Verdict
              </span>
              <div className={`text-[11px] mt-0.5 font-sans ${isDossier ? 'text-[#575A65]' : 'text-slate-400'}`}>
                Rubric {report.rubric_version || scorecard.rubric_version || '2.0.0'}
              </div>
            </div>
            <span className="text-[10px] font-mono uppercase tracking-widest font-bold text-slate-400">
              DETERMINISTIC
            </span>
          </div>

          <div className="my-4 flex flex-col items-center">
            <div className="flex items-baseline gap-1">
              <span className={`text-6xl font-black font-mono tracking-tight tabular-nums ${isDossier ? 'text-[#101114]' : 'text-slate-100'}`}>
                <OdometerNumeral value={overallScore} />
              </span>
              <span className={`text-lg font-mono ${isDossier ? 'text-[#575A65]' : 'text-slate-400'}`}>/ 100</span>
            </div>
            <div className="mt-3">
              <VerdictSeal tier={riskTier} isCapped={scorecard.has_critical_blocker} capReason="Hard gate blocker active" />
            </div>
          </div>

          <div className={`w-full pt-3 border-t flex items-center justify-between text-xs font-mono ${isDossier ? 'border-[#D8D2C5] text-[#575A65]' : 'border-[#2A2E35] text-slate-400'}`}>
            <span>PHASE:</span>
            <span className="font-bold text-laser-lime">{scorecard.phase}</span>
          </div>
        </div>

        {/* Model Estimate (calibrated heuristic) — explicitly labeled & separate from Effort Range */}
        <div className={`lg:col-span-4 rounded-xl border p-5 flex flex-col justify-between ${isDossier ? 'border-[#D8D2C5] bg-[#F7F4EE]' : 'border-[#2A2E35] bg-[#15171B]'}`}>
          <div>
            <div className="flex items-center justify-between">
              <span className={`text-xs font-bold uppercase tracking-wider font-mono ${isDossier ? 'text-[#101114]' : 'text-slate-300'}`}>
                ONNX FRAGILITY REGRESSOR
              </span>
              <span className="rounded border border-[#2A2E35] bg-[#0A0B0D] px-2 py-0.5 text-[10px] font-mono text-slate-300">
                model estimate (calibrated heuristic)
              </span>
            </div>

            <div className="mt-3.5 grid grid-cols-2 gap-2.5">
              <div className={`rounded-lg border p-3 ${isDossier ? 'border-[#D8D2C5] bg-[#EFEAE0]' : 'border-[#2A2E35] bg-[#0A0B0D]'}`}>
                <span className="text-[10px] uppercase font-mono block text-slate-400">Fragility Index</span>
                <span className="text-xl font-bold font-mono text-[#FFB020] tabular-nums">
                  {onnxMetrics.fragility_score ?? '0.45'}
                </span>
              </div>
              <div className={`rounded-lg border p-3 ${isDossier ? 'border-[#D8D2C5] bg-[#EFEAE0]' : 'border-[#2A2E35] bg-[#0A0B0D]'}`}>
                <span className="text-[10px] uppercase font-mono block text-slate-400">Defect Risk Tier</span>
                <span className="text-base font-bold font-mono uppercase text-slate-100">
                  {onnxMetrics.defect_risk_tier || 'Moderate'}
                </span>
              </div>
            </div>

            {effort && (
              <div className={`mt-3 rounded-lg border p-2.5 text-xs font-mono ${isDossier ? 'border-[#D8D2C5] bg-[#EFEAE0]' : 'border-[#2A2E35] bg-[#0A0B0D]'}`}>
                <div className="text-[10px] uppercase text-slate-400">Rule Effort Range (Assumptions v{effort.effort_model_version})</div>
                <div className="font-bold text-laser-lime tabular-nums mt-0.5">
                  {effort.person_days?.min}..{effort.person_days?.max} person-days (likely {effort.person_days?.likely})
                </div>
              </div>
            )}
          </div>
          <div className="mt-3 pt-2 border-t border-[#2A2E35] text-[10px] font-mono text-slate-400">
            ONNX heuristic never alters deterministic rubric score or phase.
          </div>
        </div>

        {/* SHAP Explainability */}
        <div className={`lg:col-span-4 rounded-xl border p-5 flex flex-col justify-between ${isDossier ? 'border-[#D8D2C5] bg-[#F7F4EE]' : 'border-[#2A2E35] bg-[#15171B]'}`}>
          <div>
            <div className="flex items-center justify-between">
              <span className={`text-xs font-bold uppercase tracking-wider font-mono ${isDossier ? 'text-[#101114]' : 'text-slate-300'}`}>
                SHAP EXPLAINABILITY
              </span>
              <span className="rounded border border-emerald-900/60 bg-emerald-950/40 px-2 py-0.5 text-[10px] font-mono text-[#5DE6A8]">
                SURROGATE
              </span>
            </div>
            <div className="mt-3">
              <SHAPLedger shapData={shapData} finalScore={overallScore} isDossier={isDossier} />
            </div>
          </div>
        </div>
      </div>

      {/* 7-Dimension Breakdown */}
      <div>
        <div className="flex items-center justify-between mb-2.5">
          <h2 className="text-xs font-bold uppercase tracking-wider font-mono text-slate-400">
            Dimensional Maturity Breakdown (Rubric {report.rubric_version || '2.0.0'})
          </h2>
          <span className="text-[10px] text-slate-400 font-mono">Click dimension to filter findings</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2.5">
          {ALL_DIMS.map((dim) => {
            const s = (scorecard.dimensions || {})[dim]
            if (!s) return null
            const isNa = Boolean(s.not_applicable)
            const assessed = s.assessed !== false && s.score !== null && s.score !== undefined
            const scoreVal = assessed ? s.score : null
            const isSelected = dimFilter === dim
            return (
              <button
                key={dim}
                type="button"
                onClick={() => setDimFilter(isSelected ? 'all' : dim)}
                className={`text-left rounded-lg border p-3 flex flex-col justify-between space-y-2 transition ${
                  isSelected ? 'border-laser-lime bg-[#1E2228]' : 'border-[#2A2E35] bg-[#15171B] hover:border-slate-500'
                }`}
              >
                <span className="text-[11px] font-bold uppercase tracking-wider font-mono text-slate-200 truncate w-full">
                  {dim.replace('_', ' ')}
                </span>
                <div className="font-mono">
                  {assessed ? (
                    <span className="text-xl font-black text-slate-100 tabular-nums">{scoreVal}<span className="text-[10px] text-slate-400">/100</span></span>
                  ) : (
                    <span className="text-[11px] font-bold text-[#FFB020]">{isNa ? 'N/A' : 'NOT ASSESSED'}</span>
                  )}
                </div>
                <div className="text-[10px] font-mono text-slate-400">{s.findings_count ?? 0} findings</div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Evidenced Findings Ledger */}
      <div className={`rounded-xl border p-5 space-y-4 ${isDossier ? 'border-[#D8D2C5] bg-[#F7F4EE]' : 'border-[#2A2E35] bg-[#15171B]'}`}>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-[#2A2E35] pb-3">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wider font-mono text-slate-100">
              Evidenced Findings Catalog ({filteredFindings.length} of {findings.length})
            </h2>
          </div>
          <div className="flex flex-wrap items-center gap-1 font-mono text-xs">
            {['all', 'critical', 'high', 'medium', 'low'].map((id) => (
              <button
                key={id}
                type="button"
                onClick={() => setSevFilter(id)}
                className={`rounded px-2.5 py-1 text-[11px] font-bold uppercase ${
                  sevFilter === id ? 'bg-laser-lime text-black' : 'bg-[#0A0B0D] border border-[#2A2E35] text-slate-400'
                }`}
              >
                {id}
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-2 font-mono text-xs">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search rule ID, file, fingerprint, or description..."
            className="w-full rounded border border-[#2A2E35] bg-[#0A0B0D] px-3.5 py-2 text-xs text-slate-100 placeholder-slate-500 focus:border-laser-lime focus:outline-none"
          />
          <select
            aria-label="Filter findings by dimension"
            value={dimFilter}
            onChange={(e) => setDimFilter(e.target.value)}
            className="rounded border border-[#2A2E35] bg-[#0A0B0D] px-3 py-2 text-xs text-slate-200 uppercase focus:border-laser-lime focus:outline-none"
          >
            <option value="all">ALL DIMENSIONS</option>
            {ALL_DIMS.map((d) => (
              <option key={d} value={d}>{d.toUpperCase()}</option>
            ))}
          </select>
        </div>

        {filteredFindings.length === 0 ? (
          <div className="rounded border border-dashed border-[#2A2E35] p-8 text-center text-xs font-mono text-slate-400">
            No findings match the current filters.
          </div>
        ) : (
          <div className="overflow-x-auto rounded border border-[#2A2E35]" tabIndex={0} aria-label="Evidenced findings table">
            <table className="w-full text-left text-xs font-mono">
              <thead className="border-b border-[#2A2E35] bg-[#0A0B0D] text-[10px] uppercase text-slate-400">
                <tr>
                  <th className="px-3 py-2.5">Severity</th>
                  <th className="px-3 py-2.5">Rule</th>
                  <th className="px-3 py-2.5">Evidence Citation</th>
                  <th className="px-3 py-2.5">Basis</th>
                  <th className="px-3 py-2.5">Description</th>
                  <th className="px-3 py-2.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#2A2E35] bg-[#15171B]">
                {filteredFindings.map((f, idx) => {
                  const isExp = expandedFinding === idx
                  return (
                    <React.Fragment key={f.id || idx}>
                      <tr onClick={() => setExpandedFinding(isExp ? null : idx)} className="cursor-pointer hover:bg-[#1E2228]">
                        <td className="px-3 py-2.5 whitespace-nowrap"><CritBadge tier={f.severity} /></td>
                        <td className="px-3 py-2.5 whitespace-nowrap font-bold text-laser-lime">{f.rule_id}</td>
                        <td className="px-3 py-2.5 whitespace-nowrap">
                          <code className="rounded border border-[#2A2E35] bg-[#0A0B0D] px-2 py-0.5 text-slate-200">
                            {f.evidence_file}:{f.evidence_line ?? 1}
                          </code>
                          {f.commit_sha && (
                            <span className="ml-1.5 rounded border border-[#2A2E35] bg-[#0A0B0D] px-1.5 py-0.5 text-[10px] text-slate-400">
                              {String(f.commit_sha).slice(0, 7)}
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2.5 whitespace-nowrap">
                          <ConfidenceGauge level={f.confidence} basis={f.basis} />
                        </td>
                        <td className="px-3 py-2.5 max-w-md font-sans text-slate-200 truncate">{f.description}</td>
                        <td className="px-3 py-2.5 text-right whitespace-nowrap space-x-1" onClick={(e) => e.stopPropagation()}>
                          {f.fingerprint && (
                            <button
                              type="button"
                              onClick={() => copyText(f.fingerprint, `fp-${idx}`)}
                              className="rounded border border-[#2A2E35] bg-[#0A0B0D] px-2 py-0.5 text-[10px] text-slate-300 hover:border-laser-lime"
                              title="Copy stable fingerprint for .codit.yml suppressions"
                            >
                              {copiedId === `fp-${idx}` ? '✓ FP' : 'Copy FP'}
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => openInspector(f.evidence_file, 'deps')}
                            className="rounded border border-laser-lime/40 bg-laser-lime/10 px-2 py-0.5 text-[10px] font-bold text-laser-lime hover:bg-laser-lime hover:text-black"
                          >
                            Inspect ↗
                          </button>
                        </td>
                      </tr>
                      {isExp && (
                        <tr className="bg-[#0A0B0D]">
                          <td colSpan="6" className="p-4 text-xs font-sans text-slate-200 space-y-2">
                            <p>{f.description}</p>
                            {f.remediation && (
                              <p className="text-slate-300"><strong>Remediation:</strong> {f.remediation}</p>
                            )}
                            {f.fingerprint && (
                              <div className="font-mono text-[10px] text-slate-400">Fingerprint: <code>{f.fingerprint}</code></div>
                            )}
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

      {/* Criticality Leaderboard */}
      <div className="rounded-xl border border-[#2A2E35] bg-[#15171B] p-5 space-y-3">
        <h2 className="text-sm font-bold uppercase tracking-wider font-mono text-slate-100">
          Component Criticality Leaderboard
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
          {(report.criticality_leaderboard || []).map((item, idx) => {
            const compId = item.component?.id || item.id || `comp-${idx}`
            const compName = item.component?.name || item.name || compId
            const compType = item.type || 'Module'
            return (
              <div
                key={compId}
                data-testid="leaderboard-card"
                onClick={() => openInspector(compId, 'deps')}
                className="rounded-lg border border-[#2A2E35] bg-[#0A0B0D] p-3 space-y-2 cursor-pointer hover:border-laser-lime/60"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 min-w-0">
                    <Dot type={compType} />
                    <span className="truncate font-mono font-bold text-xs text-slate-200">{compName}</span>
                  </div>
                  <CritBadge tier={item.tier || 'MEDIUM'} size="xs" />
                </div>
                <div className="text-[10px] font-mono text-slate-400">Reach: {item.reach || 0} nodes</div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Architecture Blueprints */}
      <div className="rounded-xl border border-[#2A2E35] bg-[#15171B] p-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-bold uppercase tracking-wider font-mono text-slate-100">
            Architecture &amp; Blast Radius Blueprint
          </h2>
          <div className="inline-flex rounded border border-[#2A2E35] bg-[#0A0B0D] p-0.5 font-mono text-xs">
            <button
              type="button"
              onClick={() => setActiveDiagramTab('arch')}
              className={`px-3 py-1 rounded font-bold uppercase ${activeDiagramTab === 'arch' ? 'bg-laser-lime text-black' : 'text-slate-400'}`}
            >
              Architecture
            </button>
            <button
              type="button"
              onClick={() => setActiveDiagramTab('blast')}
              className={`px-3 py-1 rounded font-bold uppercase ${activeDiagramTab === 'blast' ? 'bg-laser-lime text-black' : 'text-slate-400'}`}
            >
              Blast Radius
            </button>
          </div>
        </div>
        {activeDiagramTab === 'arch' ? (
          <div className="rounded-xl border border-[#2A2E35] bg-[#0A0B0D] p-4 overflow-x-auto" tabIndex={0} aria-label="Architecture overview diagram">
            <MermaidViewer code={report.architecture_diagram_mermaid} />
          </div>
        ) : (
          <div className="space-y-3 font-mono">
            <select
              aria-label="Select blast radius origin component"
              value={selectedComponentId}
              onChange={(e) => setSelectedComponentId(e.target.value)}
              className="rounded border border-[#2A2E35] bg-[#0A0B0D] px-3 py-1.5 text-xs text-laser-lime"
            >
              <option value="">-- Choose Origin Component --</option>
              {(report.criticality_leaderboard || []).map((item, idx) => {
                const cid = item.component?.id || item.id || `comp-${idx}`
                return <option key={cid} value={cid}>{item.component?.name || item.name || cid}</option>
              })}
            </select>
            {selectedComponentId && blastRadiusData?.mermaid && (
              <div className="rounded-xl border border-[#2A2E35] bg-[#0A0B0D] p-4 overflow-x-auto" tabIndex={0} aria-label="Blast radius diagram">
                <MermaidViewer code={blastRadiusData.mermaid} />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
