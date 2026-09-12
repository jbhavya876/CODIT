import React, { useState } from 'react'
import { api } from '../api.js'
import { navigate } from '../router.js'

export default function IngestPage() {
  const [activeTab, setActiveTab] = useState('public') // 'public', 'private', 'zip'
  const [publicUrl, setPublicUrl] = useState('https://github.com/charmi-reddy/Dependency-Detective')
  const [publicRef, setPublicRef] = useState('main')

  const [privateRepo, setPrivateRepo] = useState('')
  const [privateToken, setPrivateToken] = useState('')

  const [zipFile, setZipFile] = useState(null)

  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handlePublicSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const res = await api.ingestPublic(publicUrl, publicRef)
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
    try {
      const res = await api.ingestPrivate(privateRepo, privateToken)
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
    try {
      const formData = new FormData()
      formData.append('file', zipFile)
      const res = await api.ingestZip(formData)
      setResult(res)
    } catch (err) {
      setError(err.message || 'Failed to extract ZIP archive.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-8 max-w-4xl mx-auto">
      <div>
        <div className="inline-flex items-center gap-2 rounded-full border border-sky-500/30 bg-sky-500/10 px-3 py-1 text-xs font-medium text-sky-400">
          Module 1 · Multi-Tier Repository Ingestion
        </div>
        <h1 className="mt-3 text-2xl font-bold tracking-tight text-slate-100 sm:text-3xl">
          Ingest Target Codebase
        </h1>
        <p className="mt-2 text-sm text-slate-400">
          Accepts public GitHub repos, private repos via GitHub App scoped tokens, or ZIP archives.
          Static analysis only: untrusted code is never executed, and uploaded ZIPs are destroyed post-report.
        </p>
      </div>

      {/* Intake Tabs */}
      <div className="flex border-b border-slate-800">
        <button
          onClick={() => { setActiveTab('public'); setError(null); }}
          className={`px-5 py-3 text-sm font-medium border-b-2 transition ${
            activeTab === 'public'
              ? 'border-sky-500 text-sky-400 bg-slate-900/40'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          🌐 Public GitHub Repo
          <span className="ml-2 rounded-full bg-slate-800 px-2 py-0.5 text-[10px] text-slate-300">Free</span>
        </button>

        <button
          onClick={() => { setActiveTab('zip'); setError(null); }}
          className={`px-5 py-3 text-sm font-medium border-b-2 transition ${
            activeTab === 'zip'
              ? 'border-sky-500 text-sky-400 bg-slate-900/40'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          📦 ZIP Archive Upload
          <span className="ml-2 rounded-full bg-emerald-950 border border-emerald-500/40 px-2 py-0.5 text-[10px] text-emerald-400">Zero Retention</span>
        </button>

        <button
          onClick={() => { setActiveTab('private'); setError(null); }}
          className={`px-5 py-3 text-sm font-medium border-b-2 transition ${
            activeTab === 'private'
              ? 'border-sky-500 text-sky-400 bg-slate-900/40'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          🔒 Private Repo (GitHub App)
          <span className="ml-2 rounded-full bg-slate-800 px-2 py-0.5 text-[10px] text-slate-300">Paid Tier</span>
        </button>
      </div>

      {/* Tab Panels */}
      <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-6 shadow-xl">
        {activeTab === 'public' && (
          <form onSubmit={handlePublicSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Public GitHub Repository URL or Slug
              </label>
              <input
                type="text"
                value={publicUrl}
                onChange={(e) => setPublicUrl(e.target.value)}
                placeholder="https://github.com/owner/repository"
                required
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:border-sky-500 focus:outline-none"
              />
              <p className="mt-1 text-xs text-slate-500">
                Fetched recursively via GitHub REST API tree endpoints with rate-limit protection. No clone executed.
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Branch / Ref (Default: main)
              </label>
              <input
                type="text"
                value={publicRef}
                onChange={(e) => setPublicRef(e.target.value)}
                className="w-48 rounded-lg border border-slate-700 bg-slate-950 px-4 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="rounded-lg bg-sky-500 px-5 py-2.5 text-sm font-semibold text-slate-950 hover:bg-sky-400 disabled:opacity-50 transition"
            >
              {loading ? 'Fetching Repository Tree...' : 'Ingest Repository'}
            </button>
          </form>
        )}

        {activeTab === 'zip' && (
          <form onSubmit={handleZipSubmit} className="space-y-4">
            <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 text-xs text-emerald-300 space-y-1">
              <div className="font-semibold flex items-center gap-1.5">
                <span>🛡️ Non-Negotiable Privacy & Defense Guarantee</span>
              </div>
              <p>
                1. Every entry is strictly verified against <strong>Zip-Slip</strong> and <strong>Zip-Bomb</strong> before extracting.
              </p>
              <p>
                2. Extracted files reside in an ephemeral, resource-capped directory and are <strong>permanently destroyed</strong> immediately post-audit.
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Select .ZIP Archive (Max 200MB, 5,000 files)
              </label>
              <input
                type="file"
                accept=".zip"
                onChange={(e) => setZipFile(e.target.files[0] || null)}
                required
                className="w-full text-sm text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-slate-800 file:text-slate-200 hover:file:bg-slate-700 cursor-pointer"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="rounded-lg bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-slate-950 hover:bg-emerald-400 disabled:opacity-50 transition"
            >
              {loading ? 'Validating & Extracting...' : 'Upload & Validate Archive'}
            </button>
          </form>
        )}

        {activeTab === 'private' && (
          <form onSubmit={handlePrivateSubmit} className="space-y-4">
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-xs text-amber-300">
              <div className="font-semibold">GitHub App Integration</div>
              <p className="mt-1">
                For private repositories, provide a scoped installation access token (read-only <code>contents</code> permission).
                Shallow clone is performed inside an isolated sandbox with zero hooks.
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Repository Slug (owner/repo)
              </label>
              <input
                type="text"
                value={privateRepo}
                onChange={(e) => setPrivateRepo(e.target.value)}
                placeholder="acme-corp/private-service"
                required
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:border-sky-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                GitHub App Token (Ephemeral Access)
              </label>
              <input
                type="password"
                value={privateToken}
                onChange={(e) => setPrivateToken(e.target.value)}
                placeholder="ghs_..."
                required
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="rounded-lg bg-sky-500 px-5 py-2.5 text-sm font-semibold text-slate-950 hover:bg-sky-400 disabled:opacity-50 transition"
            >
              {loading ? 'Cloning in Isolated Sandbox...' : 'Clone & Ingest Private Repo'}
            </button>
          </form>
        )}

        {error && (
          <div className="mt-6 rounded-lg border border-rose-500/50 bg-rose-950/30 p-4 text-sm text-rose-300">
            <strong>Ingestion Error:</strong> {error}
          </div>
        )}

        {result && (
          <div className="mt-6 rounded-lg border border-emerald-500/40 bg-emerald-950/20 p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div className="text-emerald-400 font-semibold text-sm">
                ✓ Codebase Ingested Successfully
              </div>
              <span className="text-xs text-slate-400">
                {result.file_count} files ({result.total_size_kb} KB)
              </span>
            </div>

            <div className="flex flex-wrap gap-2">
              {Object.entries(result.languages || {}).map(([lang, count]) => (
                <span
                  key={lang}
                  className="rounded-md bg-slate-800/80 px-2.5 py-1 text-xs font-mono text-slate-300"
                >
                  {lang}: {count}
                </span>
              ))}
            </div>

            <div className="pt-2 flex items-center justify-between">
              <span className="text-xs text-slate-400">Target: <code className="text-slate-200">{result.target}</code></span>
              <button
                onClick={() => navigate('#/audit')}
                className="rounded-lg bg-emerald-500 px-4 py-2 text-xs font-semibold text-slate-950 hover:bg-emerald-400 transition"
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
