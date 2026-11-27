import React, { useEffect, useState } from 'react'
import { X, Shield, Terminal, Copy, Check } from 'lucide-react'

const SNIPPETS = [
  {
    id: 'claude',
    title: '1. Agent Hook — Claude Code PreToolUse',
    layer: 'Agent hook (shortens feedback loop; agent can use unmatched tools)',
    cmd: `pip install codit-guard
codit-guard install --agent claude-code`,
  },
  {
    id: 'precommit',
    title: '2. Commit Hook — git / pre-commit',
    layer: 'Commit hook (blocks local commits; bypassable with git commit --no-verify)',
    cmd: `codit-guard install --git-hook
# or in .pre-commit-config.yaml:
# - repo: local / codit-guard (id: codit-guard-staged)`,
  },
  {
    id: 'ci',
    title: '3. CI Required Status Check — GitHub Actions',
    layer: 'CI check (AUTHORITATIVE gate on protected branches)',
    cmd: `- uses: codit/action@v1
  with:
    fail_on: high
    offline: "true"`,
  },
]

export default function GuardDrawer({ isOpen, onClose }) {
  const [copiedId, setCopiedId] = useState(null)

  useEffect(() => {
    if (!isOpen) return
    const onKey = (e) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [isOpen, onClose])

  if (!isOpen) return null

  const copySnippet = (text, id) => {
    navigator.clipboard?.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 1600)
  }

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/70 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="CODIT Guard Setup Drawer"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl bg-[#15171B] border-l border-[#2A2E35] h-full overflow-y-auto p-6 space-y-5 font-sans text-slate-200 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between border-b border-[#2A2E35] pb-4">
          <div>
            <div className="font-mono text-[11px] uppercase tracking-wider text-laser-lime flex items-center gap-1.5">
              <Shield className="w-3.5 h-3.5" aria-hidden="true" />
              <span>codit-guard // Diff-Level Assurance Gate</span>
            </div>
            <h2 className="mt-1 text-xl font-serif font-normal text-slate-50">
              Enforcement Layers &amp; Local Setup
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close Guard drawer"
            data-testid="close-guard-drawer"
            className="rounded border border-[#2A2E35] bg-[#0A0B0D] p-1.5 text-slate-400 hover:text-white"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="rounded-lg border border-amber-900/60 bg-amber-950/20 p-3.5 text-xs space-y-2">
          <div className="font-mono font-bold text-[#FFB020] uppercase text-[11px]">
            Honest Enforcement Boundary
          </div>
          <p className="text-slate-200 font-semibold">
            Only the CI check, set as a required status check, is authoritative.
          </p>
          <div className="overflow-x-auto" tabIndex={0} aria-label="Enforcement layer comparison table">
            <table className="w-full text-left text-[11px] font-mono border-t border-amber-900/40 mt-2">
              <thead>
                <tr className="text-slate-400">
                  <th className="py-1.5 pr-2">Layer</th>
                  <th className="py-1.5 pr-2">Purpose</th>
                  <th className="py-1.5">Bypass Boundary</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#2A2E35] text-slate-300">
                <tr>
                  <td className="py-1.5 pr-2 font-bold">Agent hook</td>
                  <td className="py-1.5 pr-2">Immediate PreToolUse feedback</td>
                  <td className="py-1.5">Agent can use unmatched tools</td>
                </tr>
                <tr>
                  <td className="py-1.5 pr-2 font-bold">Commit hook</td>
                  <td className="py-1.5 pr-2">Blocks local staged diffs</td>
                  <td className="py-1.5">Bypassable via <code>git commit --no-verify</code></td>
                </tr>
                <tr>
                  <td className="py-1.5 pr-2 font-bold text-laser-lime">CI check</td>
                  <td className="py-1.5 pr-2">Authoritative PR gate (base policy)</td>
                  <td className="py-1.5">Required status check on protected branch</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div className="space-y-4">
          {SNIPPETS.map((s) => (
            <div key={s.id} className="rounded-lg border border-[#2A2E35] bg-[#0A0B0D] p-3.5 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <div className="font-mono text-xs font-bold text-slate-100 flex items-center gap-1.5">
                    <Terminal className="w-3.5 h-3.5 text-laser-lime" aria-hidden="true" />
                    <span>{s.title}</span>
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5">{s.layer}</div>
                </div>
                <button
                  type="button"
                  onClick={() => copySnippet(s.cmd, s.id)}
                  data-testid={`copy-guard-${s.id}`}
                  className="inline-flex items-center gap-1 rounded border border-[#2A2E35] bg-[#15171B] px-2.5 py-1 text-[11px] font-mono text-laser-lime hover:border-laser-lime"
                >
                  {copiedId === s.id ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                  <span>{copiedId === s.id ? 'Copied' : 'Copy'}</span>
                </button>
              </div>
              <pre className="rounded border border-[#2A2E35] bg-[#050608] p-2.5 text-[11px] font-mono text-slate-300 overflow-x-auto" tabIndex={0}>
                {s.cmd}
              </pre>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
