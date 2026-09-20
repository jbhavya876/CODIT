import React, { useState } from 'react'
import algosdk from 'algosdk'
import { api } from '../api.js'
import { usePeraWallet } from '../wallet.js'

const NETWORKS = {
  testnet: {
    label: 'TestNet',
    network: 'algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI=',
    algod: 'https://testnet-api.algonode.cloud',
    explorer: 'https://testnet.explorer.perawallet.app/tx',
  },
  mainnet: {
    label: 'MainNet',
    network: 'algorand:wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=',
    algod: 'https://mainnet-api.algonode.cloud',
    explorer: 'https://explorer.perawallet.app/tx',
  },
}

const configuredNetwork = import.meta.env.VITE_X402_NETWORK || 'mainnet'
const networkConfig = NETWORKS[configuredNetwork] || NETWORKS.mainnet
const ALGORAND_ALGOD = import.meta.env.VITE_ALGORAND_ALGOD_URL || networkConfig.algod

function toBase64(value) {
  const bytes = value instanceof Uint8Array ? value : new TextEncoder().encode(value)
  let binary = ''
  bytes.forEach((byte) => { binary += String.fromCharCode(byte) })
  return btoa(binary)
}

export default function X402TestnetPanel() {
  const wallet = usePeraWallet()
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState(null)
  const [paidReport, setPaidReport] = useState(null)

  const payForReport = async () => {
    setBusy(true)
    setStatus(null)
    try {
      const accountAddress = wallet.connected ? wallet.accountAddress : await wallet.connect()
      if (!accountAddress) throw new Error('Connect Pera Wallet to continue.')
      const requirements = await api.paymentRequirements()
      const accepted = requirements.accepts?.[0]
      if (!accepted || accepted.network !== networkConfig.network) {
        throw new Error(`Backend is not configured for Algorand ${networkConfig.label}.`)
      }

      const algod = new algosdk.Algodv2('', ALGORAND_ALGOD, '')
      const suggestedParams = await algod.getTransactionParams().do()
      const transaction = algosdk.makeAssetTransferTxnWithSuggestedParamsFromObject({
        sender: accountAddress,
        receiver: accepted.payTo,
        assetIndex: Number(accepted.asset),
        amount: Number(accepted.amount),
        suggestedParams,
      })
      const signedTransactions = await wallet.signTransactions([[
        { txn: transaction, signers: [accountAddress] },
      ]])
      const paymentPayload = {
        x402Version: 2,
        resource: requirements.resource,
        accepted,
        payload: {
          paymentIndex: 0,
          paymentGroup: [toBase64(signedTransactions[0])],
        },
        extensions: {},
      }
      const result = await api.paidReport(toBase64(JSON.stringify(paymentPayload)))
      setPaidReport(result)
      setStatus(`Payment settled on Algorand ${networkConfig.label}.`)
    } catch (error) {
      setStatus(error.message || 'TestNet payment was cancelled or failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="mb-6 rounded-xl border border-amber-500/30 bg-amber-950/20 p-4 shadow-lg shadow-amber-950/10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-amber-300">
            <span className="h-2 w-2 rounded-full bg-amber-400" />
            x402 {networkConfig.label} payment
          </div>
          <p className="mt-1 text-sm text-slate-300">Pay for a CODIT audit report with {networkConfig.label} USDC.</p>
          <p className="mt-1 font-mono text-[10px] text-slate-500">ASA {networkConfig.label === 'MainNet' ? '31566704' : '10458941'} · GoPlausible facilitator</p>
        </div>
        <button
          type="button"
          onClick={payForReport}
          disabled={busy}
          className="rounded-lg bg-amber-400 px-4 py-2 text-xs font-bold text-slate-950 transition hover:bg-amber-300 disabled:cursor-wait disabled:opacity-60"
        >
          {busy ? 'Waiting for Pera…' : wallet.connected ? `Pay 0.15 USDC ${networkConfig.label}` : `Connect & Pay ${networkConfig.label}`}
        </button>
      </div>
      {status && <p className={`mt-3 text-xs ${paidReport ? 'text-emerald-300' : 'text-amber-200'}`}>{status}</p>}
      {paidReport?.payment?.transaction && (
        <a
          className="mt-2 inline-block text-xs text-sky-300 underline hover:text-sky-200"
          href={`${networkConfig.explorer}/${paidReport.payment.transaction}`}
          target="_blank"
          rel="noreferrer"
        >
          View transaction {paidReport.payment.transaction.slice(0, 10)}…
        </a>
      )}
    </section>
  )
}
