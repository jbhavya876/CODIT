import React from 'react'
import X402TestnetPanel from './X402TestnetPanel.jsx'

export default function X402VerificationModal({ isOpen, onClose }) {
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-xl rounded-2xl border border-slate-700 bg-[#0c1220] p-6 shadow-2xl space-y-5">
        <div className="flex items-start justify-between border-b border-slate-800 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-amber-500/20 text-amber-400 text-xs">
                ⛓️
              </span>
              <h3 className="text-base font-bold text-slate-100">
                On-Chain Audit Settlement (Algorand x402)
              </h3>
            </div>
            <p className="mt-1 text-xs text-slate-400">
              Cryptographically verify and anchor your audit report on the Algorand blockchain.
            </p>
          </div>
          <button
            onClick={onClose}
            data-testid="x402-modal-close"
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-slate-100 transition"
            aria-label="Close Verification Modal"
          >
            <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </button>
        </div>

        {/* Free-tier clarity notice per Section 11 */}
        <div className="rounded-xl border border-sky-500/30 bg-sky-950/20 p-3.5 text-xs text-sky-300 space-y-1">
          <div className="font-semibold flex items-center gap-1.5">
            <span>🛡️</span> Standard Audits Are 100% Free & Unlocked
          </div>
          <p className="text-[11px] text-slate-300 leading-relaxed">
            All CODIT audit scorecards, AST findings, blast radius blueprints, and Markdown/PDF exports are completely free by default.
            This Algorand x402 rail is an <strong>optional, additive protocol</strong> for developers wanting immutable on-chain proof of audit settlement via 0.15 USDC micro-payment and GoPlausible facilitator verification.
          </p>
        </div>

        {/* Embedded x402 Panel */}
        <X402TestnetPanel />

        <div className="flex justify-end pt-2">
          <button
            onClick={onClose}
            className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-800 transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
