import React from 'react'
import AttributionStrip, { ATTRIBUTION_LIMITATION } from './AttributionStrip.jsx'
import IntegrityLedger from './IntegrityLedger.jsx'

export default function ProcessTab({ processData, findings = [] }) {
  const assessed = Boolean(processData?.assessed)
  const cov = processData?.coverage || {}

  return (
    <div className="space-y-5" data-testid="process-tab-panel">
      {/* Uncollapsed top coverage banner */}
      <section
        aria-label="Process History Coverage Banner"
        data-testid="process-coverage-banner"
        className={`rounded-xl border p-4 font-mono text-xs ${
          assessed
            ? 'border-[#2A2E35] bg-[#15171B] text-slate-200'
            : 'border-amber-900/60 bg-amber-950/20 text-[#FFB020]'
        }`}
      >
        {assessed ? (
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <strong>Process History Assessed:</strong> {cov.commits_analyzed ?? 0} commit(s) analyzed in window
              {cov.shallow_boundary ? ' · Shallow clone boundary reached' : ''}
              {cov.caps_hit ? ' · Depth/size caps hit (partial)' : ''}
            </div>
            <span className="text-[11px] text-slate-400">
              Raw commit text &amp; identities discarded
            </span>
          </div>
        ) : (
          <div className="space-y-1">
            <div className="font-bold">{processData?.status_text || 'Not assessed — git history was not evaluated.'}</div>
            <div className="text-[11px] text-slate-300 font-sans">{ATTRIBUTION_LIMITATION}</div>
          </div>
        )}
      </section>

      {assessed && (
        <>
          <AttributionStrip
            attribution={processData?.attribution || {}}
            headToolingPresent={Boolean(processData?.head_tooling_present)}
          />
          <IntegrityLedger
            series={processData?.series || []}
            flaggedCommits={processData?.flagged_commits || []}
            findings={findings}
          />
        </>
      )}
    </div>
  )
}
