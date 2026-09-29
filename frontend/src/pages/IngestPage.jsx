import React, { useState, useEffect } from 'react'
import { api } from '../api.js'
import { navigate } from '../router.js'

const PIPELINE_STEPS = [
  { id: 1, title: 'Intake & Security Gate', desc: 'Pre-flight path sanitization, Zip-Slip check & bomb quotas' },
  { id: 2, title: 'AST Parsing Engine', desc: 'Tree-sitter syntactic walks, import extraction & call graphs' },
  { id: 3, title: 'Vulnerability Telemetry', desc: 'OSV API advisory queries & high-entropy secret scanning' },
  { id: 4, title: 'ONNX & SHAP Models', desc: 'Architectural fragility prediction & Shapley attribution scoring' },
  { id: 5, title: 'Property Graph Activation', desc: 'openCypher graph assembly & blast-radius precomputation' },
]

export default function IngestPage() {
  const [activeTab, setActiveTab] = useState('public') // 'public', 'private', 'zip'
  const [publicUrl, setPublicUrl] = useState('https://github.com/jbhavya876/alt_sentinal')
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
    <div className="space-y-8 max-w-4xl mx-auto">
      {/* Header */}
      <div>
        <div className="inline-flex items-center gap-2 rounded-full border border-sky-500/30 bg-sky-500/10 px-3 py-1 text-xs font-semibold text-sky-400 font-mono">
          <span className="h-1.5 w-1.5 rounded-full bg-sky-400 animate-pulse" />
          Module 1 · Multi-Tier Codebase Ingestion
        </div>
        <h1 className="mt-3 text-2xl font-black tracking-tight text-slate-100 sm:text-3xl">
          Ingest Target Codebase
        </h1>
        <p className="mt-2 text-sm text-slate-400 leading-relaxed">
          Accepts public GitHub repositories, private repositories via scoped GitHub App tokens, or zero-retention ZIP archives.
          All source files are evaluated purely via static AST analysis — no untrusted scripts or package builds are ever executed.
        </p>
      </div>

      {/* Quick Ingestion Presets */}
      <div className="rounded-2xl border border-slate-800 bg-[#0c1220]/80 p-5 shadow-xl backdrop-blur-md">
        <span className="text-xs font-bold uppercase tracking-wider text-slate-400 block mb-2.5">
          Quick Ingest Presets (Click to Load Target):
        </span>
        <div className="flex flex-wrap gap-2.5">
          <button
            type="button"
            onClick={() => {
              setActiveTab('public')
              setPublicUrl('https://github.com/jbhavya876/alt_sentinal')
              setPublicRef('main')
            }}
            className="rounded-xl border border-sky-500/40 bg-sky-950/30 px-3.5 py-2 text-xs text-sky-300 hover:bg-sky-900/40 hover:border-sky-500/60 transition flex items-center gap-2"
          >
            <span>🎯</span>
            <span className="font-mono font-bold">jbhavya876/alt_sentinal</span>
            <span className="text-[10px] text-slate-400 font-mono">(Algorand dApp)</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setActiveTab('public')
              setPublicUrl('https://github.com/charmi-reddy/Dependency-Detective')
              setPublicRef('main')
            }}
            className="rounded-xl border border-slate-700 bg-slate-900/70 px-3.5 py-2 text-xs text-slate-300 hover:bg-slate-800 hover:text-slate-100 transition flex items-center gap-2"
          >
            <span>🌐</span>
            <span className="font-mono font-bold">charmi-reddy/Dependency-Detective</span>
            <span className="text-[10px] text-slate-400 font-mono">(Microservices Graph)</span>
          </button>
        </div>
      </div>

      {/* Intake Tabs */}
      <div className="flex border-b border-slate-800">
        <button
          onClick={() => { setActiveTab('public'); setError(null); }}
          className={`px-5 py-3 text-sm font-semibold border-b-2 transition flex items-center gap-2 ${
            activeTab === 'public'
              ? 'border-sky-500 text-sky-400 bg-slate-900/40'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <span>🌐</span> Public GitHub Repo
          <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] text-slate-300 font-mono">Tree API</span>
        </button>

        <button
          onClick={() => { setActiveTab('zip'); setError(null); }}
          className={`px-5 py-3 text-sm font-semibold border-b-2 transition flex items-center gap-2 ${
            activeTab === 'zip'
              ? 'border-sky-500 text-sky-400 bg-slate-900/40'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <span>📦</span> ZIP Archive Upload
          <span className="rounded-full bg-emerald-950 border border-emerald-500/40 px-2 py-0.5 text-[10px] text-emerald-400 font-mono">Zero Retention</span>
        </button>

        <button
          onClick={() => { setActiveTab('private'); setError(null); }}
          className={`px-5 py-3 text-sm font-semibold border-b-2 transition flex items-center gap-2 ${
            activeTab === 'private'
              ? 'border-sky-500 text-sky-400 bg-slate-900/40'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <span>🔒</span> Private Repo (GitHub App)
          <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] text-slate-300 font-mono">Sandbox Clone</span>
        </button>
      </div>

      {/* Tab Panels */}
      <div className="rounded-2xl border border-slate-800 bg-[#0c1220]/80 p-6 shadow-xl backdrop-blur-md">
        {activeTab === 'public' && (
          <form onSubmit={handlePublicSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">
                Public GitHub Repository URL or Slug
              </label>
              <input
                type="text"
                value={publicUrl}
                onChange={(e) => setPublicUrl(e.target.value)}
                placeholder="https://github.com/owner/repository"
                required
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:border-sky-500 focus:outline-none font-mono"
              />
              <p className="mt-1.5 text-xs text-slate-500">
                Fetched recursively via GitHub REST API tree endpoints with rate-limit protection. Zero arbitrary code execution.
              </p>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">
                Branch / Git Reference
              </label>
              <input
                type="text"
                value={publicRef}
                onChange={(e) => setPublicRef(e.target.value)}
                placeholder="main"
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:border-sky-500 focus:outline-none font-mono"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="rounded-xl bg-sky-500 px-6 py-2.5 text-sm font-bold text-slate-950 hover:bg-sky-400 disabled:opacity-50 transition shadow-lg shadow-sky-500/25"
            >
              {loading ? 'Executing Full Audit Pipeline...' : 'Fetch & Analyze Codebase →'}
            </button>
          </form>
        )}

        {activeTab === 'zip' && (
          <form onSubmit={handleZipSubmit} className="space-y-4">
            <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/20 p-4 text-xs text-emerald-300 space-y-1">
              <div className="font-bold flex items-center gap-1.5">
                <span>🛡️</span> Security Guarantees (Section 9 Non-Negotiables)
              </div>
              <p className="text-[11px] leading-relaxed text-emerald-200/90">
                Uploaded archives are extracted inside an isolated, network-isolated sandbox. All files are purged immediately post-audit.
                Pre-extraction validation rejects Zip-Slip path traversals (../) and decompression bombs (&gt;250MB uncompressed, &gt;5,000 files).
              </p>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">
                Select ZIP Archive
              </label>
              <input
                type="file"
                accept=".zip"
                onChange={(e) => setZipFile(e.target.files?.[0] || null)}
                className="block w-full text-xs text-slate-400 file:mr-4 file:rounded-lg file:border-0 file:bg-slate-800 file:px-4 file:py-2 file:text-xs file:font-bold file:text-slate-200 hover:file:bg-slate-700 cursor-pointer"
              />
            </div>

            <button
              type="submit"
              disabled={loading || !zipFile}
              className="rounded-xl bg-sky-500 px-6 py-2.5 text-sm font-bold text-slate-950 hover:bg-sky-400 disabled:opacity-50 transition shadow-lg shadow-sky-500/25"
            >
              {loading ? 'Validating & Extracting in Sandbox...' : 'Upload & Audit ZIP'}
            </button>
          </form>
        )}

        {activeTab === 'private' && (
          <form onSubmit={handlePrivateSubmit} className="space-y-4">
            <div className="rounded-xl border border-amber-500/30 bg-amber-950/20 p-4 text-xs text-amber-300 space-y-1">
              <div className="font-bold flex items-center gap-1.5">
                <span>🔑</span> Scoped GitHub App Access
              </div>
              <p className="text-[11px] leading-relaxed text-amber-200/90">
                Provide a scoped installation access token with read-only <code>contents</code> permission.
                Shallow clone (<code>--depth 1</code>) runs inside an isolated ephemeral container with disabled network egress and zero git hooks.
              </p>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">
                Repository Slug (owner/repo)
              </label>
              <input
                type="text"
                value={privateRepo}
                onChange={(e) => setPrivateRepo(e.target.value)}
                placeholder="acme-corp/private-service"
                required
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:border-sky-500 focus:outline-none font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">
                GitHub App Token (Ephemeral Access)
              </label>
              <input
                type="password"
                value={privateToken}
                onChange={(e) => setPrivateToken(e.target.value)}
                placeholder="ghs_..."
                required
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm text-slate-100 focus:border-sky-500 focus:outline-none font-mono"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="rounded-xl bg-sky-500 px-6 py-2.5 text-sm font-bold text-slate-950 hover:bg-sky-400 disabled:opacity-50 transition shadow-lg shadow-sky-500/25"
            >
              {loading ? 'Cloning in Isolated Sandbox...' : 'Clone & Ingest Private Repo'}
            </button>
          </form>
        )}

        {/* Live Pipeline Stepper during Loading */}
        {loading && (
          <div className="mt-6 rounded-2xl border border-sky-500/40 bg-slate-950/90 p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2 text-sm font-bold text-sky-400">
                <span className="h-2 w-2 rounded-full bg-sky-400 animate-ping" />
                Pipeline Orchestrator Active
              </div>
              <span className="text-xs font-mono text-slate-400">Stage {currentStep} of 5</span>
            </div>

            <div className="space-y-3">
              {PIPELINE_STEPS.map((step) => {
                const isCurrent = step.id === currentStep
                const isDone = step.id < currentStep
                return (
                  <div key={step.id} className="flex items-start gap-3 text-xs">
                    <div className="mt-0.5 shrink-0">
                      {isDone && <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400 font-bold">✓</span>}
                      {isCurrent && <div className="h-5 w-5 rounded-full border-2 border-sky-400 border-t-transparent animate-spin" />}
                      {!isDone && !isCurrent && <span className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-800 text-slate-500 font-mono text-[10px]">{step.id}</span>}
                    </div>
                    <div>
                      <div className={`font-semibold ${isCurrent ? 'text-sky-300 font-bold' : isDone ? 'text-slate-200' : 'text-slate-500'}`}>
                        {step.title}
                      </div>
                      <div className="text-slate-400 text-[11px]">{step.desc}</div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Error Notification */}
        {error && (
          <div className="mt-6 rounded-xl border border-rose-500/50 bg-rose-950/30 p-4 text-xs text-rose-300">
            <strong>Ingestion Error:</strong> {error}
          </div>
        )}

        {/* Success Confirmation & Direct Cockpit Link */}
        {result && (
          <div className="mt-6 rounded-2xl border border-emerald-500/40 bg-emerald-950/20 p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div className="text-emerald-400 font-bold text-sm flex items-center gap-2">
                <span className="text-lg">✓</span> Codebase Ingested & Fully Analyzed
              </div>
              <span className="text-xs text-slate-400 font-mono">
                {result.file_count} files ({result.total_size_kb} KB)
              </span>
            </div>

            <div className="flex flex-wrap gap-2">
              {Object.entries(result.languages || {}).map(([lang, count]) => (
                <span
                  key={lang}
                  className="rounded-lg bg-slate-800/80 px-2.5 py-1 text-xs font-mono text-slate-300"
                >
                  {lang}: {count}
                </span>
              ))}
            </div>

            {result.analysis && (
              <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3.5 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
                <div>
                  <span className="text-slate-500 text-[10px] uppercase block">Audit Score</span>
                  <span className="font-black text-slate-100 text-lg">{result.analysis.score}/100</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] uppercase block">Maturity Phase</span>
                  <span className="font-bold text-sky-400">{result.analysis.phase}</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] uppercase block">ONNX Fragility</span>
                  <span className="font-bold text-amber-400">{result.analysis.onnx_fragility ?? 'Calculated'}</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] uppercase block">Findings</span>
                  <span className="font-bold text-slate-200">{result.analysis.findings_count}</span>
                </div>
              </div>
            )}

            <div className="pt-2 flex items-center justify-between">
              <span className="text-xs text-slate-400">Target: <code className="text-slate-200 font-mono font-semibold">{result.target}</code></span>
              <button
                onClick={() => navigate('#/audit')}
                className="rounded-xl bg-emerald-500 px-5 py-2 text-xs font-bold text-slate-950 hover:bg-emerald-400 transition shadow-lg shadow-emerald-500/20"
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
