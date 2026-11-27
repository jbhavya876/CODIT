import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * REST client for Codit — Assurance Layer for AI-Written Code & Architecture Platform.
 */

const API_BASE = import.meta.env.VITE_API_BASE || ''

async function request(path, options = {}) {
  let res
  const url = `${API_BASE}/api${path}`
  try {
    res = await fetch(url, options)
  } catch {
    throw { status: 0, code: 'network_error', message: 'Unable to reach the server.' }
  }
  let body = null
  try {
    body = await res.json()
  } catch {
    /* non-JSON body */
  }
  if (!res.ok) {
    throw {
      status: res.status,
      code: body?.error?.code || 'error',
      message: body?.error?.message || `Request failed (${res.status}).`,
      payment_requirements: body?.payment_requirements || null,
    }
  }
  return body
}

const qs = (params) => {
  const p = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') p.set(k, v)
  })
  const s = p.toString()
  return s ? `?${s}` : ''
}

export const api = {
  // --- Core Health & Graph Endpoints ---
  health: () => request('/health'),
  stats: () => request('/stats'),
  search: (q, opts = {}) => request(`/components${qs({ q, type: opts.type, limit: opts.limit })}`),
  component: (id) => request(`/components/${id}`),
  dependencies: (id) => request(`/components/${id}/dependencies`),
  impact: (id) => request(`/components/${id}/impact`),
  criticality: (id) => request(`/components/${id}/criticality`),
  leaderboard: (limit = 8) => request(`/criticality${qs({ limit })}`),
  path: (from, to) => request(`/path${qs({ from, to })}`),

  // --- One-Shot Audits API (Section 10) ---
  createAuditJson: (payload) =>
    request('/audits', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  createAuditZip: (formData) =>
    request('/audits', {
      method: 'POST',
      body: formData,
    }),
  getAudit: (auditId) => request(`/audits/${encodeURIComponent(auditId)}`),
  getAuditEvents: (auditId, after = 0) =>
    request(`/audits/${encodeURIComponent(auditId)}/events${qs({ after })}`),
  getAuditFindings: (auditId, params = {}) =>
    request(`/audits/${encodeURIComponent(auditId)}/findings${qs(params)}`),
  getAuditProcess: (auditId) => request(`/audits/${encodeURIComponent(auditId)}/process`),
  getAuditLicenses: (auditId) => request(`/audits/${encodeURIComponent(auditId)}/licenses`),
  getProfileReport: (auditId, { profile = 'technical', hourlyRate = '', paymentSignature = '' } = {}) =>
    request(
      `/audits/${encodeURIComponent(auditId)}/report${qs({
        profile,
        format: 'json',
        hourly_rate: hourlyRate,
      })}`,
      paymentSignature ? { headers: { 'PAYMENT-SIGNATURE': paymentSignature } } : {}
    ),
  getProfileReportUrl: (auditId, { profile = 'technical', format = 'html', hourlyRate = '' } = {}) =>
    `${API_BASE}/api/audits/${encodeURIComponent(auditId)}/report${qs({
      profile,
      format,
      hourly_rate: hourlyRate,
    })}`,
  deleteAudit: (auditId) =>
    fetch(`${API_BASE}/api/audits/${encodeURIComponent(auditId)}`, { method: 'DELETE' }),

  // --- Attestations (Section 10) ---
  createAttestChallenge: (repo) =>
    request('/attest/challenge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo }),
    }),
  issueAttestation: (auditId, { consentPublish = true, paymentSignature = '' } = {}) =>
    request(`/audits/${encodeURIComponent(auditId)}/attest`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(paymentSignature ? { 'PAYMENT-SIGNATURE': paymentSignature } : {}),
      },
      body: JSON.stringify({ consent_publish: Boolean(consentPublish) }),
    }),
  getPublicAttestation: (attId) => request(`/attest/${encodeURIComponent(attId)}`),

  // --- Legacy Endpoints (Preserved via signed-cookie wrapper) ---
  ingestStatus: () => request('/ingest/status'),
  ingestPublic: (url, ref = 'main') =>
    request('/ingest/public', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, ref }),
    }),
  ingestPrivate: (repo, token, branch) =>
    request('/ingest/private', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo, token, branch }),
    }),
  ingestZip: (formData) =>
    request('/ingest/zip', {
      method: 'POST',
      body: formData,
    }),
  runAnalysis: (goal = 'production') =>
    request('/analyze/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ goal }),
    }),
  getReport: () => request('/report'),
  getBlastRadiusDiagram: (id) => request(`/report/diagram/impact/${encodeURIComponent(id)}`),
  getMarkdownReportUrl: () => `${API_BASE}/api/report/markdown`,
  getHtmlReportUrl: () => `${API_BASE}/api/report/html`,

  // x402 Algorand payment flow
  paymentRequirements: () => request('/payments/requirements'),
  paidReport: (paymentSignature) =>
    request('/payments/report', {
      headers: { 'PAYMENT-SIGNATURE': paymentSignature },
    }),
}

export function useFetch(fn, deps = []) {
  const [state, setState] = useState({ data: null, loading: true, error: null })
  const fnRef = useRef(fn)
  fnRef.current = fn

  const run = useCallback(() => {
    let cancelled = false
    setState({ data: null, loading: true, error: null })
    fnRef.current()
      .then((data) => !cancelled && setState({ data, loading: false, error: null }))
      .catch((error) => !cancelled && setState({ data: null, loading: false, error }))
    return () => {
      cancelled = true
    }
  }, deps) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(run, [run])
  return { ...state, refetch: run }
}

export function useDebounced(value, delay = 200) {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return v
}
