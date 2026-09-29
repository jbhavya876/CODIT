import React from 'react'
import { AlertOctagon, CheckCircle2, AlertTriangle, ShieldAlert } from 'lucide-react'

/**
 * Stamped Rotating Risk Tier Seal + Hard Cap Ribbon
 */
export default function VerdictSeal({
  tier = 'MODERATE',
  isCapped = false,
  capReason = 'Plaintext secret or critical CVE discovered in codebase',
  className = '',
}) {
  const norm = (tier || 'MODERATE').toUpperCase()

  const tierConfigs = {
    CRITICAL: {
      color: 'text-[#FF4A2B]',
      border: 'border-[#FF4A2B]/80',
      bg: 'bg-[#2A0E0B]/90',
      glow: 'shadow-crit-glow',
      icon: ShieldAlert,
      stampText: 'CRITICAL RISK',
      sub: 'UNFIT FOR PRODUCTION',
    },
    HIGH: {
      color: 'text-[#FFB020]',
      border: 'border-[#FFB020]/80',
      bg: 'bg-[#281805]/90',
      glow: 'shadow-[0_0_25px_-5px_rgba(255,176,32,0.3)]',
      icon: AlertTriangle,
      stampText: 'HIGH RISK',
      sub: 'ELEVATED BLAST HAZARD',
    },
    MODERATE: {
      color: 'text-[#FACC15]',
      border: 'border-[#FACC15]/80',
      bg: 'bg-[#241F06]/90',
      glow: 'shadow-[0_0_20px_-5px_rgba(250,204,21,0.25)]',
      icon: AlertOctagon,
      stampText: 'MODERATE RISK',
      sub: 'REMEDIATION REQUIRED',
    },
    LOW: {
      color: 'text-[#5DE6A8]',
      border: 'border-[#5DE6A8]/80',
      bg: 'bg-[#0B231A]/90',
      glow: 'shadow-[0_0_25px_-5px_rgba(93,230,168,0.3)]',
      icon: CheckCircle2,
      stampText: 'LOW RISK',
      sub: 'PRODUCTION READY',
    },
  }

  const conf = tierConfigs[norm] || tierConfigs.MODERATE
  const Icon = conf.icon

  return (
    <div className={`flex flex-col items-center gap-3 ${className}`}>
      {/* Stamped Seal */}
      <div
        className={`relative flex flex-col items-center justify-center p-3 rounded-full border-2 border-dashed ${conf.border} ${conf.bg} ${conf.glow} animate-stamp w-32 h-32 select-none`}
        style={{ transformOrigin: 'center center' }}
      >
        <div className="absolute inset-1 rounded-full border border-current opacity-20 pointer-events-none" />
        <Icon className={`w-6 h-6 mb-1 ${conf.color}`} />
        <div className={`font-mono text-[11px] font-black tracking-widest uppercase text-center ${conf.color}`}>
          {conf.stampText}
        </div>
        <div className="font-mono text-[8px] uppercase tracking-tighter text-slate-400 mt-0.5 text-center">
          {conf.sub}
        </div>
        <div className="font-mono text-[7px] text-slate-500 mt-0.5 tracking-tight">CODIT VERIFIED</div>
      </div>

      {/* Hard Cap Notice Ribbon */}
      {isCapped && (
        <div className="mt-1 flex items-center gap-2 rounded border border-[#FF4A2B] bg-[#2A0E0B] px-3 py-1.5 font-mono text-xs text-[#FF4A2B] shadow-crit-glow max-w-sm text-center">
          <span className="font-black px-1.5 py-0.5 rounded bg-[#FF4A2B] text-black text-[10px]">
            CAPPED ≤ 25
          </span>
          <span className="text-[11px] text-slate-300 leading-tight text-left">
            {capReason}
          </span>
        </div>
      )}
    </div>
  )
}
