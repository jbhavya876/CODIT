import React, { useMemo, useState } from 'react'

export const LICENSE_DISCLAIMER =
  'Automated license classification. Not legal advice. Verify with counsel before relying on it.'

const CLASS_GLYPHS = {
  network_copyleft: { glyph: '◆', label: 'Network Copyleft', cls: 'text-[#FF4A2B] border-[#5A1C16] bg-[#2A0E0B]' },
  strong_copyleft: { glyph: '◆', label: 'Strong Copyleft', cls: 'text-[#FF4A2B] border-[#5A1C16] bg-[#2A0E0B]' },
  source_available: { glyph: '▲', label: 'Source Available', cls: 'text-[#FFB020] border-[#5E3808] bg-[#281805]' },
  unknown: { glyph: '■', label: 'Unresolved / Unknown', cls: 'text-[#FACC15] border-[#564908] bg-[#241F06]' },
  weak_copyleft: { glyph: '●', label: 'Weak Copyleft', cls: 'text-[#5DE6A8] border-[#164E37] bg-[#0B231A]' },
  permissive: { glyph: '○', label: 'Permissive', cls: 'text-[#8CC8FF] border-[#1A3B66] bg-[#0C1B2E]' },
}

export default function LicensesTab({ licensesData }) {
  const [classFilter, setClassFilter] = useState('all')
  const [scopeFilter, setScopeFilter] = useState('all')
  const [query, setQuery] = useState('')

  const cov = licensesData?.coverage || {}
  const register = licensesData?.register || []
  const proj = licensesData?.project_license
  const unpinned = cov.unpinned || []
  const disclaimer = licensesData?.disclaimer || LICENSE_DISCLAIMER

  const filtered = useMemo(() => {
    return register.filter((item) => {
      if (classFilter !== 'all' && item.license_class !== classFilter) return false
      if (scopeFilter !== 'all' && item.scope !== scopeFilter) return false
      if (query.trim()) {
        const q = query.toLowerCase()
        if (
          !String(item.package || '').toLowerCase().includes(q) &&
          !String(item.spdx_id || '').toLowerCase().includes(q) &&
          !String(item.rule_id || '').toLowerCase().includes(q)
        ) {
          return false
        }
      }
      return true
    })
  }, [register, classFilter, scopeFilter, query])

  const grouped = useMemo(() => {
    const groups = {}
    for (const row of filtered) {
      const k = row.license_class || 'unknown'
      groups[k] = groups[k] || []
      groups[k].push(row)
    }
    return groups
  }, [filtered])

  return (
    <div className="space-y-5" data-testid="licenses-tab-panel">
      {/* Coverage Line & Project License */}
      <div className="rounded-xl border border-[#2A2E35] bg-[#15171B] p-4 flex flex-wrap items-center justify-between gap-3 font-mono text-xs">
        <div className="space-y-1">
          <div className="font-bold text-slate-100 tabular-nums" data-testid="license-coverage-line">
            {cov.total ? `${cov.resolved ?? 0} of ${cov.total ?? 0} resolved; ${cov.unresolved ?? 0} unresolved (${cov.resolved_pct ?? 0}%)` : 'No pinned dependencies found in lockfiles or manifests.'}
          </div>
          <div className="text-[11px] text-slate-400">
            Project license: <strong>{proj?.spdx_id || 'Unknown'}</strong> ({proj?.license_class || 'unknown'})
            {unpinned.length > 0 ? ` · ${unpinned.length} unpinned manifest specifier(s) not assessed` : ''}
          </div>
        </div>
        <p className="text-[11px] text-slate-300 font-sans border-l-2 border-laser-lime pl-3 max-w-md" data-testid="license-disclaimer">
          {disclaimer}
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 font-mono text-xs">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter package, SPDX, or rule ID..."
          aria-label="Filter license register"
          className="flex-1 min-w-[200px] rounded border border-[#2A2E35] bg-[#0A0B0D] px-3 py-1.5 text-slate-100 placeholder-slate-500 focus:border-laser-lime focus:outline-none"
        />
        <select
          value={classFilter}
          onChange={(e) => setClassFilter(e.target.value)}
          aria-label="Filter by license class"
          data-testid="license-class-filter"
          className="rounded border border-[#2A2E35] bg-[#0A0B0D] px-3 py-1.5 text-slate-200 focus:border-laser-lime focus:outline-none"
        >
          <option value="all">ALL CLASSES</option>
          {Object.keys(CLASS_GLYPHS).map((k) => (
            <option key={k} value={k}>
              {CLASS_GLYPHS[k].label.toUpperCase()}
            </option>
          ))}
        </select>
        <select
          value={scopeFilter}
          onChange={(e) => setScopeFilter(e.target.value)}
          aria-label="Filter by dependency scope"
          className="rounded border border-[#2A2E35] bg-[#0A0B0D] px-3 py-1.5 text-slate-200 focus:border-laser-lime focus:outline-none"
        >
          <option value="all">ALL SCOPES</option>
          <option value="prod">PROD</option>
          <option value="dev">DEV</option>
        </select>
      </div>

      {/* Grouped License Register */}
      {filtered.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[#2A2E35] p-8 text-center text-xs font-mono text-slate-400">
          No dependencies match the selected license filters.
        </div>
      ) : (
        Object.entries(grouped).map(([clsKey, items]) => {
          const meta = CLASS_GLYPHS[clsKey] || CLASS_GLYPHS.unknown
          return (
            <div key={clsKey} className="rounded-xl border border-[#2A2E35] bg-[#15171B] overflow-hidden">
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#2A2E35] bg-[#0A0B0D]">
                <span className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 font-mono text-[11px] font-bold ${meta.cls}`}>
                  <span aria-hidden="true">{meta.glyph}</span>
                  <span>{meta.label}</span>
                </span>
                <span className="font-mono text-[11px] text-slate-400 tabular-nums">{items.length} package(s)</span>
              </div>
              <div className="overflow-x-auto" tabIndex={0} aria-label={`${meta.label} license register`}>
                <table className="w-full text-left text-xs font-mono">
                  <thead className="border-b border-[#2A2E35] text-[10px] uppercase text-slate-400">
                    <tr>
                      <th className="px-3 py-2">Package</th>
                      <th className="px-3 py-2">Version</th>
                      <th className="px-3 py-2">Scope</th>
                      <th className="px-3 py-2">SPDX License</th>
                      <th className="px-3 py-2">Rule</th>
                      <th className="px-3 py-2">Evidence</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#2A2E35]">
                    {items.map((row, idx) => (
                      <tr key={`${row.ecosystem}-${row.package}-${row.version}-${idx}`} className="hover:bg-[#1E2228]">
                        <td className="px-3 py-2 font-semibold text-slate-100">{row.package}</td>
                        <td className="px-3 py-2 text-slate-300 tabular-nums">{row.version}</td>
                        <td className="px-3 py-2 uppercase text-slate-400">{row.scope}</td>
                        <td className="px-3 py-2 text-laser-lime">{row.spdx_id}</td>
                        <td className="px-3 py-2 text-slate-300">{row.rule_id || '—'}</td>
                        <td className="px-3 py-2 text-slate-400">
                          <code>{row.evidence_file}:{row.evidence_line ?? 1}</code>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )
        })
      )}
    </div>
  )
}
