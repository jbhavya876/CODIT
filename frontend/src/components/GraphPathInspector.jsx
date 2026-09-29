import React, { useState, useEffect } from 'react'
import { api, useFetch } from '../api.js'
import MermaidViewer from './MermaidViewer.jsx'
import { Dot, TypeBadge, StatusPill, CritBadge, RelBadge } from './ui.jsx'

export default function GraphPathInspector({ componentId, initialTab = 'deps', initialPathTo = '', onClose }) {
  const [tab, setTab] = useState(initialTab) // 'deps', 'blast', 'path'
  const [currentId, setCurrentId] = useState(componentId)
  const [pathTo, setPathTo] = useState(initialPathTo)
  const [pathSearching, setPathSearching] = useState(false)
  const [pathResult, setPathResult] = useState(null)
  const [pathError, setPathError] = useState(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    setCurrentId(componentId)
  }, [componentId])

  useEffect(() => {
    if (initialTab) setTab(initialTab)
  }, [initialTab])

  useEffect(() => {
    if (initialPathTo) {
      setPathTo(initialPathTo)
      runPathSearch(currentId, initialPathTo)
    }
  }, [initialPathTo, currentId])

  // Fetch component dependencies & details
  const { data: depData, loading: depLoading, error: depError } = useFetch(
    () => (currentId ? api.dependencies(currentId) : Promise.resolve(null)),
    [currentId]
  )

  // Fetch component criticality
  const { data: critData, loading: critLoading } = useFetch(
    () => (currentId ? api.criticality(currentId) : Promise.resolve(null)),
    [currentId]
  )

  // Fetch blast radius diagram
  const { data: blastData, loading: blastLoading } = useFetch(
    () => (currentId ? api.getBlastRadiusDiagram(currentId) : Promise.resolve(null)),
    [currentId]
  )

  // Fetch all components for path dropdown
  const { data: allComponents } = useFetch(
    () => api.search('', { limit: 100 }),
    []
  )

  const runPathSearch = async (fromId, toId) => {
    if (!fromId || !toId || fromId === toId) return
    setPathSearching(true)
    setPathError(null)
    try {
      const res = await api.path(fromId, toId)
      setPathResult(res)
    } catch (err) {
      setPathError(err.message || 'Unable to compute dependency path.')
      setPathResult(null)
    } finally {
      setPathSearching(false)
    }
  }

  const handleCopyId = () => {
    navigator.clipboard.writeText(currentId)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (!currentId) return null

  const record = depData?.component?.component || {}
  const compType = depData?.component?.type || 'Module'
  const dependencies = depData?.dependencies || []
  const dependents = depData?.dependents || []

  return (
    <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-2xl flex-col border-l border-slate-800 bg-[#0c1220]/95 shadow-2xl backdrop-blur-xl">
      {/* Drawer Header */}
      <div className="border-b border-slate-800/80 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <Dot type={compType} />
              <h2 className="truncate text-lg font-bold text-slate-100" title={record.name || currentId}>
                {record.name || currentId}
              </h2>
              <TypeBadge type={compType} />
              {record.status && <StatusPill status={record.status} />}
              {critData?.tier && <CritBadge tier={critData.tier} />}
            </div>

            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs font-mono text-slate-400">
              <span className="truncate max-w-md bg-slate-900 px-2 py-0.5 rounded border border-slate-800 text-slate-300">
                {currentId}
              </span>
              <button
                onClick={handleCopyId}
                className="text-[11px] text-sky-400 hover:text-sky-300 font-mono transition"
              >
                {copied ? '✓ Copied' : '📋 Copy ID'}
              </button>
              {record.owner && <span className="text-slate-500">· owner: {record.owner}</span>}
              {record.language && <span className="text-slate-500">· {record.language}</span>}
            </div>
          </div>

          <button
            onClick={onClose}
            className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-slate-100 transition"
            title="Close Inspector"
          >
            <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </button>
        </div>

        {/* Navigation Tabs */}
        <div className="mt-4 flex gap-1 rounded-lg border border-slate-800 bg-slate-950 p-1">
          <button
            onClick={() => setTab('deps')}
            className={`flex-1 rounded-md py-1.5 text-xs font-semibold transition ${
              tab === 'deps'
                ? 'bg-sky-500 text-slate-950 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Neighborhood ({dependencies.length + dependents.length})
          </button>
          <button
            onClick={() => setTab('blast')}
            className={`flex-1 rounded-md py-1.5 text-xs font-semibold transition ${
              tab === 'blast'
                ? 'bg-sky-500 text-slate-950 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Blast Radius ({critData?.total ?? 0})
          </button>
          <button
            onClick={() => setTab('path')}
            className={`flex-1 rounded-md py-1.5 text-xs font-semibold transition ${
              tab === 'path'
                ? 'bg-sky-500 text-slate-950 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Path Finder
          </button>
        </div>
      </div>

      {/* Drawer Body */}
      <div className="flex-1 overflow-y-auto p-5 space-y-5">
        {/* --- TAB 1: NEIGHBORHOOD --- */}
        {tab === 'deps' && (
          <div className="space-y-6">
            {depLoading && (
              <div className="flex items-center justify-center p-8 text-xs text-slate-500">
                <span className="h-4 w-4 animate-spin rounded-full border border-sky-400 border-t-transparent mr-2" />
                Querying graph neighborhood...
              </div>
            )}

            {depError && (
              <div className="rounded-lg border border-rose-500/30 bg-rose-950/20 p-4 text-xs text-rose-300">
                {depError.message || 'Unable to load component dependencies.'}
              </div>
            )}

            {!depLoading && !depError && (
              <>
                {/* Dependencies: What this component relies on */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
                      Relies On ({dependencies.length})
                    </span>
                    <span className="text-[10px] text-slate-500">Upstream Dependencies</span>
                  </div>
                  {dependencies.length === 0 ? (
                    <div className="rounded-lg border border-dashed border-slate-800 p-4 text-center text-xs text-slate-500">
                      This component has no outgoing dependencies — it is foundational.
                    </div>
                  ) : (
                    <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1">
                      {dependencies.map((row, idx) => {
                        const targetComp = row.component || {}
                        return (
                          <div
                            key={idx}
                            onClick={() => setCurrentId(targetComp.id)}
                            className="group flex items-center justify-between rounded-lg border border-slate-800/80 bg-slate-950/60 p-2.5 text-xs transition hover:border-sky-500/50 hover:bg-slate-900 cursor-pointer"
                          >
                            <div className="flex items-center gap-2 min-w-0">
                              <Dot type={row.type} />
                              <span className="truncate font-medium text-slate-200 group-hover:text-sky-300">
                                {targetComp.name || targetComp.id}
                              </span>
                              <TypeBadge type={row.type} />
                            </div>
                            <div className="flex items-center gap-2 shrink-0">
                              <RelBadge rel={row.rel} />
                              <span className="text-slate-600 group-hover:text-sky-400">›</span>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>

                {/* Dependents: What relies on this component */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
                      Relied On By ({dependents.length})
                    </span>
                    <span className="text-[10px] text-slate-500">Downstream Impact Targets</span>
                  </div>
                  {dependents.length === 0 ? (
                    <div className="rounded-lg border border-dashed border-slate-800 p-4 text-center text-xs text-slate-500">
                      Nothing depends on this component — it is a terminal leaf.
                    </div>
                  ) : (
                    <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1">
                      {dependents.map((row, idx) => {
                        const sourceComp = row.component || {}
                        return (
                          <div
                            key={idx}
                            onClick={() => setCurrentId(sourceComp.id)}
                            className="group flex items-center justify-between rounded-lg border border-slate-800/80 bg-slate-950/60 p-2.5 text-xs transition hover:border-sky-500/50 hover:bg-slate-900 cursor-pointer"
                          >
                            <div className="flex items-center gap-2 min-w-0">
                              <Dot type={row.type} />
                              <span className="truncate font-medium text-slate-200 group-hover:text-sky-300">
                                {sourceComp.name || sourceComp.id}
                              </span>
                              <TypeBadge type={row.type} />
                            </div>
                            <div className="flex items-center gap-2 shrink-0">
                              <RelBadge rel={row.rel} />
                              <span className="text-slate-600 group-hover:text-sky-400">›</span>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        )}

        {/* --- TAB 2: BLAST RADIUS --- */}
        {tab === 'blast' && (
          <div className="space-y-4">
            {/* Criticality Metrics Banner */}
            {critData && (
              <div className="grid grid-cols-3 gap-2 rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-center">
                <div>
                  <span className="text-[10px] uppercase text-slate-500 block">Criticality Tier</span>
                  <span className={`text-base font-bold ${
                    critData.tier === 'HIGH' ? 'text-rose-400' : critData.tier === 'MEDIUM' ? 'text-amber-400' : 'text-emerald-400'
                  }`}>
                    {critData.tier}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] uppercase text-slate-500 block">Graph Reach</span>
                  <span className="text-base font-bold font-mono text-sky-400">
                    {((critData.share || 0) * 100).toFixed(1)}%
                  </span>
                </div>
                <div>
                  <span className="text-[10px] uppercase text-slate-500 block">Total Blast Radius</span>
                  <span className="text-base font-bold font-mono text-slate-200">
                    {critData.total || 0} nodes
                  </span>
                </div>
              </div>
            )}

            {/* Blast Radius Visualizer */}
            {blastLoading ? (
              <div className="flex items-center justify-center p-12 text-xs text-slate-500">
                <span className="h-4 w-4 animate-spin rounded-full border border-sky-400 border-t-transparent mr-2" />
                Traversing failure propagation paths...
              </div>
            ) : blastData?.mermaid ? (
              <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
                <div className="mb-2 flex items-center justify-between text-[11px] text-slate-400">
                  <span className="font-semibold">Multi-Hop Failure Tree</span>
                  <span className="font-mono text-slate-500">openCypher Traversal (*1..6)</span>
                </div>
                <MermaidViewer code={blastData.mermaid} />
              </div>
            ) : (
              <div className="rounded-lg border border-dashed border-slate-800 p-8 text-center text-xs text-slate-500">
                No blast radius impact paths found for this component.
              </div>
            )}
          </div>
        )}

        {/* --- TAB 3: PATH FINDER --- */}
        {tab === 'path' && (
          <div className="space-y-4">
            <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 space-y-3">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-300 block">
                Find Shortest Dependency Path
              </span>
              <p className="text-[11px] text-slate-400">
                Calculates the exact sequence of dependency relationships between this component and another target in the graph.
              </p>

              <div className="space-y-2">
                <label className="text-[11px] text-slate-400 block font-semibold">Destination Component:</label>
                <div className="flex gap-2">
                  <select
                    value={pathTo}
                    onChange={(e) => {
                      setPathTo(e.target.value)
                      if (e.target.value) runPathSearch(currentId, e.target.value)
                    }}
                    className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-100 focus:border-sky-500 focus:outline-none"
                  >
                    <option value="">-- Select Destination Component --</option>
                    {(allComponents || []).map((row) => {
                      const c = row.component
                      if (c.id === currentId) return null
                      return (
                        <option key={c.id} value={c.id}>
                          {c.name || c.id} ({row.type})
                        </option>
                      )
                    })}
                  </select>

                  <button
                    onClick={() => runPathSearch(currentId, pathTo)}
                    disabled={pathSearching || !pathTo}
                    className="rounded-lg bg-sky-500 px-4 py-2 text-xs font-bold text-slate-950 hover:bg-sky-400 disabled:opacity-50 transition"
                  >
                    {pathSearching ? 'Searching…' : 'Find Path'}
                  </button>
                </div>
              </div>
            </div>

            {/* Path Search Result */}
            {pathSearching && (
              <div className="flex items-center justify-center p-8 text-xs text-slate-500">
                <span className="h-4 w-4 animate-spin rounded-full border border-sky-400 border-t-transparent mr-2" />
                Computing shortest path in CognoDB...
              </div>
            )}

            {pathError && (
              <div className="rounded-lg border border-rose-500/30 bg-rose-950/20 p-3 text-xs text-rose-300">
                {pathError}
              </div>
            )}

            {pathResult && !pathSearching && (
              <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 space-y-3">
                <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
                  <span className="text-xs font-bold text-slate-200">
                    {pathResult.found ? `Path Found (${pathResult.length} hops)` : 'No Path Exists'}
                  </span>
                  <span className="text-[10px] font-mono text-slate-500">
                    Traversed {pathResult.checked || 0} paths
                  </span>
                </div>

                {pathResult.found && pathResult.path?.length > 0 ? (
                  <div className="space-y-2 pt-2">
                    {pathResult.path.map((step, idx) => (
                      <div key={idx} className="flex items-center gap-3">
                        <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-800 font-mono text-[10px] text-sky-400">
                          {idx + 1}
                        </div>
                        <div className="flex-1 rounded-lg border border-slate-800/80 bg-slate-900/60 p-2.5 text-xs">
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-slate-200">{step.name || step.id}</span>
                            <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[9px] font-mono text-slate-400">
                              {step.type}
                            </span>
                          </div>
                          {step.relationship && (
                            <div className="mt-1 flex items-center gap-1.5 text-[10px] font-mono text-slate-500">
                              <span>relies via</span>
                              <RelBadge rel={step.relationship} />
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 pt-1">
                    No directed dependency connection exists between <code className="text-slate-300">{currentId}</code> and <code className="text-slate-300">{pathTo}</code>.
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
