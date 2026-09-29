import React from 'react'

/**
 * SHAP Accounting Waterfall Ledger
 * Renders game-theoretic feature contributions as an authoritative double-entry accounting waterfall:
 * Baseline -> Line-by-line signals adding or subtracting points -> Final Score.
 */
export default function SHAPLedger({
  shapData = {},
  finalScore = 85,
  isDossier = false,
  className = '',
}) {
  const baseline = shapData.baseline_score ?? 95.0
  const waterfallItems = shapData.waterfall || [
    { name: 'Graph Modularity', shap_value: 0.88, rationale: 'Clean separation between microservice domains' },
    { name: 'Test Coverage Gap', shap_value: -3.5, rationale: 'Missing unit test suites on critical authentication routes' },
    { name: 'Cyclomatic Complexity', shap_value: -1.2, rationale: 'Nested conditionals exceeding threshold in payment dispatch' },
  ]

  let runningScore = baseline

  return (
    <div
      className={`rounded-xl border overflow-hidden font-mono ${
        isDossier
          ? 'border-[#D8D2C5] bg-[#F7F4EE] text-[#101114]'
          : 'border-[#2A2E35] bg-[#15171B] text-slate-200'
      } ${className}`}
    >
      {/* Header */}
      <div
        className={`px-4 py-3 border-b flex items-center justify-between ${
          isDossier ? 'border-[#D8D2C5] bg-[#EFEAE0]' : 'border-[#2A2E35] bg-[#0A0B0D]'
        }`}
      >
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold uppercase tracking-wider">
            SHAP Game-Theoretic Waterfall Ledger
          </span>
          <span
            className={`px-1.5 py-0.2 rounded text-[9px] font-bold ${
              isDossier ? 'bg-[#D8D2C5] text-black' : 'bg-laser-lime/10 text-laser-lime border border-laser-lime/30'
            }`}
          >
            SHAPLEY ATTRIBUTION
          </span>
        </div>
        <div className="text-[10px] text-slate-400">
          Decomposes exact delta from expected baseline to final score
        </div>
      </div>

      {/* Ledger Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr
              className={`border-b text-[10px] uppercase tracking-wider ${
                isDossier ? 'border-[#D8D2C5] bg-[#EAE5DB] text-[#575A65]' : 'border-[#2A2E35] bg-[#0A0B0D]/50 text-slate-400'
              }`}
            >
              <th className="py-2.5 px-4 font-bold">Signal / AST Feature</th>
              <th className="py-2.5 px-4 font-medium hidden md:table-cell">Plain-English Rationale</th>
              <th className="py-2.5 px-4 text-right font-bold">Delta (SHAP)</th>
              <th className="py-2.5 px-4 text-right font-bold">Running Score</th>
            </tr>
          </thead>
          <tbody className={`divide-y ${isDossier ? 'divide-[#D8D2C5]' : 'divide-[#2A2E35]/60'}`}>
            {/* Baseline Entry */}
            <tr className={isDossier ? 'bg-[#F2EFE8]' : 'bg-[#1E2228]/50'}>
              <td className="py-2.5 px-4 font-bold text-slate-100 flex items-center gap-2">
                <span className="text-[10px] text-slate-400">E[f(X)]</span>
                <span className={isDossier ? 'text-[#101114]' : 'text-slate-100'}>Empirical Baseline Expectation</span>
              </td>
              <td className={`py-2.5 px-4 text-[11px] font-sans hidden md:table-cell ${isDossier ? 'text-[#575A65]' : 'text-slate-400'}`}>
                Benchmark expectation for production-ready architecture
              </td>
              <td className="py-2.5 px-4 text-right font-mono font-bold text-slate-400">—</td>
              <td className={`py-2.5 px-4 text-right font-mono font-black tabular-nums ${isDossier ? 'text-[#101114]' : 'text-slate-100'}`}>
                {baseline.toFixed(2)} pts
              </td>
            </tr>

            {/* Line-by-Line Waterfall Steps */}
            {waterfallItems.map((item, idx) => {
              const val = typeof item.shap_value === 'number' ? item.shap_value : parseFloat(item.shap_value) || 0
              runningScore += val
              const isPositive = val >= 0

              return (
                <tr
                  key={idx}
                  className={`transition-colors ${
                    isDossier ? 'hover:bg-[#EAE5DB]/60' : 'hover:bg-[#1E2228]'
                  }`}
                >
                  <td className="py-2.5 px-4 font-medium">
                    <div className="flex items-center gap-2">
                      <span className={`text-[10px] ${isPositive ? 'text-emerald-400' : 'text-[#FF4A2B]'}`}>
                        {isPositive ? '▲' : '▼'}
                      </span>
                      <span className={`truncate max-w-xs ${isDossier ? 'text-[#101114] font-semibold' : 'text-slate-200'}`}>
                        {item.name}
                      </span>
                    </div>
                  </td>
                  <td className={`py-2.5 px-4 text-[11px] font-sans max-w-md ${isDossier ? 'text-[#575A65]' : 'text-slate-400'} hidden md:table-cell`}>
                    {item.rationale}
                  </td>
                  <td className="py-2.5 px-4 text-right font-mono font-bold tabular-nums">
                    <span
                      className={`inline-block px-1.5 py-0.5 rounded text-[10px] ${
                        isPositive
                          ? isDossier ? 'bg-[#ECFDF5] text-[#047857]' : 'bg-[#0B231A] text-[#5DE6A8] border border-[#164E37]'
                          : isDossier ? 'bg-[#FDECEB] text-[#B91C1C]' : 'bg-[#2A0E0B] text-[#FF4A2B] border border-[#5A1C16]'
                      }`}
                    >
                      {isPositive ? `+${val.toFixed(2)}` : val.toFixed(2)}
                    </span>
                  </td>
                  <td className={`py-2.5 px-4 text-right font-mono font-semibold tabular-nums ${isDossier ? 'text-[#101114]' : 'text-slate-300'}`}>
                    {runningScore.toFixed(2)}
                  </td>
                </tr>
              )
            })}

            {/* Final Sum Total Row */}
            <tr className={`border-t-2 font-black ${isDossier ? 'border-[#101114] bg-[#EFEAE0]' : 'border-laser-lime/40 bg-[#0A0B0D]'}`}>
              <td colSpan={2} className="py-3 px-4 uppercase tracking-wider text-xs">
                <div className="flex items-center gap-2">
                  <span className="text-laser-lime">■</span>
                  <span>Final Multi-Dimensional Score Result</span>
                </div>
              </td>
              <td className="py-3 px-4 text-right font-mono text-[11px] text-slate-400">∑ CONTRIBUTIONS</td>
              <td className={`py-3 px-4 text-right font-mono text-sm ${isDossier ? 'text-[#101114]' : 'text-laser-lime'} tabular-nums`}>
                {finalScore} / 100
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}
