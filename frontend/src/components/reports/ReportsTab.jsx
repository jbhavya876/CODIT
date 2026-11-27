import React, { useEffect, useState } from 'react'
import { api } from '../../api.js'
import { Download, Printer, ShieldAlert } from 'lucide-react'

const PROFILES = [
  { id: 'technical', label: 'Technical' },
  { id: 'diligence', label: 'Diligence' },
  { id: 'executive', label: 'Executive' },
  { id: 'underwriting', label: 'Underwriting JSON' },
]

export default function ReportsTab({ auditId, onOpenPayment }) {
  const [profile, setProfile] = useState('technical')
  // Hourly rate is held strictly in component memory for display rendering only; never persisted
  const [hourlyRate, setHourlyRate] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!auditId) return
    let cancelled = false
    setLoading(true)
    setError(null)
    api
      .getProfileReport(auditId, {
        profile,
        hourlyRate: hourlyRate.trim(),
      })
      .then((res) => {
        if (!cancelled) {
          setData(res)
          setLoading(false)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setData(null)
          setError(err)
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [auditId, profile, hourlyRate])

  if (!auditId) {
    return (
      <div className="rounded-xl border border-dashed border-[#2A2E35] p-8 text-center font-mono text-xs text-slate-400">
        No persisted audit ID active yet. Run or select an audit from Ingest to inspect profile views.
      </div>
    )
  }

  return (
    <div className="space-y-5" data-testid="reports-tab-panel">
      {/* ProfileSwitcher + Optional Hourly Rate + Downloads */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#2A2E35] bg-[#15171B] p-4">
        <div className="inline-flex flex-wrap rounded-lg border border-[#2A2E35] bg-[#0A0B0D] p-1 gap-1" role="tablist" aria-label="Report profile switcher">
          {PROFILES.map((p) => (
            <button
              key={p.id}
              role="tab"
              aria-selected={profile === p.id}
              data-testid={`profile-switch-${p.id}`}
              onClick={() => setProfile(p.id)}
              className={`rounded px-3 py-1.5 font-mono text-xs font-bold uppercase tracking-wider transition ${
                profile === p.id ? 'bg-laser-lime text-black' : 'text-slate-300 hover:text-white'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
          <label htmlFor="hourly-rate-input" className="text-slate-400">
            Hourly rate (1–2000):
          </label>
          <input
            id="hourly-rate-input"
            type="number"
            min="1"
            max="2000"
            value={hourlyRate}
            onChange={(e) => setHourlyRate(e.target.value)}
            placeholder="optional"
            className="w-24 rounded border border-[#2A2E35] bg-[#0A0B0D] px-2.5 py-1 text-xs text-slate-100 focus:border-laser-lime focus:outline-none"
          />
          {profile === 'underwriting' ? (
            <a
              href={api.getProfileReportUrl(auditId, { profile: 'underwriting', format: 'json' })}
              download={`codit-underwriting-${auditId}.json`}
              className="inline-flex items-center gap-1.5 rounded border border-laser-lime bg-laser-lime px-3 py-1.5 font-bold text-black"
            >
              <Download className="w-3.5 h-3.5" aria-hidden="true" />
              <span>Download JSON</span>
            </a>
          ) : (
            <>
              <a
                href={api.getProfileReportUrl(auditId, { profile, format: 'md', hourlyRate })}
                target="_blank"
                rel="noreferrer"
                className="rounded border border-[#2A2E35] bg-[#0A0B0D] px-3 py-1.5 text-slate-200 hover:border-laser-lime"
              >
                Markdown
              </a>
              <a
                href={api.getProfileReportUrl(auditId, { profile, format: 'html', hourlyRate })}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 rounded border border-laser-lime bg-laser-lime px-3 py-1.5 font-bold text-black"
              >
                <Printer className="w-3.5 h-3.5" aria-hidden="true" />
                <span>HTML / Print</span>
              </a>
            </>
          )}
        </div>
      </div>

      {loading && (
        <div className="p-8 text-center font-mono text-xs text-slate-400">Loading {profile} profile...</div>
      )}

      {error && (
        <div className="rounded-xl border border-amber-900/60 bg-amber-950/20 p-5 space-y-3 font-mono text-xs">
          <div className="flex items-center gap-2 text-[#FFB020] font-bold">
            <ShieldAlert className="w-4 h-4" aria-hidden="true" />
            <span>Profile Gated ({error.code || error.status})</span>
          </div>
          <p className="text-slate-200 font-sans">{error.message}</p>
          {(error.status === 402 || error.status === 403) && onOpenPayment && (
            <button
              type="button"
              onClick={onOpenPayment}
              className="rounded border border-laser-lime bg-laser-lime px-4 py-1.5 text-xs font-bold text-black"
            >
              Open Settlement Flow
            </button>
          )}
        </div>
      )}

      {/* Dossier Paper Mode Rendering for Technical / Diligence / Executive */}
      {!loading && data && profile !== 'underwriting' && (
        <article className="bg-[#EFEAE0] text-[#101114] rounded-xl border border-[#D8D2C5] p-6 sm:p-8 space-y-6 shadow-xl">
          {profile === 'diligence' && (
            <>
              <header className="border-b-2 border-[#101114] pb-4 flex flex-wrap justify-between gap-2">
                <div>
                  <h2 className="font-serif text-2xl">Due Diligence Technical &amp; IP Ledger</h2>
                  <p className="font-mono text-xs text-[#575A65]">
                    Rubric {data.rubric_version} · Phase {data.verdict_and_coverage?.phase} · Score {data.verdict_and_coverage?.overall_score}/100
                  </p>
                </div>
              </header>
              <section className="space-y-2">
                <h3 className="font-mono text-xs font-bold uppercase tracking-wider">1. Verdict &amp; Coverage</h3>
                <p className="font-mono text-xs tabular-nums">
                  Files scanned: {data.verdict_and_coverage?.coverage?.files_scanned} / {data.verdict_and_coverage?.coverage?.files_total}
                </p>
                {(data.verdict_and_coverage?.not_assessed || []).map((na) => (
                  <p key={na.dimension} className="text-xs font-mono text-[#B45309]">{na.text}</p>
                ))}
              </section>
              <section className="space-y-1">
                <h3 className="font-mono text-xs font-bold uppercase tracking-wider">2. Red-Flag Register</h3>
                {(data.red_flag_register || []).length === 0 ? (
                  <p className="text-xs">No release blockers triggered.</p>
                ) : (
                  <ul className="list-disc pl-5 text-xs space-y-1">
                    {data.red_flag_register.map((r) => (
                      <li key={r.blocker_code}>
                        <strong>{r.blocker_code}</strong>: {r.summary} ({r.count} refs)
                      </li>
                    ))}
                  </ul>
                )}
              </section>
              <section className="space-y-1">
                <h3 className="font-mono text-xs font-bold uppercase tracking-wider">3. IP &amp; Licensing Register</h3>
                <p className="text-xs italic">{data.ip_and_licensing_register?.disclaimer}</p>
              </section>
              <section className="space-y-1">
                <h3 className="font-mono text-xs font-bold uppercase tracking-wider">4. Process-Integrity Timeline</h3>
                <p className="text-xs italic">{data.process_integrity_timeline?.attribution_limitation}</p>
                {!data.process_integrity_timeline?.assessed && (
                  <p className="text-xs font-mono">{data.process_integrity_timeline?.status_text}</p>
                )}
              </section>
              <section className="space-y-1">
                <h3 className="font-mono text-xs font-bold uppercase tracking-wider">5. Key-Person Exposure</h3>
                {data.key_person_exposure?.assessed ? (
                  <p className="text-xs font-mono">
                    Top contributor share: {data.key_person_exposure.top_contributor_share_pct}% · Single-owner dirs: {data.key_person_exposure.single_owner_dirs_count}
                  </p>
                ) : (
                  <p className="text-xs font-mono">{data.key_person_exposure?.status_text}</p>
                )}
              </section>
              <section className="space-y-1">
                <h3 className="font-mono text-xs font-bold uppercase tracking-wider">6. Remediation Estimate</h3>
                <p className="text-xs font-mono tabular-nums">
                  {data.remediation_estimate?.person_days?.min}..{data.remediation_estimate?.person_days?.max} person-days (likely {data.remediation_estimate?.person_days?.likely})
                </p>
                {data.remediation_estimate?.monetary_range && (
                  <p className="text-xs font-mono font-bold tabular-nums">
                    Estimated cost range: {data.remediation_estimate.monetary_range.min}..{data.remediation_estimate.monetary_range.max} ({data.remediation_estimate.monetary_range.unit})
                  </p>
                )}
              </section>
              <footer className="border-t border-[#D8D2C5] pt-3 text-[11px] text-[#575A65]">
                {data.methodology_and_limitations?.methodology}
              </footer>
            </>
          )}

          {profile === 'executive' && (
            <>
              <header className="border-b-2 border-[#101114] pb-4">
                <h2 className="font-serif text-2xl">
                  Executive Summary — {data.verdict_seal?.phase} ({data.verdict_seal?.overall_score}/100)
                </h2>
              </header>
              <section className="space-y-2">
                <h3 className="font-mono text-xs font-bold uppercase tracking-wider">Risk Themes</h3>
                <ul className="space-y-2 text-sm">
                  {(data.themes || []).map((t, i) => (
                    <li key={i} className="border-l-2 border-[#101114] pl-3">
                      <strong>{t.title}</strong>: {t.rationale}
                    </li>
                  ))}
                </ul>
              </section>
              <section className="space-y-2">
                <h3 className="font-mono text-xs font-bold uppercase tracking-wider">Prioritized Actions</h3>
                <ol className="list-decimal pl-5 text-sm space-y-1">
                  {(data.actions || []).map((a, i) => (
                    <li key={i}>{a.text}</li>
                  ))}
                </ol>
              </section>
              <section className="space-y-1">
                <h3 className="font-mono text-xs font-bold uppercase tracking-wider">What This Does Not Cover</h3>
                <ul className="list-disc pl-5 text-xs space-y-1 text-[#575A65]">
                  {(data.what_this_does_not_cover || []).map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              </section>
              <footer className="border-t border-[#D8D2C5] pt-3 text-[11px] text-[#575A65]">
                {data.methodology}
              </footer>
            </>
          )}

          {profile === 'technical' && (
            <>
              <header className="border-b-2 border-[#101114] pb-4">
                <h2 className="font-serif text-2xl">
                  Technical Assurance Dossier — {data.scorecard?.overall_score}/100 ({data.scorecard?.phase})
                </h2>
                <p className="font-mono text-xs text-[#575A65]">
                  Rubric {data.rubric_version} · Effort range {data.effort?.person_days?.min}..{data.effort?.person_days?.max} person-days
                  {data.effort?.monetary_range
                    ? ` · Rate range ${data.effort.monetary_range.min}..${data.effort.monetary_range.max} (${data.effort.monetary_range.unit})`
                    : ''}
                </p>
              </header>
              <p className="text-xs">{data.methodology}</p>
              <p className="text-xs font-mono">
                Process: {data.process?.assessed ? `${data.process.coverage?.commits_analyzed ?? 0} commits analyzed` : data.process?.status_text}
              </p>
              <p className="text-xs font-mono">Licenses: {data.licenses?.disclaimer}</p>
            </>
          )}
        </article>
      )}

      {!loading && data && profile === 'underwriting' && (
        <div className="rounded-xl border border-[#2A2E35] bg-[#15171B] p-4 space-y-3 font-mono text-xs">
          <div className="flex items-center justify-between text-slate-300">
            <span>Schema: <code>codit.underwriting.v1</code> (zero repository-derived strings)</span>
            <a href="/rubric/2.0.0" target="_blank" rel="noreferrer" className="text-laser-lime hover:underline">
              Rubric 2.0.0 Spec
            </a>
          </div>
          <pre className="rounded border border-[#2A2E35] bg-[#0A0B0D] p-4 text-[11px] overflow-x-auto text-slate-200">
            {JSON.stringify(data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}
