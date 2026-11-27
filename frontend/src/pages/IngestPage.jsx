import React, { useState, useEffect, useRef } from 'react'
import { api } from '../api.js'
import { navigate, href } from '../router.js'
import { Terminal, UploadCloud, Globe, Lock, ShieldCheck, CheckCircle2, ArrowRight, History } from 'lucide-react'

const PIPELINE_STEPS = [
  { id: 1, stage: 'ingest', title: 'Intake & Archive Validation', desc: 'URL/branch check, archive quota & Zip-Slip guards' },
  { id: 2, stage: 'history', title: 'Git Object History Walk', desc: 'Dulwich bare-history read in bounded worker (commit text discarded)' },
  { id: 3, stage: 'parse', title: 'Tree-sitter AST & Manifests', desc: 'Syntactic node extraction, internal imports & dependency lockfiles' },
  { id: 4, stage: 'collect', title: 'Security & Process Signals', desc: 'CVE lookup, credential patterns, test integrity & scalability signals' },
  { id: 5, stage: 'licenses', title: 'License & IP Resolution', desc: 'SPDX expression normalization, allowlisted registry checks & conflict matrix' },
  { id: 6, stage: 'score', title: 'Rubric 2.0.0 & Graph Assembly', desc: 'Deterministic scoring, effort bounds & openCypher blast-radius graph' },
]

// Enumerated event code -> operator-controlled copy (never renders server free text)
const EVENT_CODE_COPY = {
  ingest_started: 'INTAKE: Queuing source ingestion and validation...',
  ingest_done: (d) => `INTAKE: Extracted ${d?.file_count ?? 0} source files safely.`,
  history_started: 'HISTORY: Reading commit objects in bounded dulwich worker...',
  history_done: (d) => `HISTORY: Analyzed ${d?.commits ?? 0} commits; raw commit text discarded.`,
  history_not_assessed: 'HISTORY: Process integrity not assessed for this source.',
  parse_done: (d) => `PARSE: Extracted AST syntax trees across ${d?.ast_files ?? 0} files.`,
  collect_done: (d) => `COLLECT: Evaluated static and process rules (${d?.findings_count ?? 0} findings so far).`,
  licenses_started: 'LICENSES: Normalizing SPDX declarations and dependency lockfiles...',
  licenses_done: (d) => `LICENSES: Resolved ${d?.resolved ?? 0} of ${d?.total ?? 0} pinned dependencies.`,
  score_done: (d) => `SCORE: Computed deterministic Rubric 2.0.0 score (${d?.overall ?? 0}/100).`,
  report_ready: 'DELIVER: Audit persisted and ready for inspection in Cockpit.',
  audit_failed: 'DELIVER: Audit terminated due to stage failure.',
}

const ERROR_CODE_MESSAGES = {
  invalid_source: 'Unsupported source or unsafe repository/branch specifier. Provide https://github.com/owner/repo or owner/repo.',
  repo_too_large: 'Repository or ZIP archive exceeds size or file count limits. Trim build artifacts or archive size and retry.',
  invalid_archive: 'Archive failed Zip-Slip, symlink, or compression safety checks. Rebuild the .zip from a clean working tree.',
  history_unavailable: 'Git history could not be acquired within sandbox limits. Re-run with a smaller commit window or History Off.',
  job_interrupted: 'Audit job hit its worker time/memory limit or restarted. Submit again or reduce history depth.',
  rate_limited: 'Rate limit reached for audit creation. Wait briefly and retry.',
  network_error: 'Unable to reach the CODIT API server. Verify backend availability and try again.',
}

const HISTORY_PRESETS = [
  { id: 'off', label: 'Off', enabled: false, maxCommits: 100, maxDays: 30 },
  { id: '100', label: 'Last 100 commits', enabled: true, maxCommits: 100, maxDays: 365 },
  { id: '500', label: 'Last 500 commits (default)', enabled: true, maxCommits: 500, maxDays: 365 },
  { id: '365d', label: 'Last 365 days', enabled: true, maxCommits: 500, maxDays: 365 },
]

function stageToStepIndex(stage) {
  const idx = PIPELINE_STEPS.findIndex((s) => s.stage === stage)
  return idx >= 0 ? idx + 1 : 1
}

export default function IngestPage() {
  const [activeTab, setActiveTab] = useState('public') // 'public', 'zip', 'private'
  const [publicUrl, setPublicUrl] = useState('https://github.com/charmi-reddy/Dependency-Detective')
  const [publicRef, setPublicRef] = useState('main')

  const [privateRepo, setPrivateRepo] = useState('')
  const [privateToken, setPrivateToken] = useState('')
  const [privateBranch, setPrivateBranch] = useState('')

  const [zipFile, setZipFile] = useState(null)
  const [dragOver, setDragOver] = useState(false)

  const [historyPreset, setHistoryPreset] = useState('500')
  const [goal, setGoal] = useState('production')

  const [loading, setLoading] = useState(false)
  const [currentStep, setCurrentStep] = useState(1)
  const [terminalLogs, setTerminalLogs] = useState([])
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const terminalEndRef = useRef(null)
  const abortPollRef = useRef(false)

  useEffect(() => {
    return () => {
      abortPollRef.current = true
    }
  }, [])

  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: 'auto' })
  }, [terminalLogs])

  const selectedHist = HISTORY_PRESETS.find((p) => p.id === historyPreset) || HISTORY_PRESETS[2]

  const formatEventLine = (ev) => {
    const entry = EVENT_CODE_COPY[ev.code]
    const msg = typeof entry === 'function' ? entry(ev.data) : entry || `EVENT: ${ev.code}`
    const tsLabel = ev.ts ? new Date(ev.ts).toLocaleTimeString() : new Date().toLocaleTimeString()
    return `[${tsLabel}] ${msg}`
  }

  const pollUntilDone = async (auditId, targetLabel) => {
    let lastEventId = 0
    abortPollRef.current = false
    const deadline = Date.now() + 180000

    while (!abortPollRef.current && Date.now() < deadline) {
      const [statusObj, events] = await Promise.all([
        api.getAudit(auditId),
        api.getAuditEvents(auditId, lastEventId).catch(() => []),
      ])

      if (Array.isArray(events) && events.length > 0) {
        lastEventId = events[events.length - 1].id
        setTerminalLogs((prev) => [...prev, ...events.map(formatEventLine)])
      }

      if (statusObj.stage) {
        setCurrentStep(stageToStepIndex(statusObj.stage))
      }

      if (statusObj.status === 'completed') {
        try {
          window.localStorage.setItem('codit_active_audit_id', auditId)
        } catch {
          /* ignore storage restrictions */
        }
        setCurrentStep(PIPELINE_STEPS.length)
        setResult({
          audit_id: auditId,
          target: targetLabel,
          statusObj,
        })
        return
      }

      if (statusObj.status === 'failed') {
        const code = statusObj.error_code || 'job_interrupted'
        throw { code, message: ERROR_CODE_MESSAGES[code] || `Audit failed (${code}).` }
      }

      await new Promise((r) => setTimeout(r, 350))
    }

    throw { code: 'job_interrupted', message: ERROR_CODE_MESSAGES.job_interrupted }
  }

  const startAudit = async (submitFn, targetLabel) => {
    setLoading(true)
    setError(null)
    setResult(null)
    setCurrentStep(1)
    setTerminalLogs([])

    try {
      const queued = await submitFn()
      await pollUntilDone(queued.audit_id, targetLabel)
    } catch (err) {
      const code = err?.code || 'error'
      setError(ERROR_CODE_MESSAGES[code] || err?.message || 'Unable to start audit.')
    } finally {
      setLoading(false)
    }
  }

  const handlePublicSubmit = (e) => {
    e.preventDefault()
    startAudit(
      () =>
        api.createAuditJson({
          type: 'public',
          url: publicUrl,
          ref: publicRef || 'main',
          goal,
          history: {
            enabled: selectedHist.enabled,
            max_commits: selectedHist.maxCommits,
            max_days: selectedHist.maxDays,
          },
        }),
      publicUrl
    )
  }

  const handlePrivateSubmit = (e) => {
    e.preventDefault()
    startAudit(
      () =>
        api.createAuditJson({
          type: 'private',
          repo: privateRepo,
          token: privateToken,
          branch: privateBranch || undefined,
          goal,
          history: {
            enabled: selectedHist.enabled,
            max_commits: selectedHist.maxCommits,
            max_days: selectedHist.maxDays,
          },
        }),
      privateRepo
    )
  }

  const handleZipSubmit = (e) => {
    e.preventDefault()
    if (!zipFile) {
      setError('Select a .zip archive first.')
      return
    }
    const fd = new FormData()
    fd.append('file', zipFile)
    fd.append('goal', goal)
    fd.append('history_enabled', String(selectedHist.enabled))
    fd.append('history_max_commits', String(selectedHist.maxCommits))
    fd.append('history_max_days', String(selectedHist.maxDays))
    startAudit(() => api.createAuditZip(fd), zipFile.name)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer?.files?.[0]
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.zip')) {
      setError(ERROR_CODE_MESSAGES.invalid_archive)
      return
    }
    if (file.size > 200 * 1024 * 1024) {
      setError(ERROR_CODE_MESSAGES.repo_too_large)
      return
    }
    setZipFile(file)
    setError(null)
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto font-sans">
      <div>
        <div className="inline-flex items-center gap-2 rounded border border-laser-lime/40 bg-laser-lime/10 px-2.5 py-0.5 text-xs font-semibold text-laser-lime font-mono">
          <span className="h-1.5 w-1.5 rounded-full bg-laser-lime" aria-hidden="true" />
          Static Source &amp; Git History Intake
        </div>
        <h1 className="mt-2.5 text-2xl sm:text-3xl font-serif font-normal tracking-tight text-slate-100">
          Target Codebase Ingestion
        </h1>
        <p className="mt-1 text-xs text-slate-400 leading-relaxed max-w-2xl">
          Inspect public repositories, scoped private repositories, or uploaded ZIP archives via static AST analysis
          and bounded dulwich git-object reads. No repository scripts or package hooks are executed.
        </p>
      </div>

      {/* Quick Presets + Process History Control */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-xl border border-[#2A2E35] bg-[#15171B] p-4 space-y-2">
          <span className="text-xs font-bold uppercase tracking-wider font-mono text-slate-400 block">
            QUICK INGEST PRESETS
          </span>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => {
                setActiveTab('public')
                setPublicUrl('https://github.com/charmi-reddy/Dependency-Detective')
                setPublicRef('main')
              }}
              className="rounded-lg border border-[#2A2E35] bg-[#0A0B0D] px-3 py-1.5 text-xs font-mono text-slate-300 hover:border-laser-lime/60 hover:text-slate-100 transition"
            >
              charmi-reddy/Dependency-Detective
            </button>
            <button
              type="button"
              onClick={() => {
                setActiveTab('public')
                setPublicUrl('https://github.com/jbhavya876/alt_sentinal')
                setPublicRef('main')
              }}
              className="rounded-lg border border-laser-lime/40 bg-laser-lime/10 px-3 py-1.5 text-xs font-mono text-laser-lime hover:bg-laser-lime hover:text-black transition"
            >
              jbhavya876/alt_sentinal
            </button>
          </div>
        </div>

        {/* Process History Scope Control */}
        <div className="rounded-xl border border-[#2A2E35] bg-[#15171B] p-4 space-y-2">
          <div className="flex items-center justify-between">
            <label htmlFor="history-window-select" className="text-xs font-bold uppercase tracking-wider font-mono text-slate-300 flex items-center gap-1.5">
              <History className="w-3.5 h-3.5 text-laser-lime" aria-hidden="true" />
              <span>Process History Window</span>
            </label>
            <select
              id="goal-select"
              aria-label="Target Readiness Goal"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              className="rounded border border-[#2A2E35] bg-[#0A0B0D] px-2 py-1 text-[11px] font-mono text-slate-200 focus:border-laser-lime focus:outline-none"
            >
              <option value="production">Goal: Production</option>
              <option value="mvp">Goal: MVP</option>
            </select>
          </div>
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Process history option">
            {HISTORY_PRESETS.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setHistoryPreset(p.id)}
                aria-pressed={historyPreset === p.id}
                className={`rounded px-2.5 py-1 text-[11px] font-mono transition border ${
                  historyPreset === p.id
                    ? 'border-laser-lime bg-laser-lime text-black font-bold'
                    : 'border-[#2A2E35] bg-[#0A0B0D] text-slate-300 hover:text-white'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
          <p className="text-[11px] text-slate-400">
            History is read from a temporary copy and discarded. No commit messages, names, or emails are kept.
          </p>
        </div>
      </div>

      {/* Intake Source Tabs */}
      <div className="flex border-b border-[#2A2E35] font-mono text-xs overflow-x-auto whitespace-nowrap" role="tablist">
        <button
          role="tab"
          aria-selected={activeTab === 'public'}
          onClick={() => { setActiveTab('public'); setError(null) }}
          className={`px-4 py-2.5 font-bold uppercase tracking-wider border-b-2 transition flex items-center gap-2 ${
            activeTab === 'public'
              ? 'border-laser-lime text-laser-lime bg-[#15171B]'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Globe className="w-3.5 h-3.5" aria-hidden="true" />
          <span>Public GitHub Repo</span>
        </button>

        <button
          role="tab"
          aria-selected={activeTab === 'zip'}
          onClick={() => { setActiveTab('zip'); setError(null) }}
          className={`px-4 py-2.5 font-bold uppercase tracking-wider border-b-2 transition flex items-center gap-2 ${
            activeTab === 'zip'
              ? 'border-laser-lime text-laser-lime bg-[#15171B]'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <UploadCloud className="w-3.5 h-3.5" aria-hidden="true" />
          <span>ZIP Archive Upload</span>
        </button>

        <button
          role="tab"
          aria-selected={activeTab === 'private'}
          onClick={() => { setActiveTab('private'); setError(null) }}
          className={`px-4 py-2.5 font-bold uppercase tracking-wider border-b-2 transition flex items-center gap-2 ${
            activeTab === 'private'
              ? 'border-laser-lime text-laser-lime bg-[#15171B]'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Lock className="w-3.5 h-3.5" aria-hidden="true" />
          <span>Private Repo (GitHub App)</span>
        </button>
      </div>

      {/* Forms & Live Pipeline */}
      <div className="rounded-xl border border-[#2A2E35] bg-[#15171B] p-5">
        {activeTab === 'public' && (
          <form onSubmit={handlePublicSubmit} className="space-y-4 font-mono text-xs">
            <div>
              <label htmlFor="public-url-input" className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                Public GitHub Repository URL or Slug
              </label>
              <input
                id="public-url-input"
                type="text"
                value={publicUrl}
                onChange={(e) => setPublicUrl(e.target.value)}
                placeholder="https://github.com/owner/repository"
                required
                className="w-full rounded-lg border border-[#2A2E35] bg-[#0A0B0D] px-3.5 py-2.5 text-xs text-slate-100 placeholder-slate-500 focus:border-laser-lime focus:outline-none"
              />
            </div>

            <div>
              <label htmlFor="public-ref-input" className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                Branch / Git Reference
              </label>
              <input
                id="public-ref-input"
                type="text"
                value={publicRef}
                onChange={(e) => setPublicRef(e.target.value)}
                placeholder="main"
                className="w-full rounded-lg border border-[#2A2E35] bg-[#0A0B0D] px-3.5 py-2.5 text-xs text-slate-100 placeholder-slate-500 focus:border-laser-lime focus:outline-none"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="rounded-lg border border-laser-lime bg-laser-lime px-5 py-2.5 text-xs font-bold uppercase tracking-wider text-black hover:shadow-laser-glow disabled:opacity-50 transition"
            >
              {loading ? 'Running Audit...' : 'Start Audit'}
            </button>
          </form>
        )}

        {activeTab === 'zip' && (
          <form onSubmit={handleZipSubmit} className="space-y-4">
            <div className="rounded-lg border border-emerald-900/60 bg-emerald-950/20 p-3.5 text-xs text-emerald-200 space-y-1">
              <div className="font-bold font-mono uppercase tracking-wider flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-emerald-400" aria-hidden="true" />
                <span>Zip-Slip &amp; Immediate Source Purge</span>
              </div>
              <p className="text-[11px] leading-relaxed text-slate-300 font-sans">
                Archives are checked for path traversal, symlinks, and decompression limits (&gt;200MB / 5,000 files), then purged when the audit completes.
                History is assessed only if the archive contains a <code>.git</code> directory; if not, the result will say &ldquo;Process integrity: not assessed.&rdquo;
              </p>
            </div>

            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={(e) => { e.preventDefault(); setDragOver(false) }}
              onDrop={handleDrop}
              className={`rounded-xl border-2 border-dashed p-8 text-center transition-all ${
                dragOver ? 'border-laser-lime bg-laser-lime/10' : 'border-[#2A2E35] bg-[#0A0B0D]'
              }`}
            >
              <UploadCloud className="w-8 h-8 mx-auto mb-2 text-laser-lime/80" aria-hidden="true" />
              <div className="text-xs font-mono font-bold text-slate-200 uppercase tracking-wider">
                {zipFile ? `Selected: ${zipFile.name} (${(zipFile.size / (1024 * 1024)).toFixed(2)} MB)` : 'Select or Drop .ZIP Archive'}
              </div>
              <input
                type="file"
                accept=".zip"
                aria-label="Upload ZIP archive"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (!f) return
                  if (f.size > 200 * 1024 * 1024) {
                    setError(ERROR_CODE_MESSAGES.repo_too_large)
                    return
                  }
                  setZipFile(f)
                  setError(null)
                }}
                className="mt-3 block mx-auto text-xs text-slate-400 file:mr-4 file:rounded file:border file:border-[#2A2E35] file:bg-[#15171B] file:px-3 file:py-1.5 file:text-xs file:font-mono file:font-bold file:text-slate-200 cursor-pointer font-mono"
              />
            </div>

            <button
              type="submit"
              disabled={loading || !zipFile}
              className="rounded-lg border border-laser-lime bg-laser-lime px-5 py-2.5 text-xs font-bold font-mono uppercase tracking-wider text-black hover:shadow-laser-glow disabled:opacity-50 transition"
            >
              {loading ? 'Running Audit...' : 'Upload & Audit ZIP'}
            </button>
          </form>
        )}

        {activeTab === 'private' && (
          <form onSubmit={handlePrivateSubmit} className="space-y-4 font-mono text-xs">
            <div>
              <label htmlFor="private-repo-input" className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                Repository Slug (owner/repo)
              </label>
              <input
                id="private-repo-input"
                type="text"
                value={privateRepo}
                onChange={(e) => setPrivateRepo(e.target.value)}
                placeholder="acme-corp/private-service"
                required
                className="w-full rounded-lg border border-[#2A2E35] bg-[#0A0B0D] px-3.5 py-2.5 text-xs text-slate-100 placeholder-slate-500 focus:border-laser-lime focus:outline-none"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label htmlFor="private-token-input" className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                  Scoped Read-Only Token
                </label>
                <input
                  id="private-token-input"
                  type="password"
                  value={privateToken}
                  onChange={(e) => setPrivateToken(e.target.value)}
                  placeholder="ghs_..."
                  required
                  className="w-full rounded-lg border border-[#2A2E35] bg-[#0A0B0D] px-3.5 py-2.5 text-xs text-slate-100 focus:border-laser-lime focus:outline-none"
                />
              </div>
              <div>
                <label htmlFor="private-branch-input" className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                  Branch (optional)
                </label>
                <input
                  id="private-branch-input"
                  type="text"
                  value={privateBranch}
                  onChange={(e) => setPrivateBranch(e.target.value)}
                  placeholder="main"
                  className="w-full rounded-lg border border-[#2A2E35] bg-[#0A0B0D] px-3.5 py-2.5 text-xs text-slate-100 focus:border-laser-lime focus:outline-none"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="rounded-lg border border-laser-lime bg-laser-lime px-5 py-2.5 text-xs font-bold uppercase tracking-wider text-black hover:shadow-laser-glow disabled:opacity-50 transition"
            >
              {loading ? 'Running Audit...' : 'Clone & Audit Private Repo'}
            </button>
          </form>
        )}

        {/* Real Event-Driven Scan Sequence */}
        {loading && (
          <div className="mt-6 rounded-xl border border-laser-lime/40 bg-[#0A0B0D] p-5 space-y-4 font-mono" role="status" aria-live="polite">
            <div className="flex items-center justify-between border-b border-[#2A2E35] pb-3">
              <div className="flex items-center gap-2 text-xs font-bold text-laser-lime">
                <span className="h-2 w-2 rounded-full bg-laser-lime animate-pulse" aria-hidden="true" />
                <span>AUDIT PIPELINE RUNNING</span>
              </div>
              <span className="text-[10px] text-slate-400 uppercase tracking-widest font-bold">
                STAGE {currentStep} OF {PIPELINE_STEPS.length}
              </span>
            </div>

            <div className="space-y-2.5">
              {PIPELINE_STEPS.map((step) => {
                const isCurrent = step.id === currentStep
                const isDone = step.id < currentStep
                return (
                  <div key={step.id} className="flex items-start gap-3 text-xs">
                    <div className="mt-0.5 shrink-0">
                      {isDone && (
                        <span className="flex h-4 w-4 items-center justify-center rounded bg-emerald-950/60 border border-emerald-800 text-[#5DE6A8] text-[9px] font-bold">
                          ✓
                        </span>
                      )}
                      {isCurrent && (
                        <div className="h-4 w-4 rounded-full border-2 border-laser-lime border-t-transparent animate-spin" />
                      )}
                      {!isDone && !isCurrent && (
                        <span className="flex h-4 w-4 items-center justify-center rounded bg-[#15171B] border border-[#2A2E35] text-slate-400 text-[9px]">
                          {step.id}
                        </span>
                      )}
                    </div>
                    <div>
                      <div className={`font-semibold ${isCurrent ? 'text-laser-lime' : isDone ? 'text-slate-200' : 'text-slate-400'}`}>
                        {step.title}
                      </div>
                      <div className="text-slate-400 text-[10px] font-sans">{step.desc}</div>
                    </div>
                  </div>
                )
              })}
            </div>

            <div className="mt-4 border-t border-[#2A2E35] pt-3">
              <div className="flex items-center gap-2 text-[10px] text-slate-400 mb-2 uppercase tracking-wider font-bold">
                <Terminal className="w-3 h-3 text-laser-lime" aria-hidden="true" />
                <span>Verified Stage Events</span>
              </div>
              <div className="h-28 overflow-y-auto rounded bg-[#050608] border border-[#2A2E35] p-2.5 text-[11px] font-mono text-slate-300 space-y-1">
                {terminalLogs.map((entry, idx) => (
                  <div key={idx} className="leading-tight">
                    <span className="text-slate-400 mr-1.5">&gt;</span>
                    {entry}
                  </div>
                ))}
                <div ref={terminalEndRef} />
              </div>
            </div>
          </div>
        )}

        {error && (
          <div role="alert" className="mt-5 rounded-lg border border-[#5A1C16] bg-[#2A0E0B] p-3.5 text-xs text-[#FF4A2B] font-mono">
            <strong>AUDIT ERROR:</strong> {error}
          </div>
        )}

        {result && (
          <div className="mt-5 rounded-xl border border-emerald-900/60 bg-emerald-950/20 p-5 space-y-3 font-mono">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="text-[#5DE6A8] font-bold text-xs flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-[#5DE6A8]" aria-hidden="true" />
                <span>AUDIT COMPLETE</span>
              </div>
              <span className="text-[10px] text-slate-400">
                TARGET: {result.target} · ID: {result.audit_id}
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs pt-1">
              <div className="rounded border border-[#2A2E35] bg-[#0A0B0D] p-2">
                <span className="text-[10px] text-slate-400 uppercase block">Files Scanned</span>
                <span className="font-bold text-slate-200 tabular-nums">
                  {result.statusObj?.coverage?.files_scanned ?? 0} / {result.statusObj?.coverage?.files_total ?? 0}
                </span>
              </div>
              <div className="rounded border border-[#2A2E35] bg-[#0A0B0D] p-2">
                <span className="text-[10px] text-slate-400 uppercase block">History</span>
                <span className="font-bold text-slate-200">
                  {result.statusObj?.coverage?.history?.assessed
                    ? `${result.statusObj.coverage.history.commits_analyzed} commits`
                    : 'Not assessed'}
                </span>
              </div>
              <div className="rounded border border-[#2A2E35] bg-[#0A0B0D] p-2">
                <span className="text-[10px] text-slate-400 uppercase block">Rubric Phase</span>
                <span className="font-bold text-[#FFB020]">{result.statusObj?.scorecard?.phase || 'Prototype'}</span>
              </div>
              <div className="rounded border border-[#2A2E35] bg-[#0A0B0D] p-2">
                <span className="text-[10px] text-slate-400 uppercase block">Score (v2.0.0)</span>
                <span className="font-bold text-emerald-400 tabular-nums">
                  {result.statusObj?.scorecard?.overall ?? result.statusObj?.scorecard?.overall_score ?? 0} / 100
                </span>
              </div>
            </div>

            <div className="pt-2 flex justify-end">
              <button
                type="button"
                onClick={() => navigate(href.auditTab('overview', result.audit_id))}
                className="rounded-lg border border-laser-lime bg-laser-lime px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider text-black transition hover:shadow-laser-glow flex items-center gap-1.5"
              >
                <span>Open Audit Cockpit</span>
                <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
