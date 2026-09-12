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

  if (parts.length === 0) return { name: 'dashboard' }
  if (parts[0] === 'audit') return { name: 'audit' }
  if (parts[0] === 'ingest') return { name: 'ingest' }
  if (parts[0] === 'c' && parts[1] && parts[2] === 'impact')
    return { name: 'impact', id: parts[1] }
  if (parts[0] === 'c' && parts[1])
    return { name: 'component', id: parts[1], action: params.get('path') }
  if (parts[0] === 'path')
    return { name: 'path', from: params.get('from') || '', to: params.get('to') || '' }
  return { name: 'dashboard' }
}

export const href = {
  dashboard: () => '#/',
  audit: () => '#/audit',
  ingest: () => '#/ingest',
  component: (id) => `#/c/${id}`,
  impact: (id) => `#/c/${id}/impact`,
  path: (from, to) => `#/path?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
}

export function navigate(to) {
  window.location.hash = to
}
