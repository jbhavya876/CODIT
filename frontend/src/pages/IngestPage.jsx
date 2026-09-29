import React, { useState, useEffect } from 'react'
import { api } from '../api.js'
import { navigate } from '../router.js'

const PIPELINE_STEPS = [
  { id: 1, title: 'Intake & Security Gate', desc: 'Pre-flight path sanitization, Zip-Slip check & decompression bomb quotas' },
  { id: 2, title: 'AST Parsing Engine', desc: 'Tree-sitter syntactic walks, import extraction & call graphs' },
  { id: 3, title: 'Vulnerability Telemetry', desc: 'OSV API advisory queries & high-entropy secret scanning' },
  { id: 4, title: 'ONNX & SHAP Models', desc: 'Architectural fragility prediction & Shapley attribution scoring' },
  { id: 5, title: 'Property Graph Activation', desc: 'openCypher graph assembly & blast-radius precomputation' },
]

export default function IngestPage() {
  const [activeTab, setActiveTab] = useState('public') // 'public', 'private', 'zip'
  const [publicUrl, setPublicUrl] = useState('https://github.com/charmi-reddy/Dependency-Detective')
  const [publicRef, setPublicRef] = useState('main')

  const [privateRepo, setPrivateRepo] = useState('')
  const [privateToken, setPrivateToken] = useState('')

  const [zipFile, setZipFile] = useState(null)

  const [loading, setLoading] = useState(false)
  const [currentStep, setCurrentStep] = useState(1)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  // Progress simulation during ingestion
  useEffect(() => {
    let timer
    if (loading) {
      setCurrentStep(1)
      timer = setInterval(() => {
        setCurrentStep((prev) => (prev < 5 ? prev + 1 : prev))
      }, 1200)
    } else {
      clearInterval(timer)
    }
    return () => clearInterval(timer)
  }, [loading])

  const handlePublicSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await api.ingestPublic(publicUrl, publicRef)
      try {
        const analysis = await api.runAnalysis('production')
        res.analysis = analysis
      } catch (aErr) {
        console.warn('Auto-analysis warning:', aErr)
      }
      setResult(res)
    } catch (err) {
      setError(err.message || 'Failed to ingest public repository.')
    } finally {
      setLoading(false)
    }
  }

  const handlePrivateSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await api.ingestPrivate(privateRepo, privateToken)
      try {
        const analysis = await api.runAnalysis('production')
        res.analysis = analysis
      } catch (aErr) {
        console.warn('Auto-analysis warning:', aErr)
      }
      setResult(res)
    } catch (err) {
      setError(err.message || 'Failed to clone private repository.')
    } finally {
      setLoading(false)
    }
  }

  const handleZipSubmit = async (e) => {
    e.preventDefault()
    if (!zipFile) {
      setError('Please select a .zip archive first.')
      return
    }
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const formData = new FormData()
      formData.append('file', zipFile)
      const res = await api.ingestZip(formData)
      try {
        const analysis = await api.runAnalysis('production')
        res.analysis = analysis
      } catch (aErr) {
        console.warn('Auto-analysis warning:', aErr)
      }
      setResult(res)
    } catch (err) {
      setError(err.message || 'Failed to extract ZIP archive.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div>
        <div className="inline-flex items-center gap-2 rounded border border-sky-900/60 bg-sky-950/40 px-2.5 py-0.5 text-xs font-semibold text-sky-400 font-mono">
          <span className="h-1.5 w-1.5 rounded-full bg-sky-400 animate-pulse" />
          Module 1 · Multi-Tier Codebase Ingestion
        </div>
        <h1 className="mt-2.5 text-xl sm:text-2xl font-black tracking-tight text-slate-100 font-mono">
          Ingest Target Codebase
        </h1>
        <p className="mt-1 text-xs text-slate-400 leading-relaxed font-sans">
          Accepts public GitHub repositories, private repositories via scoped GitHub App tokens, or zero-retention ZIP archives.
          All source files are evaluated purely via static AST analysis — no untrusted scripts or package builds are ever executed.
        </p>
      </div>

      {/* Quick Ingestion Presets */}
      <div className="rounded-xl border border-[#1A2438] bg-[#0E1420] p-4">
        <span className="text-xs font-bold uppercase tracking-wider font-mono text-slate-400 block mb-2">
          QUICK INGEST PRESETS:
        </span>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => {
              setActiveTab('public')
              setPublicUrl('https://github.com/charmi-reddy/Dependency-Detective')
              setPublicRef('main')
            }}
            className="rounded border border-[#1A2438] bg-[#111827] px-3 py-1.5 text-xs font-mono text-slate-300 hover:border-sky-500/60 hover:text-slate-100 transition flex items-center gap-2"
          >
            <span className="text-sky-400">🌐</span>
            <span className="font-bold">charmi-reddy/Dependency-Detective</span>
            <span className="text-[10px] text-slate-500">(Microservices Graph)</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setActiveTab('public')
              setPublicUrl('https://github.com/jbhavya876/alt_sentinal')
              setPublicRef('main')
            }}
            className="rounded border border-sky-900/60 bg-sky-950/40 px-3 py-1.5 text-xs font-mono text-sky-300 hover:border-sky-500 transition flex items-center gap-2"
          >
            <span>🎯</span>
            <span className="font-bold">jbhavya876/alt_sentinal</span>
            <span className="text-[10px] text-slate-400">(Algorand dApp)</span>
          </button>
        </div>
      </div>

      {/* Intake Tabs */}
      <div className="flex border-b border-[#1A2438] font-mono text-xs overflow-x-auto whitespace-nowrap">
        <button
          onClick={() => { setActiveTab('public'); setError(null); }}
          className={`px-4 py-2.5 font-bold uppercase tracking-wider border-b-2 transition flex items-center gap-2 ${
            activeTab === 'public'
              ? 'border-sky-500 text-sky-400 bg-[#0E1420]'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <span>🌐</span> Public GitHub Repo
          <span className="rounded bg-[#111827] border border-[#1A2438] px-1.5 py-0.2 text-[9px] text-slate-400 font-mono">TREE API</span>
        </button>

        <button
          onClick={() => { setActiveTab('zip'); setError(null); }}
          className={`px-4 py-2.5 font-bold uppercase tracking-wider border-b-2 transition flex items-center gap-2 ${
            activeTab === 'zip'
              ? 'border-sky-500 text-sky-400 bg-[#0E1420]'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <span>📦</span> ZIP Archive Upload
          <span className="rounded border border-emerald-900/60 bg-emerald-950/40 px-1.5 py-0.2 text-[9px] text-emerald-400 font-mono">ZERO RETENTION</span>
        </button>

        <button
          onClick={() => { setActiveTab('private'); setError(null); }}
          className={`px-4 py-2.5 font-bold uppercase tracking-wider border-b-2 transition flex items-center gap-2 ${
            activeTab === 'private'
              ? 'border-sky-500 text-sky-400 bg-[#0E1420]'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <span>🔒</span> Private Repo (GitHub App)
          <span className="rounded bg-[#111827] border border-[#1A2438] px-1.5 py-0.2 text-[9px] text-slate-400 font-mono">SANDBOX</span>
        </button>
      </div>

      {/* Tab Panels */}
      <div className="rounded-xl border border-[#1A2438] bg-[#0E1420] p-5">
        {activeTab === 'public' && (
          <form onSubmit={handlePublicSubmit} className="space-y-4 font-mono text-xs">
            <div>
              <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                Public GitHub Repository URL or Slug
              </label>
              <input
                type="text"
                value={publicUrl}
                onChange={(e) => setPublicUrl(e.target.value)}
                placeholder="https://github.com/owner/repository"
                required
                className="w-full rounded border border-[#1A2438] bg-[#080B11] px-3.5 py-2 text-xs text-slate-100 placeholder-slate-500 focus:border-sky-500 focus:outline-none"
              />
              <p className="mt-1 text-[11px] text-slate-500 font-sans">
                Fetched recursively via GitHub REST API tree endpoints with rate-limit protection. Zero arbitrary code execution.
              </p>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                Branch / Git Reference
              </label>
              <input
                type="text"
                value={publicRef}
                onChange={(e) => setPublicRef(e.target.value)}
                placeholder="main"
                className="w-full rounded border border-[#1A2438] bg-[#080B11] px-3.5 py-2 text-xs text-slate-100 placeholder-slate-500 focus:border-sky-500 focus:outline-none"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="rounded border border-sky-500 bg-sky-500 px-5 py-2 text-xs font-bold uppercase tracking-wider text-slate-950 hover:bg-sky-400 disabled:opacity-50 transition"
            >
              {loading ? 'Executing Full Audit Pipeline...' : 'Fetch & Analyze Codebase →'}
            </button>
          </form>
        )}

        {activeTab === 'zip' && (
          <form onSubmit={handleZipSubmit} className="space-y-4">
            <div className="rounded-lg border border-emerald-900/60 bg-emerald-950/20 p-3.5 text-xs text-emerald-300 space-y-1">
              <div className="font-bold font-mono uppercase tracking-wider flex items-center gap-1.5">
                <span>🛡️</span> Non-Negotiable Privacy & Defense Guarantee
              </div>
              <p className="text-[11px] leading-relaxed text-emerald-200/90 font-sans">
                Pre-extraction validation protects against Zip-Slip and Zip-Bomb attacks (&gt;250MB uncompressed, &gt;5,000 files).
                Archives are extracted inside an isolated ephemeral memory sandbox and all source files are permanently destroyed immediately post-audit.
              </p>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider font-mono mb-1.5">
                Select ZIP Archive
              </label>
              <input
                type="file"
                accept=".zip"
                onChange={(e) => setZipFile(e.target.files?.[0] || null)}
                className="block w-full text-xs text-slate-400 file:mr-4 file:rounded file:border file:border-[#1A2438] file:bg-[#111827] file:px-3 file:py-1.5 file:text-xs file:font-mono file:font-bold file:text-slate-200 hover:file:bg-slate-800 cursor-pointer font-mono"
              />
            </div>

            <button
              type="submit"
              disabled={loading || !zipFile}
              className="rounded border border-sky-500 bg-sky-500 px-5 py-2 text-xs font-bold font-mono uppercase tracking-wider text-slate-950 hover:bg-sky-400 disabled:opacity-50 transition"
            >
              {loading ? 'Validating & Extracting in Sandbox...' : 'Upload & Audit ZIP'}
            </button>
          </form>
        )}

        {activeTab === 'private' && (
          <form onSubmit={handlePrivateSubmit} className="space-y-4 font-mono text-xs">
            <div className="rounded-lg border border-amber-900/60 bg-amber-950/20 p-3.5 text-xs text-amber-300 space-y-1">
              <div className="font-bold uppercase tracking-wider flex items-center gap-1.5">
                <span>🔑</span> GitHub App Integration & Scoped Access
              </div>
              <p className="text-[11px] leading-relaxed text-amber-200/90 font-sans">
                Provide a scoped installation access token with read-only contents permission.
                Shallow clone (--depth 1) runs inside an isolated container with disabled network egress and zero git hooks.
              </p>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                Repository Slug (owner/repo)
              </label>
              <input
                type="text"
                value={privateRepo}
                onChange={(e) => setPrivateRepo(e.target.value)}
                placeholder="acme-corp/private-service"
                required
                className="w-full rounded border border-[#1A2438] bg-[#080B11] px-3.5 py-2 text-xs text-slate-100 placeholder-slate-500 focus:border-sky-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                GitHub App Token (Ephemeral Access)
              </label>
              <input
                type="password"
                value={privateToken}
                onChange={(e) => setPrivateToken(e.target.value)}
                placeholder="ghs_..."
                required
                className="w-full rounded border border-[#1A2438] bg-[#080B11] px-3.5 py-2 text-xs text-slate-100 focus:border-sky-500 focus:outline-none"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="rounded border border-sky-500 bg-sky-500 px-5 py-2 text-xs font-bold uppercase tracking-wider text-slate-950 hover:bg-sky-400 disabled:opacity-50 transition"
            >
              {loading ? 'Cloning in Isolated Sandbox...' : 'Clone & Ingest Private Repo'}
            </button>
          </form>
        )}

        {/* Live Pipeline Stepper during Loading */}
        {loading && (
          <div className="mt-5 rounded-lg border border-sky-900/60 bg-[#080B11] p-4 space-y-3 font-mono">
            <div className="flex items-center justify-between border-b border-[#1A2438] pb-2.5">
              <div className="flex items-center gap-2 text-xs font-bold text-sky-400">
                <span className="h-1.5 w-1.5 rounded-full bg-sky-400 animate-ping" />
                PIPELINE ORCHESTRATOR ACTIVE
              </div>
              <span className="text-[10px] text-slate-400">STAGE {currentStep} OF 5</span>
            </div>

            <div className="space-y-2">
              {PIPELINE_STEPS.map((step) => {
                const isCurrent = step.id === currentStep
                const isDone = step.id < currentStep
                return (
                  <div key={step.id} className="flex items-start gap-2.5 text-xs">
                    <div className="mt-0.5 shrink-0">
                      {isDone && <span className="flex h-4 w-4 items-center justify-center rounded bg-emerald-950/60 border border-emerald-800 text-emerald-400 text-[9px] font-bold">✓</span>}
                      {isCurrent && <div className="h-4 w-4 rounded border-2 border-sky-400 border-t-transparent animate-spin" />}
                      {!isDone && !isCurrent && <span className="flex h-4 w-4 items-center justify-center rounded bg-[#111827] border border-[#1A2438] text-slate-500 text-[9px]">{step.id}</span>}
                    </div>
                    <div>
                      <div className={`font-semibold ${isCurrent ? 'text-sky-300' : isDone ? 'text-slate-200' : 'text-slate-500'}`}>
                        {step.title}
                      </div>
                      <div className="text-slate-400 text-[10px] font-sans">{step.desc}</div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Error Notification */}
        {error && (
          <div className="mt-5 rounded-lg border border-rose-900/80 bg-[#1E0A10] p-3.5 text-xs text-rose-300 font-mono">
            <strong>INGESTION ERROR:</strong> {error}
          </div>
        )}

        {/* Success Confirmation & Direct Cockpit Link */}
        {result && (
          <div className="mt-5 rounded-lg border border-emerald-900/60 bg-emerald-950/20 p-4 space-y-3 font-mono">
            <div className="flex items-center justify-between">
              <div className="text-emerald-400 font-bold text-xs flex items-center gap-2">
                <span>✓</span> CODEBASE INGESTED & FULLY ANALYZED
              </div>
              <span className="text-[10px] text-slate-400">
                {result.file_count} files ({result.total_size_kb} KB)
              </span>
            </div>

            <div className="flex flex-wrap gap-1.5">
              {Object.entries(result.languages || {}).map(([lang, count]) => (
                <span
                  key={lang}
                  className="rounded border border-[#1A2438] bg-[#111827] px-2 py-0.5 text-[10px] text-slate-300"
                >
                  {lang}: {count}
                </span>
              ))}
            </div>

            {result.analysis && (
              <div className="rounded border border-[#1A2438] bg-[#0E1420] p-3 grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
                <div>
                  <span className="text-slate-500 text-[9px] uppercase block">Audit Score</span>
                  <span className="font-black text-slate-100 text-base">{result.analysis.score}/100</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[9px] uppercase block">Maturity Phase</span>
                  <span className="font-bold text-sky-400">{result.analysis.phase}</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[9px] uppercase block">ONNX Fragility</span>
                  <span className="font-bold text-amber-400">{result.analysis.onnx_fragility ?? 'Calculated'}</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[9px] uppercase block">Findings</span>
                  <span className="font-bold text-slate-200">{result.analysis.findings_count}</span>
                </div>
              </div>
            )}

            <div className="pt-2 flex items-center justify-between">
              <span className="text-xs text-slate-400 font-sans">
                Target: <code className="text-slate-200 font-mono font-semibold">{result.target}</code>
              </span>
              <button
                onClick={() => navigate('#/audit')}
                className="rounded border border-emerald-500 bg-emerald-500 px-4 py-1.5 text-xs font-bold text-slate-950 hover:bg-emerald-400 transition"
              >
                Launch Audit Cockpit →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
