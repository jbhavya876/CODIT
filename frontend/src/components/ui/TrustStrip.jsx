import React from 'react'
import { ShieldCheck, Lock, Zap, Clock } from 'lucide-react'

/**
 * Trust & Safety Strip
 * Persistent indicator: "0 lines executed · Zip guards passed · Ephemeral sandbox · Retention: 0s"
 */
export default function TrustStrip({ className = '' }) {
  const items = [
    { icon: ShieldCheck, label: '0 Lines Executed', desc: 'Strictly static AST parsing (Tree-sitter)' },
    { icon: Lock, label: 'Zip-Slip Guards Active', desc: 'Guards against traversal, symlink & bomb attacks' },
    { icon: Zap, label: 'Ephemeral Sandbox', desc: 'Isolated execution memory' },
    { icon: Clock, label: 'Retention: 0s', desc: 'Zero persistence — memory purged immediately' },
  ]

  return (
    <aside
      aria-label="Security and Trust Guarantees"
      className={`border-y border-[#2A2E35] bg-[#0A0B0D]/80 backdrop-blur-sm py-2 px-4 ${className}`}
    >
      <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-y-2 gap-x-6 text-[11px] font-mono">
        <div className="flex items-center gap-2 text-laser-lime">
          <span className="h-1.5 w-1.5 rounded-full bg-laser-lime animate-pulse" />
          <span className="font-bold tracking-wider uppercase text-[10px]">Audit Guarantees</span>
        </div>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-slate-400">
          {items.map((item, idx) => {
            const Icon = item.icon
            return (
              <div
                key={idx}
                title={item.desc}
                className="flex items-center gap-1.5 transition-colors hover:text-slate-200 cursor-help"
              >
                <Icon className="h-3.5 w-3.5 text-laser-lime/80" />
                <span>{item.label}</span>
                {idx < items.length - 1 && <span className="text-[#2A2E35] hidden sm:inline ml-4">|</span>}
              </div>
            )
          })}
        </div>
      </div>
    </aside>
  )
}
