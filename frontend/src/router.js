import { useEffect, useState } from 'react'

/** Minimal hash router — keeps the SPA static-host-friendly (no rewrite rules). */

export function useHashRoute() {
  const [hash, setHash] = useState(window.location.hash || '#/')
  useEffect(() => {
    const onChange = () => setHash(window.location.hash || '#/')
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return hash
}

export function parseRoute(hash) {
  const raw = hash.replace(/^#/, '') || '/'
  const [pathPart, queryPart] = raw.split('?')
  const params = new URLSearchParams(queryPart || '')
  const parts = pathPart.split('/').filter(Boolean)

  if (parts.length === 0) {
    return { name: 'audit', inspectId: params.get('inspect') || '' }
  }
  if (parts[0] === 'audit') {
    return { name: 'audit', inspectId: params.get('inspect') || '' }
  }
  if (parts[0] === 'ingest') {
    return { name: 'ingest' }
  }
  if (parts[0] === 'design-system') {
    return { name: 'design-system' }
  }
  // Legacy deep-links seamlessly fold into Audit Cockpit inspection
  if (parts[0] === 'c' && parts[1]) {
    return {
      name: 'audit',
      inspectId: parts[1],
      tab: parts[2] === 'impact' ? 'blast' : 'deps',
    }
  }
  if (parts[0] === 'path') {
    return {
      name: 'audit',
      inspectId: params.get('from') || '',
      pathTo: params.get('to') || '',
      tab: 'path',
    }
  }
  return { name: 'audit', inspectId: params.get('inspect') || '' }
}

export const href = {
  audit: (inspectId) => (inspectId ? `#/audit?inspect=${encodeURIComponent(inspectId)}` : '#/audit'),
  ingest: () => '#/ingest',
  component: (id) => `#/audit?inspect=${encodeURIComponent(id)}`,
  impact: (id) => `#/audit?inspect=${encodeURIComponent(id)}&tab=blast`,
  path: (from, to) => `#/audit?inspect=${encodeURIComponent(from || '')}&to=${encodeURIComponent(to || '')}&tab=path`,
}

export function navigate(to) {
  window.location.hash = to
}
