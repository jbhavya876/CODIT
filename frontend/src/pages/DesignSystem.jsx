import React, { useState } from 'react'
import TrustStrip from '../components/ui/TrustStrip.jsx'
import VerdictSeal from '../components/ui/VerdictSeal.jsx'
import OdometerNumeral from '../components/ui/OdometerNumeral.jsx'
import { CritBadge, ConfidenceGauge, EvidenceCitation } from '../components/ui.jsx'
import { ArrowLeft, RefreshCw, Zap, Shield, FileCode, CheckCircle2 } from 'lucide-react'
import { href, navigate } from '../router.js'

export default function DesignSystem() {
  const [odometerScore, setOdometerScore] = useState(87)
  const [selectedTier, setSelectedTier] = useState('CRITICAL')

  const tokens = [
    { name: 'Obsidian Bedrock', hex: '#0A0B0D', role: 'Chamber Ground Void', dark: true },
    { name: 'Obsidian Graphite', hex: '#15171B', role: 'Chamber Elevated Card Deck', dark: true },
    { name: 'Obsidian Steel', hex: '#2A2E35', role: '1px Structural Boundary Lines', dark: true },
    { name: 'Dossier Bone', hex: '#EFEAE0', role: 'Archival Paper Surface', dark: false },
    { name: 'Dossier Ink', hex: '#101114', role: 'Dossier Carbon Typography', dark: true },
    { name: 'Laser Lime', hex: '#D4FF3A', role: 'Precision Metrology Signal Laser', dark: false },
  ]

  return (
    <div className="min-h-screen bg-[#0A0B0D] text-slate-200 p-6 md:p-12 space-y-12 max-w-7xl mx-auto">
      {/* Header */}
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-[#2A2E35] pb-6">
        <div>
          <button
            onClick={() => navigate(href.audit())}
            className="flex items-center gap-2 text-xs font-mono text-slate-400 hover:text-laser-lime transition mb-2"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Return to Audit Cockpit
          </button>
          <h1 className="font-serif text-3xl md:text-5xl font-normal text-slate-100 tracking-tight">
            CODIT Metrology & Design System
          </h1>
          <p className="font-mono text-xs text-slate-400 mt-1 uppercase tracking-widest">
            Design Direction: Forensic Luxury · Dual-Atmosphere Specification
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded border border-laser-lime/40 bg-laser-lime/10 px-2.5 py-1 font-mono text-[11px] font-bold text-laser-lime">
            v3.0 COMPLIANT
          </span>
        </div>
      </header>

      {/* Palette Tokens */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-mono text-xs font-bold uppercase tracking-wider text-slate-300">
            01 / Substrate & Laser Palette Tokens
          </h2>
          <span className="font-mono text-[11px] text-slate-500">OKLCH Calibrated</span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {tokens.map((tok) => (
            <div
              key={tok.name}
              className="rounded-lg border border-[#2A2E35] bg-[#15171B] p-3 flex flex-col justify-between h-32"
            >
              <div
                className="w-full h-12 rounded border border-white/10"
                style={{ backgroundColor: tok.hex }}
              />
              <div className="mt-2">
                <div className="text-xs font-mono font-bold text-slate-200">{tok.name}</div>
                <div className="text-[10px] font-mono text-slate-400">{tok.hex}</div>
                <div className="text-[9px] text-slate-500 truncate mt-0.5">{tok.role}</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Typography Scale */}
      <section className="space-y-6">
        <h2 className="font-mono text-xs font-bold uppercase tracking-wider text-slate-300">
          02 / Typography Hierarchy (Editorial Serif + Swiss Grotesk + Precision Mono)
        </h2>
        <div className="rounded-xl border border-[#2A2E35] bg-[#15171B] p-6 space-y-6">
          <div>
            <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500 mb-1">
              Display Verdict Serif · Instrument Serif
            </div>
            <div className="font-serif text-4xl md:text-6xl text-slate-100 tracking-tight leading-none">
              Defect Risk Tier: Production Ready
            </div>
          </div>
          <div className="border-t border-[#2A2E35] pt-4">
            <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500 mb-1">
              Interface & Body · Geist Sans
            </div>
            <p className="font-sans text-sm text-slate-300 max-w-3xl leading-relaxed">
              CODIT performs deterministic Tree-sitter AST parsing across repository sources without untrusted code execution. Multi-hop reach graphs identify cascading single-points-of-failure across services and data stores.
            </p>
          </div>
          <div className="border-t border-[#2A2E35] pt-4">
            <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500 mb-1">
              Data, Code Citations & Hashes · JetBrains Mono (Tabular Figures)
            </div>
            <div className="font-mono text-xs text-sky-300 space-y-1">
              <div>SHA256: 9b2d87e04f93c52a089d3112847291a0c4f88e7b1a2c3d4e5f60718293a4b5c6</div>
              <div>LOC: backend/app/auth.py:47 · AST_NODE: FunctionDef[generate_jwt]</div>
            </div>
          </div>
        </div>
      </section>

      {/* Metrology: Two-Channel Severity & Confidence */}
      <section className="space-y-4">
        <h2 className="font-mono text-xs font-bold uppercase tracking-wider text-slate-300">
          03 / Two-Channel Severity Metrology & Decoupled Confidence
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Severity Badges */}
          <div className="rounded-xl border border-[#2A2E35] bg-[#15171B] p-5 space-y-4">
            <div className="text-xs font-mono font-bold text-slate-200">Severity Badges (Glyph + Color + Label)</div>
            <div className="flex flex-wrap gap-2">
              <CritBadge tier="CRITICAL" />
              <CritBadge tier="HIGH" />
              <CritBadge tier="MEDIUM" />
              <CritBadge tier="LOW" />
              <CritBadge tier="INFO" />
            </div>
            <p className="text-[11px] text-slate-400 font-sans">
              Meets WCAG 2.2 AA non-text contrast guidelines. Communicates risk state under full Protanopia, Deuteranopia, and Tritanopia conditions.
            </p>
          </div>

          {/* Decoupled Confidence */}
          <div className="rounded-xl border border-[#2A2E35] bg-[#15171B] p-5 space-y-4">
            <div className="text-xs font-mono font-bold text-slate-200">Confidence Metrology Gauge (Decoupled)</div>
            <div className="flex flex-col gap-2.5">
              <ConfidenceGauge level="high" />
              <ConfidenceGauge level="medium" />
              <ConfidenceGauge level="low" />
            </div>
            <p className="text-[11px] text-slate-400 font-sans">
              Confidence measures deterministic verification certainty, never styled like a severity alert.
            </p>
          </div>
        </div>
      </section>

      {/* Signature Interactive Moments */}
      <section className="space-y-4">
        <h2 className="font-mono text-xs font-bold uppercase tracking-wider text-slate-300">
          04 / Signature Interactive Moments (The Verdict & Odometer)
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Odometer */}
          <div className="rounded-xl border border-[#2A2E35] bg-[#15171B] p-6 flex flex-col items-center justify-center text-center">
            <div className="text-[10px] font-mono text-slate-500 uppercase tracking-widest mb-2">
              Odometer Rolling Verdict Numeral
            </div>
            <div className="text-6xl font-mono font-black text-slate-100 flex items-baseline">
              <OdometerNumeral value={odometerScore} />
              <span className="text-2xl text-slate-500 font-normal">/100</span>
            </div>
            <button
              onClick={() => setOdometerScore(Math.floor(Math.random() * 40) + 60)}
              className="mt-4 flex items-center gap-1.5 rounded border border-[#2A2E35] bg-[#0A0B0D] px-3 py-1 text-xs font-mono text-laser-lime hover:border-laser-lime/40 transition"
            >
              <RefreshCw className="w-3 h-3" /> Re-roll Score
            </button>
          </div>

          {/* Stamped Risk Seal */}
          <div className="rounded-xl border border-[#2A2E35] bg-[#15171B] p-6 flex flex-col items-center justify-center">
            <div className="flex gap-2 mb-4">
              {['CRITICAL', 'HIGH', 'MODERATE', 'LOW'].map((t) => (
                <button
                  key={t}
                  onClick={() => setSelectedTier(t)}
                  className={`px-2 py-0.5 rounded text-[10px] font-mono border transition ${
                    selectedTier === t ? 'border-laser-lime text-laser-lime bg-laser-lime/10' : 'border-[#2A2E35] text-slate-400'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
            <VerdictSeal
              tier={selectedTier}
              isCapped={selectedTier === 'CRITICAL'}
              capReason="Plaintext AWS signing credentials detected in config.py:12"
            />
          </div>
        </div>
      </section>

      {/* Evidence Citation */}
      <section className="space-y-4">
        <h2 className="font-mono text-xs font-bold uppercase tracking-wider text-slate-300">
          05 / Monospace AST Code Citation
        </h2>
        <div className="rounded-xl border border-[#2A2E35] bg-[#15171B] p-5">
          <EvidenceCitation
            file="backend/app/auth/tokens.py"
            line={84}
            ruleId="SEC-004"
            onInspect={() => alert('Inspector drawer trigger')}
          />
        </div>
      </section>

      {/* Trust Strip Specimen */}
      <section className="space-y-4">
        <h2 className="font-mono text-xs font-bold uppercase tracking-wider text-slate-300">
          06 / Trust & Safety Strip
        </h2>
        <TrustStrip />
      </section>
    </div>
  )
}
