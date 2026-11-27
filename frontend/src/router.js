import { useEffect, useState } from 'react'

/** Minimal hash router keeping the strict two-pillar IA (`audit` and `ingest`). */

export function useHashRoute() {
  const [hash, setHash] = useState(window.location.hash || '#/')
  useEffect(() => {
    const onChange = () => setHash(window.location.hash || '#/')
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return hash
}

const VALID_AUDIT_TABS = new Set(['overview', 'process', 'licenses', 'reports', 'attest'])

export function parseRoute(hash) {
  const raw = hash.replace(/^#/, '') || '/'
  const [pathPart, queryPart] = raw.split('?')
  const params = new URLSearchParams(queryPart || '')
  const parts = pathPart.split('/').filter(Boolean)

  const rawTab = (params.get('tab') || '').toLowerCase()
  const auditTab = VALID_AUDIT_TABS.has(rawTab) ? rawTab : 'overview'
  const auditId = params.get('id') || ''

  if (parts.length === 0) {
    return { name: 'audit', inspectId: params.get('inspect') || '', auditTab, auditId }
  }
  if (parts[0] === 'audit') {
    return { name: 'audit', inspectId: params.get('inspect') || '', auditTab, auditId }
  }
  if (parts[0] === 'ingest') {
    return { name: 'ingest' }
  }
  if (parts[0] === 'design-system') {
    return { name: 'design-system' }
  }
  // Legacy deep-links seamlessly fold into Audit Cockpit GraphPathInspector drawer
  if (parts[0] === 'c' && parts[1]) {
    return {
      name: 'audit',
      inspectId: parts[1],
      tab: parts[2] === 'impact' ? 'blast' : 'deps',
      auditTab: 'overview',
      auditId,
    }
  }
  if (parts[0] === 'path') {
    return {
      name: 'audit',
      inspectId: params.get('from') || '',
      pathTo: params.get('to') || '',
      tab: 'path',
      auditTab: 'overview',
      auditId,
    }
  }
  return { name: 'audit', inspectId: params.get('inspect') || '', auditTab, auditId }
}

export const href = {
  audit: (inspectId, extra = {}) => {
    const p = new URLSearchParams()
    if (inspectId) p.set('inspect', inspectId)
    if (extra.tab && extra.tab !== 'overview') p.set('tab', extra.tab)
    if (extra.id) p.set('id', extra.id)
    const s = p.toString()
    return s ? `#/audit?${s}` : '#/audit'
  },
  auditTab: (tab, id = '') => {
    const p = new URLSearchParams()
    if (tab && tab !== 'overview') p.set('tab', tab)
    if (id) p.set('id', id)
    const s = p.toString()
    return s ? `#/audit?${s}` : '#/audit'
  },
  ingest: () => '#/ingest',
  component: (id) => `#/audit?inspect=${encodeURIComponent(id)}`,
  impact: (id) => `#/audit?inspect=${encodeURIComponent(id)}&tab=blast`,
  path: (from, to) => `#/audit?inspect=${encodeURIComponent(from || '')}&to=${encodeURIComponent(to || '')}&tab=path`,
}

export function navigate(to) {
  window.location.hash = to
}
