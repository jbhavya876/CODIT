import React from 'react'

export const ATTRIBUTION_LIMITATION =
  'Attribution reflects declarations in commit metadata. Commits without a declaration are unknown, not human-authored.'

export default function AttributionStrip({ attribution = {}, headToolingPresent = false }) {
  const total = attribution.total_commits ?? 0
  const declared = attribution.declared_commits ?? 0
  const unknown = Math.max(0, total - declared)
  const declaredPct = total > 0 ? Math.round((declared * 100) / total) : 0
  const unknownPct = 100 - declaredPct

  return (
    <section
      aria-label="Commit Metadata Attribution Summary"
      className="rounded-xl border border-[#2A2E35] bg-[#15171B] p-4 space-y-3"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-mono text-xs font-bold uppercase tracking-wider text-slate-200">
          Declared Agent Signal vs. Unknown Commits
        </div>
        <div className="flex items-center gap-2 font-mono text-[11px]">
          <span
            className={`rounded border px-2 py-0.5 ${
              headToolingPresent
                ? 'border-laser-lime/40 bg-laser-lime/10 text-laser-lime'
                : 'border-[#2A2E35] bg-[#0A0B0D] text-slate-400'
            }`}
          >
            Agent config files at HEAD: {headToolingPresent ? 'Present' : 'Not detected'}
          </span>
        </div>
      </div>

      {/* Segmented bar */}
      <div
        className="w-full h-3 rounded overflow-hidden flex border border-[#2A2E35] bg-[#0A0B0D]"
        role="img"
        aria-label={`${declaredPct}% commits declare agent signal (${declared} of ${total}); ${unknownPct}% unknown (${unknown} of ${total})`}
      >
        {declaredPct > 0 && (
          <div className="bg-laser-lime h-full" style={{ width: `${declaredPct}%` }} />
        )}
        {unknownPct > 0 && (
          <div className="bg-slate-600 h-full" style={{ width: `${unknownPct}%` }} />
        )}
      </div>

      <div className="flex flex-wrap items-center gap-4 text-xs font-mono text-slate-300 tabular-nums">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 bg-laser-lime rounded-sm" aria-hidden="true" />
          Declares agent signal: <strong>{declared}</strong> ({declaredPct}%)
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 bg-slate-600 rounded-sm" aria-hidden="true" />
          Unknown (no declaration): <strong>{unknown}</strong> ({unknownPct}%)
        </span>
      </div>

      <p className="text-[11px] text-slate-400 border-t border-[#2A2E35] pt-2">
        {ATTRIBUTION_LIMITATION}
      </p>
    </section>
  )
}
