import React from 'react'
import { ShieldCheck, Lock, Cpu, Clock } from 'lucide-react'
import { api, useFetch } from '../../api.js'

/**
 * Compute grounded trust-strip items strictly from `/api/health` runtime posture.
 * Never claims an isolated container sandbox unless `sandbox_isolated === true`.
 */
export function buildTrustItems(posture) {
  const linesExecuted = posture?.lines_executed ?? 0
  const zipGuards = posture?.zip_guards_active !== false
  const isolated = Boolean(posture?.sandbox_isolated)
  const wallSec = posture?.walltime_seconds ?? 180
  const memMb = posture?.memory_limit_mb ?? 1024
  const srcRetention = posture?.source_retention_seconds ?? 0
  const resHours = posture?.results_retention_hours ?? 24

  return [
    {
      icon: ShieldCheck,
      label: `${linesExecuted} lines executed`,
      desc: 'Static AST and git object inspection only',
    },
    {
      icon: Lock,
      label: zipGuards ? 'Zip guards active' : 'Zip guards disabled',
      desc: 'Path traversal, symlink, and decompression quota enforcement',
    },
    {
      icon: Cpu,
      label: isolated
        ? 'Isolated sandbox'
        : `Static analysis only · ${wallSec}s / ${memMb}MB limits`,
      desc: isolated
        ? 'Process-isolated execution with resource caps'
        : 'Runs in bounded worker subprocesses with memory and wall-time limits',
    },
    {
      icon: Clock,
      label: `Source retention: ${srcRetention}s · Results kept ${resHours}h`,
      desc: 'Raw source purged immediately after analysis; derived audit results expire automatically',
    },
  ]
}

export default function TrustStrip({ className = '', postureOverride = null }) {
  const { data } = useFetch(() => (postureOverride ? Promise.resolve({ runtime_posture: postureOverride }) : api.health()), [Boolean(postureOverride)])
  const items = buildTrustItems(postureOverride || data?.runtime_posture || null)

  return (
    <aside
      aria-label="Runtime Posture and Data Retention Guarantees"
      data-testid="trust-strip"
      className={`border-y border-[#2A2E35] bg-[#0A0B0D]/90 backdrop-blur-sm py-2 px-4 ${className}`}
    >
      <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-y-2 gap-x-6 text-[11px] font-mono">
        <div className="flex items-center gap-2 text-laser-lime">
          <span className="h-1.5 w-1.5 rounded-full bg-laser-lime" aria-hidden="true" />
          <span className="font-bold tracking-wider uppercase text-[10px]">Runtime Posture</span>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-slate-300">
          {items.map((item, idx) => {
            const Icon = item.icon
            return (
              <div
                key={item.label}
                title={item.desc}
                className="flex items-center gap-1.5"
              >
                <Icon className="h-3.5 w-3.5 text-laser-lime/80 shrink-0" aria-hidden="true" />
                <span>{item.label}</span>
                {idx < items.length - 1 && <span className="text-[#2A2E35] hidden sm:inline ml-2" aria-hidden="true">|</span>}
              </div>
            )
          })}
        </div>
      </div>
    </aside>
  )
}
