import React, { useEffect, useState, useRef } from 'react'
import { Search, Compass, Terminal, FileCode, ShieldAlert, ArrowRight, CornerDownLeft } from 'lucide-react'
import { href, navigate } from '../../router.js'

/**
 * Command Palette (Cmd/Ctrl + K)
 * Keyboard-first navigation for security engineers, auditors, and developers.
 */
export default function CommandPalette({ isOpen, onClose, findings = [], components = [] }) {
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef(null)

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50)
      setQuery('')
      setSelectedIndex(0)
    }
  }, [isOpen])

  // Build searchable items
  const baseActions = [
    { id: 'nav-audit', title: 'Go to Audit Cockpit', group: 'Navigation', icon: Compass, action: () => navigate(href.audit()) },
    { id: 'nav-ingest', title: 'Ingest Repository (Public, Token, ZIP)', group: 'Navigation', icon: Terminal, action: () => navigate(href.ingest()) },
    { id: 'nav-export-md', title: 'Download Audit Report (Markdown)', group: 'Export', icon: FileCode, action: () => window.open('/api/report/markdown', '_blank') },
    { id: 'nav-export-html', title: 'Download Standalone Audit Report (HTML/PDF)', group: 'Export', icon: FileCode, action: () => window.open('/api/report/html', '_blank') },
    { id: 'nav-design-sys', title: 'View Design System Specimen', group: 'Developer', icon: Terminal, action: () => navigate('#/design-system') },
  ]

  const findingItems = (findings || []).slice(0, 10).map((f) => ({
    id: `finding-${f.id}`,
    title: `[${f.severity?.toUpperCase()}] ${f.description}`,
    sub: `${f.evidence_file}:${f.evidence_line || 1} · Rule: ${f.rule_id || 'AUDIT'}`,
    group: 'Findings',
    icon: ShieldAlert,
    action: () => {
      navigate(href.audit(f.component_id || f.evidence_file))
    },
  }))

  const compItems = (components || []).slice(0, 8).map((c) => ({
    id: `comp-${c.id}`,
    title: c.name,
    sub: `Type: ${c.type} · Relied on by downstream modules`,
    group: 'Graph Components',
    icon: Compass,
    action: () => {
      navigate(href.component(c.id))
    },
  }))

  const allItems = [...baseActions, ...findingItems, ...compItems]

  const filtered = query.trim()
    ? allItems.filter(
        (item) =>
          item.title.toLowerCase().includes(query.toLowerCase()) ||
          (item.sub && item.sub.toLowerCase().includes(query.toLowerCase())) ||
          item.group.toLowerCase().includes(query.toLowerCase())
      )
    : allItems

  useEffect(() => {
    setSelectedIndex(0)
  }, [query])

  // Keyboard navigation
  const handleKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex((prev) => (prev + 1) % (filtered.length || 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex((prev) => (prev - 1 + filtered.length) % (filtered.length || 1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (filtered[selectedIndex]) {
        filtered[selectedIndex].action()
        onClose()
      }
    } else if (e.key === 'Escape') {
      e.preventDefault()
      onClose()
    }
  }

  if (!isOpen) return null

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Command Palette"
      className="fixed inset-0 z-50 flex items-start justify-center pt-20 px-4 bg-black/70 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-2xl rounded-xl border border-[#2A2E35] bg-[#15171B] shadow-instrument-elevated overflow-hidden"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        {/* Input Bar */}
        <div className="flex items-center gap-3 border-b border-[#2A2E35] px-4 py-3.5 bg-[#0A0B0D]">
          <Search className="w-4 h-4 text-laser-lime" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type a command, finding citation, or component name…"
            className="w-full bg-transparent text-sm font-sans text-slate-100 placeholder-slate-500 focus:outline-none"
          />
          <kbd className="hidden sm:inline-block rounded border border-[#2A2E35] bg-[#15171B] px-1.5 py-0.5 text-[10px] font-mono text-slate-400">
            ESC
          </kbd>
        </div>

        {/* Results List */}
        <div className="max-h-96 overflow-y-auto p-2 divide-y divide-[#2A2E35]/40">
          {filtered.length === 0 ? (
            <div className="py-12 text-center text-xs font-mono text-slate-500">
              No matching commands or telemetry artifacts found.
            </div>
          ) : (
            filtered.map((item, idx) => {
              const isSelected = idx === selectedIndex
              const Icon = item.icon
              return (
                <div
                  key={item.id}
                  onClick={() => {
                    item.action()
                    onClose()
                  }}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`flex items-center justify-between gap-3 px-3 py-2.5 rounded-lg cursor-pointer transition-colors ${
                    isSelected ? 'bg-laser-lime/10 text-white border border-laser-lime/30' : 'text-slate-300 hover:bg-[#1E2228]'
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <Icon className={`w-4 h-4 shrink-0 ${isSelected ? 'text-laser-lime' : 'text-slate-500'}`} />
                    <div className="min-w-0 truncate">
                      <div className="text-xs font-sans font-medium truncate">{item.title}</div>
                      {item.sub && (
                        <div className="text-[11px] font-mono text-slate-400 truncate">{item.sub}</div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">
                      {item.group}
                    </span>
                    {isSelected && <CornerDownLeft className="w-3.5 h-3.5 text-laser-lime" />}
                  </div>
                </div>
              )
            })
          )}
        </div>

        {/* Footer Navigation Hints */}
        <div className="flex items-center justify-between border-t border-[#2A2E35] bg-[#0A0B0D] px-4 py-2 text-[10px] font-mono text-slate-500">
          <div className="flex items-center gap-3">
            <span>↑↓ Navigate</span>
            <span>↵ Select</span>
            <span>ESC Close</span>
          </div>
          <span className="text-laser-lime/80 font-bold">CODIT PALETTE</span>
        </div>
      </div>
    </div>
  )
}
