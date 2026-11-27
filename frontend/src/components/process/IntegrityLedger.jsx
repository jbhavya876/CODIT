import React, { useEffect, useState } from 'react'
import { CritBadge, ConfidenceGauge } from '../ui.jsx'

const SEV_GLYPH = {
  critical: { glyph: '◆', color: '#FF4A2B' },
  high: { glyph: '▲', color: '#FFB020' },
  medium: { glyph: '■', color: '#FACC15' },
  low: { glyph: '●', color: '#5DE6A8' },
}

const SEV_RANK = { critical: 4, high: 3, medium: 2, low: 1, info: 0 }

export default function IntegrityLedger({ series = [], flaggedCommits = [], findings = [] }) {
  const [viewMode, setViewMode] = useState(() =>
    typeof window !== 'undefined' && window.innerWidth < 768 ? 'table' : 'chart'
  )
  const [selectedCommitSha, setSelectedCommitSha] = useState(null)

  useEffect(() => {
    const onResize = () => {
      if (window.innerWidth < 768) {
        setViewMode('table')
      }
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  // Group history findings by commit_sha
  const findingsByCommit = {}
  for (const f of findings) {
    if (f.commit_sha) {
      findingsByCommit[f.commit_sha] = findingsByCommit[f.commit_sha] || []
      findingsByCommit[f.commit_sha].push(f)
    }
  }

  // Merge chronological commits from flaggedCommits + series summary
  const chronologicalFlagged = [...flaggedCommits].reverse()
  const maxTests = Math.max(1, ...series.map((s) => s.tests_end || s.total_tests || s.commits || 0))
  const maxAsserts = Math.max(1, ...series.map((s) => s.assertions_end || s.total_assertions || 0))
  const maxSkipped = Math.max(1, ...series.map((s) => s.skipped_end || s.total_skipped || 0))

  const selectedFindings = selectedCommitSha ? findingsByCommit[selectedCommitSha] || [] : []
  const selectedCommitObj = flaggedCommits.find((c) => c.sha === selectedCommitSha)

  const handleMarkerKeyDown = (e, idx, list) => {
    if (e.key === 'ArrowRight' && idx < list.length - 1) {
      e.preventDefault()
      setSelectedCommitSha(list[idx + 1].sha)
    } else if (e.key === 'ArrowLeft' && idx > 0) {
      e.preventDefault()
      setSelectedCommitSha(list[idx - 1].sha)
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      setSelectedCommitSha(list[idx].sha)
    } else if (e.key === 'Escape') {
      setSelectedCommitSha(null)
    }
  }

  const summarySentence = `Analyzed ${series.length} time bucket(s); ${flaggedCommits.length} flagged commit(s) with process-integrity signals.`

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-slate-300 font-sans" data-testid="integrity-ledger-summary">
          {summarySentence}
        </p>
        <button
          type="button"
          onClick={() => setViewMode((m) => (m === 'chart' ? 'table' : 'chart'))}
          data-testid="ledger-view-toggle"
          className="rounded border border-[#2A2E35] bg-[#0A0B0D] px-3 py-1 font-mono text-xs font-semibold text-laser-lime hover:border-laser-lime"
        >
          {viewMode === 'table' ? 'View as chart' : 'View as table'}
        </button>
      </div>

      {viewMode === 'chart' ? (
        <div className="rounded-xl border border-[#2A2E35] bg-[#15171B] p-4 space-y-4">
          {series.length === 0 ? (
            <div className="text-xs font-mono text-slate-400 py-4 text-center">
              No commit timeline series recorded in window.
            </div>
          ) : (
            <div className="space-y-3">
              {[
                { label: 'Tests', key: 'tests_end', fallback: 'commits', max: maxTests, color: '#D4FF3A' },
                { label: 'Assertions', key: 'assertions_end', fallback: 'commits', max: maxAsserts, color: '#5DE6A8' },
                { label: 'Skipped / xfail', key: 'skipped_end', fallback: 'flagged_commits', max: maxSkipped, color: '#FFB020' },
              ].map((track) => (
                <div key={track.label} className="grid grid-cols-12 items-center gap-3">
                  <div className="col-span-3 sm:col-span-2 font-mono text-[11px] text-slate-300">
                    {track.label}
                  </div>
                  <div className="col-span-9 sm:col-span-10 flex items-end gap-1 h-10 bg-[#0A0B0D] border border-[#2A2E35] rounded px-2 py-1 overflow-x-auto">
                    {series.map((pt, i) => {
                      const val = pt[track.key] ?? pt[track.fallback] ?? 0
                      const hPct = Math.max(12, Math.round((val * 100) / track.max))
                      return (
                        <div
                          key={pt.bucket || i}
                          title={`${pt.bucket || i}: ${val}`}
                          className="flex-1 min-w-[8px] rounded-t-sm"
                          style={{ height: `${hPct}%`, backgroundColor: track.color, opacity: 0.85 }}
                        />
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Keyboard-focusable commit event markers oldest -> newest */}
          {chronologicalFlagged.length > 0 && (
            <div className="border-t border-[#2A2E35] pt-3 space-y-2">
              <div className="font-mono text-[10px] uppercase tracking-wider text-slate-400">
                Flagged Commits (oldest &rarr; newest · use Left/Right arrows + Enter to inspect)
              </div>
              <div className="flex flex-wrap gap-2" role="group" aria-label="Flagged commits timeline">
                {chronologicalFlagged.map((c, idx) => {
                  const cFindings = findingsByCommit[c.sha] || []
                  const topSev = cFindings.reduce(
                    (best, f) => ((SEV_RANK[f.severity] || 0) > (SEV_RANK[best] || 0) ? f.severity : best),
                    'medium'
                  )
                  const st = SEV_GLYPH[topSev] || SEV_GLYPH.medium
                  const selected = selectedCommitSha === c.sha
                  return (
                    <button
                      key={c.sha || idx}
                      type="button"
                      data-testid={`ledger-marker-${idx}`}
                      aria-pressed={selected}
                      onClick={() => setSelectedCommitSha(selected ? null : c.sha)}
                      onKeyDown={(e) => handleMarkerKeyDown(e, idx, chronologicalFlagged)}
                      className={`inline-flex items-center gap-1.5 rounded border px-2 py-1 font-mono text-xs transition ${
                        selected
                          ? 'border-laser-lime bg-laser-lime/15 text-white'
                          : 'border-[#2A2E35] bg-[#0A0B0D] text-slate-300 hover:border-slate-500'
                      }`}
                    >
                      <span style={{ color: st.color }} aria-hidden="true">{st.glyph}</span>
                      <span>{c.short || String(c.sha || '').slice(0, 7)}</span>
                      <span className="text-[10px] text-slate-400">{String(c.date || '').slice(0, 10)}</span>
                    </button>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-[#2A2E35] bg-[#15171B]" tabIndex={0} aria-label="Flagged commits table">
          <table className="w-full text-left text-xs font-mono">
            <thead className="border-b border-[#2A2E35] bg-[#0A0B0D] text-[10px] uppercase text-slate-400">
              <tr>
                <th className="px-3 py-2">Commit</th>
                <th className="px-3 py-2">Date</th>
                <th className="px-3 py-2">Attribution</th>
                <th className="px-3 py-2">Findings</th>
                <th className="px-3 py-2 text-right">Inspect</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#2A2E35]">
              {chronologicalFlagged.length === 0 ? (
                <tr>
                  <td colSpan="5" className="px-3 py-6 text-center text-slate-400">
                    No flagged process-integrity commits in analyzed window.
                  </td>
                </tr>
              ) : (
                chronologicalFlagged.map((c, idx) => {
                  const cFindings = findingsByCommit[c.sha] || []
                  return (
                    <tr key={c.sha || idx} className="hover:bg-[#1E2228]">
                      <td className="px-3 py-2 text-laser-lime">{c.short || String(c.sha || '').slice(0, 7)}</td>
                      <td className="px-3 py-2 text-slate-300">{String(c.date || '').slice(0, 10)}</td>
                      <td className="px-3 py-2 text-slate-400">{c.attribution_basis || 'unknown'}</td>
                      <td className="px-3 py-2 tabular-nums">{cFindings.length}</td>
                      <td className="px-3 py-2 text-right">
                        <button
                          type="button"
                          onClick={() => setSelectedCommitSha(c.sha)}
                          className="rounded border border-[#2A2E35] bg-[#0A0B0D] px-2 py-0.5 text-[11px] text-laser-lime hover:border-laser-lime"
                        >
                          Details
                        </button>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Selected commit side/detail panel */}
      {selectedCommitSha && (
        <aside
          aria-label="Selected commit findings"
          data-testid="commit-detail-panel"
          className="rounded-xl border border-laser-lime/40 bg-[#0A0B0D] p-4 space-y-3 font-mono"
        >
          <div className="flex items-center justify-between border-b border-[#2A2E35] pb-2">
            <div className="text-xs font-bold text-slate-100">
              Commit <code>{selectedCommitObj?.short || selectedCommitSha.slice(0, 7)}</code> ·{' '}
              <span className="text-slate-400">{selectedCommitObj?.date || 'ISO date unavailable'}</span>
            </div>
            <button
              type="button"
              onClick={() => setSelectedCommitSha(null)}
              className="text-xs text-slate-400 hover:text-white"
            >
              Close
            </button>
          </div>
          {selectedFindings.length === 0 ? (
            <p className="text-xs text-slate-400">
              Commit metadata flagged (test-claim heuristic or threshold note); no standalone rule rows attached.
            </p>
          ) : (
            <ul className="space-y-2 text-xs">
              {selectedFindings.map((f) => (
                <li key={f.id} className="rounded border border-[#2A2E35] bg-[#15171B] p-2.5 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <CritBadge tier={f.severity} size="xs" />
                    <span className="font-bold text-laser-lime">{f.rule_id}</span>
                    <ConfidenceGauge level={f.confidence} basis={f.basis || 'HISTORY PROOF'} />
                    <code className="text-slate-300">{f.evidence_file}:{f.evidence_line ?? 1}</code>
                  </div>
                  <p className="text-slate-300 font-sans">{f.description}</p>
                </li>
              ))}
            </ul>
          )}
        </aside>
      )}
    </div>
  )
}
