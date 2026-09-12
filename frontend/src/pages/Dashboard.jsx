import React, { useMemo, useState } from 'react'
import { api, useFetch, useDebounced } from '../api.js'
import { href, navigate } from '../router.js'
import {
  ComponentRow, CritBadge, Dot, EmptyState, ErrorState, Panel, Spinner,
  StatusPill, TypeBadge, TYPE_META,
} from '../components/ui.jsx'

const TYPES = ['Service', 'Database', 'API', 'Library', 'Infrastructure']

const POPULAR = [
  ['db-postgresql', 'PostgreSQL'],
  ['infra-k8s', 'Kubernetes Cluster'],
  ['db-redis', 'Redis'],
  ['lib-sqlalchemy', 'SQLAlchemy'],
  ['svc-checkout', 'Checkout Service'],
  ['svc-customer-portal', 'Customer Portal'],
]

function SearchBox() {
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const debounced = useDebounced(q, 180)
  const { data, loading } = useFetch(
    () => (debounced.trim() ? api.search(debounced.trim()) : Promise.resolve([])),
    [debounced],
  )

  const go = (row) => {
    setOpen(false)
    setQ('')
    navigate(href.component(row.component.id))
  }

  return (
    <div className="relative">
      <div className="flex items-center gap-3 rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 shadow-lg shadow-slate-950/40 focus-within:border-sky-500/70">
        <svg viewBox="0 0 20 20" className="h-5 w-5 shrink-0 text-slate-500" fill="currentColor">
          <path fillRule="evenodd" d="M9 3.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11ZM2 9a7 7 0 1 1 12.45 4.4l3.07 3.08a.75.75 0 1 1-1.06 1.06l-3.07-3.07A7 7 0 0 1 2 9Z" clipRule="evenodd" />
        </svg>
        <input
          value={q}
          onChange={(e) => { setQ(e.target.value); setOpen(true) }}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && data?.length) go(data[0])
            if (e.key === 'Escape') setOpen(false)
          }}
          placeholder="Search components — try “PostgreSQL”, “Payment Service”, “React”…"
          className="w-full bg-transparent text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none"
          aria-label="Search components"
        />
        {loading && q && <span className="text-xs text-slate-500">searching…</span>}
      </div>
      {open && q.trim() && data && (
        <div className="absolute z-30 mt-2 w-full overflow-hidden rounded-xl border border-slate-700 bg-slate-900 shadow-xl shadow-slate-950/60">
          {data.length === 0 ? (
            <p className="px-4 py-3 text-sm text-slate-500">No components match “{q}”.</p>
          ) : (
            data.slice(0, 8).map((row) => (
              <button
                key={row.component.id}
                onClick={() => go(row)}
                className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left transition hover:bg-slate-800/70"
              >
                <span className="flex items-center gap-2.5 text-sm text-slate-200">
                  <Dot type={row.type} />
                  {row.component.name}
                </span>
                <TypeBadge type={row.type} />
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}

const PLURALS = {
  Service: 'Services',
  Module: 'Modules',
  Database: 'Databases',
  API: 'APIs',
  Library: 'Libraries',
  Infrastructure: 'Infra',
  Finding: 'Findings',
  Team: 'Teams',
}

function StatCards({ stats, activeType, onTypeClick }) {
  const relTotal = Object.values(stats?.relationships || {}).reduce((a, b) => a + b, 0)
  const availableTypes = useMemo(() => {
    const keys = Object.keys(stats?.nodes || {}).filter((k) => k !== 'Team')
    return keys.length > 0 ? keys : TYPES
  }, [stats])

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
      {availableTypes.map((type) => {
        const count = stats?.nodes?.[type] ?? '–'
        const active = activeType === type
        const plural = PLURALS[type] || `${type}s`
        return (
          <button
            key={type}
            onClick={() => onTypeClick(active ? '' : type)}
            className={`rounded-xl border px-4 py-3.5 text-left transition ${
              active ? 'border-sky-500/60 bg-slate-800/80' : 'border-slate-800 bg-slate-900/60 hover:border-slate-700'
            }`}
            title={`Filter the browser to ${plural.toLowerCase()}`}
          >
            <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-wider text-slate-400">
              <Dot type={type} /> {plural}
            </div>
            <div className="mt-1.5 text-2xl font-semibold text-slate-100">{count}</div>
          </button>
        )
      })}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3.5">
        <div className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Relations</div>
        <div className="mt-1.5 text-2xl font-semibold text-slate-100">{relTotal || '–'}</div>
      </div>
    </div>
  )
}

function Leaderboard() {
  const { data, loading, error, refetch } = useFetch(() => api.leaderboard(8), [])
  return (
    <Panel
      title="Most critical components"
      subtitle="Blast radius if the component fails — share of the graph reachable through dependency edges."
    >
      {loading && <Spinner label="Ranking components…" />}
      {error && <ErrorState error={error} onRetry={refetch} />}
      {data && (
        <ol className="space-y-1">
          {data.map((row, i) => {
            const max = data[0]?.reach || 1
            return (
              <li key={row.component.id}>
                <a href={href.impact(row.component.id)} className="group block rounded-lg px-2 py-1.5 transition hover:bg-slate-800/50">
                  <div className="flex items-center gap-2.5">
                    <span className="w-4 text-right font-mono text-[11px] text-slate-500">{i + 1}</span>
                    <Dot type={row.type} />
                    <span className="min-w-0 flex-1 truncate text-sm text-slate-200 group-hover:text-sky-300">
                      {row.component.name}
                    </span>
                    <span className="font-mono text-[11px] text-slate-500">{row.reach}</span>
                    <CritBadge tier={row.tier} />
                  </div>
                  <div className="ml-[26px] mt-1 h-1 overflow-hidden rounded-full bg-slate-800">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-sky-500 to-rose-400"
                      style={{ width: `${Math.max(4, (row.reach / max) * 100)}%` }}
                    />
                  </div>
                </a>
              </li>
            )
          })}
        </ol>
      )}
    </Panel>
  )
}

function Browser({ type }) {
  const { data, loading, error, refetch } = useFetch(
    () => api.search('', { type, limit: 100 }),
    [type],
  )
  return (
    <Panel
      title={type ? `${type}s` : 'All components'}
      subtitle="Click any component to explore its dependency neighbourhood."
    >
      {loading && <Spinner label="Loading components…" />}
      {error && <ErrorState error={error} onRetry={refetch} />}
      {data && data.length === 0 && (
        <EmptyState icon="∅" title="Nothing here yet" message="No components of this type exist in the dependency graph." />
      )}
      {data && data.length > 0 && (
        <div className="grid gap-x-6 sm:grid-cols-2">
          {data.map((row) => (
            <ComponentRow
              key={row.component.id}
              component={row.component}
              type={row.type}
              trailing={row.component.status ? <StatusPill status={row.component.status} /> : null}
            />
          ))}
        </div>
      )}
    </Panel>
  )
}

export default function Dashboard() {
  const [type, setType] = useState('')
  const { data: stats, loading, error, refetch } = useFetch(() => api.stats(), [])
  const { data: leaderboardData } = useFetch(() => api.leaderboard(6), [])

  const popularItems = useMemo(() => {
    if (leaderboardData && leaderboardData.length > 0) {
      return leaderboardData.map((l) => [l.component.id, l.component.name || l.component.id])
    }
    return POPULAR
  }, [leaderboardData])

  return (
    <div className="space-y-6">
      <div className="pt-2">
        <h1 className="text-xl font-semibold text-slate-50">What breaks if it breaks?</h1>
        <p className="mt-1 text-sm text-slate-400">
          Pick a component to see what it relies on, who relies on it, and the blast radius of a failure —
          computed live with multi-hop graph traversals in CognoDB.
        </p>
      </div>

      <SearchBox />

      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-slate-500">Quick Inspect:</span>
        {popularItems.map(([id, name]) => (
          <a
            key={id}
            href={href.component(id)}
            className="rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-xs text-slate-300 transition hover:border-sky-500/60 hover:text-sky-300 font-mono"
          >
            {name}
          </a>
        ))}
      </div>

      {error && <ErrorState error={error} onRetry={refetch} />}
      {!error && (loading ? <Spinner label="Loading graph stats…" /> : (
        <StatCards stats={stats} activeType={type} onTypeClick={setType} />
      ))}

      <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
        <Browser type={type} />
        <div className="space-y-6">
          <Leaderboard />
          <Panel title="Legend">
            <ul className="space-y-2 text-sm text-slate-400">
              {Object.entries(TYPE_META).filter(([k]) => k !== 'Team').map(([label]) => (
                <li key={label} className="flex items-center gap-2.5">
                  <Dot type={label} /> {label}
                </li>
              ))}
            </ul>
            <p className="mt-4 border-t border-slate-800 pt-3 text-xs leading-relaxed text-slate-500">
              Edges: <span className="font-mono text-slate-400">DEPENDS_ON · CALLS · READS_FROM · WRITES_TO · USES · DEPLOYED_ON</span>
            </p>
          </Panel>
        </div>
      </div>
    </div>
  )
}
