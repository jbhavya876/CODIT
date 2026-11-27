import React, { useState } from 'react'
import { api } from '../../api.js'
import { Check, Copy, ShieldCheck, AlertTriangle } from 'lucide-react'

const PUBLIC_FIELDS_DISCLOSURE = [
  'Attestation ID, issued_at, and expires_at timestamps (UTC)',
  'Subject descriptor: verified repository slug + commit/tree SHA, OR archive SHA-256 only (no repo name)',
  'Aggregate coverage counts (files scanned/total, history commits count, license resolution %)',
  'Rubric ID/version (`codit-rubric 2.0.0`), CODIT engine version/revision, and overall + dimensional scores',
  'SHA-256 digest of sorted finding fingerprints (individual findings and source code stay private)',
]

export default function AttestTab({ auditStatus }) {
  const auditId = auditStatus?.audit_id
  const sourceKind = auditStatus?.source_kind || 'zip'
  const isGitSource = sourceKind === 'public' || sourceKind === 'private'
  const repoSlug = isGitSource
    ? String(auditStatus?.source_ref || '').replace(/^https?:\/\/github\.com\//i, '').replace(/\.git$/i, '')
    : ''

  const [challenge, setChallenge] = useState(null)
  const [challengeErr, setChallengeErr] = useState(null)
  const [consentPublish, setConsentPublish] = useState(false)
  const [issuing, setIssuing] = useState(false)
  const [issued, setIssued] = useState(null)
  const [issueErr, setIssueErr] = useState(null)
  const [copiedId, setCopiedId] = useState(null)

  const copyVal = (text, id) => {
    navigator.clipboard?.writeText(text)?.catch(() => {})
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 1600)
  }

  const handleRequestChallenge = async () => {
    setChallengeErr(null)
    try {
      const res = await api.createAttestChallenge(repoSlug)
      setChallenge(res)
    } catch (err) {
      setChallengeErr(err?.message || 'Unable to generate repository-control challenge.')
    }
  }

  const handleIssue = async () => {
    if (!auditId) return
    setIssuing(true)
    setIssueErr(null)
    try {
      const res = await api.issueAttestation(auditId, { consentPublish })
      setIssued(res)
    } catch (err) {
      setIssueErr(err)
    } finally {
      setIssuing(false)
    }
  }

  if (!auditId) {
    return (
      <div className="rounded-xl border border-dashed border-[#2A2E35] p-8 text-center font-mono text-xs text-slate-400">
        No persisted audit selected. Run an audit in Ingest Repo before issuing an attestation.
      </div>
    )
  }

  return (
    <div className="space-y-5" data-testid="attest-tab-panel">
      {/* Step 1: Subject & Control Challenge */}
      <section className="rounded-xl border border-[#2A2E35] bg-[#15171B] p-5 space-y-3 font-mono text-xs">
        <h2 className="text-sm font-bold uppercase tracking-wider text-slate-100">
          Step 1 — Subject Verification Mode
        </h2>
        {isGitSource ? (
          <div className="space-y-3">
            <p className="font-sans text-slate-300">
              Git repository attestations require proof that someone with write access committed a single-use challenge token at <code>.codit/verify</code> before the audit ran.
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <span className="rounded border border-[#2A2E35] bg-[#0A0B0D] px-2.5 py-1 text-slate-200">
                Repository: <strong>{repoSlug}</strong>
              </span>
              <button
                type="button"
                onClick={handleRequestChallenge}
                data-testid="request-challenge-btn"
                className="rounded border border-laser-lime bg-laser-lime/10 px-3 py-1 font-bold text-laser-lime hover:bg-laser-lime hover:text-black transition"
              >
                Generate .codit/verify Challenge
              </button>
            </div>
            {challenge && (
              <div className="rounded-lg border border-laser-lime/40 bg-[#0A0B0D] p-3.5 space-y-2" data-testid="challenge-box">
                <div className="flex items-center justify-between">
                  <span>Commit this exact file to <code>{challenge.file_path}</code> and re-run audit:</span>
                  <button
                    type="button"
                    onClick={() => copyVal(challenge.content, 'challenge')}
                    className="inline-flex items-center gap-1 rounded border border-[#2A2E35] px-2 py-0.5 text-laser-lime"
                  >
                    {copiedId === 'challenge' ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                    <span>{copiedId === 'challenge' ? 'Copied' : 'Copy content'}</span>
                  </button>
                </div>
                <pre className="rounded bg-[#050608] border border-[#2A2E35] p-2 text-slate-200">{challenge.content}</pre>
                <div className="text-[11px] text-slate-400">Expires: {challenge.expires_at}</div>
              </div>
            )}
            {challengeErr && <div className="text-[#FF4A2B]">{challengeErr}</div>}
          </div>
        ) : sourceKind === 'zip' ? (
          <div className="rounded-lg border border-[#2A2E35] bg-[#0A0B0D] p-3 text-slate-300 space-y-1">
            <div className="font-bold text-slate-100">Archive audit — source not verified</div>
            <p className="font-sans text-xs text-slate-400">
              ZIP attestations publish only the archive SHA-256 digest (<code>{String(auditStatus?.source_archive_sha256 || '').slice(0, 16)}...</code>), with <code>control_verified=false</code> and no repository name.
            </p>
          </div>
        ) : (
          <div className="rounded-lg border border-amber-900/60 bg-amber-950/20 p-3 text-[#FFB020]">
            Demo audits cannot receive public attestations. Ingest a repository or ZIP archive first.
          </div>
        )}
      </section>

      {/* Step 2: Public Field Disclosure & Explicit Consent */}
      <section className="rounded-xl border border-[#2A2E35] bg-[#15171B] p-5 space-y-3 font-mono text-xs">
        <h2 className="text-sm font-bold uppercase tracking-wider text-slate-100">
          Step 2 — Public Payload Disclosure &amp; Consent
        </h2>
        <p className="font-sans text-slate-300">
          Publishing an Ed25519 attestation makes only the following fields publicly readable at <code>/v/&lt;id&gt;</code>:
        </p>
        <ul className="list-disc pl-5 space-y-1 font-sans text-slate-300">
          {PUBLIC_FIELDS_DISCLOSURE.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>

        <label className="flex items-start gap-2.5 pt-2 cursor-pointer font-sans text-slate-100">
          <input
            type="checkbox"
            checked={consentPublish}
            onChange={(e) => setConsentPublish(e.target.checked)}
            data-testid="attest-consent-checkbox"
            className="mt-1 accent-[#D4FF3A]"
          />
          <span>I understand and consent to publishing this signed summary payload publicly.</span>
        </label>

        <div>
          <button
            type="button"
            disabled={issuing || sourceKind === 'demo'}
            onClick={handleIssue}
            data-testid="issue-attestation-btn"
            className="rounded-lg border border-laser-lime bg-laser-lime px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider text-black hover:shadow-laser-glow disabled:opacity-50 transition"
          >
            {issuing ? 'Signing Attestation...' : 'Issue Signed Attestation'}
          </button>
        </div>

        {issueErr && (
          <div role="alert" className="rounded border border-[#5A1C16] bg-[#2A0E0B] p-3 text-[#FF4A2B] flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
            <div>
              <strong>{issueErr.code || 'error'}:</strong> {issueErr.message}
            </div>
          </div>
        )}
      </section>

      {/* Step 3: Issued Verification Links & Offline CLI Verify */}
      {issued && (
        <section className="rounded-xl border border-emerald-900/60 bg-emerald-950/20 p-5 space-y-3 font-mono text-xs" data-testid="issued-attestation-panel">
          <div className="flex items-center gap-2 text-[#5DE6A8] font-bold">
            <ShieldCheck className="w-4 h-4" aria-hidden="true" />
            <span>Attestation Issued: {issued.attestation_id}</span>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <a href={issued.verify_path} target="_blank" rel="noreferrer" className="underline text-laser-lime">
              Open Verify Page ({issued.verify_path})
            </a>
            <a href={`/api/attest/${issued.attestation_id}`} target="_blank" rel="noreferrer" className="underline text-slate-200">
              Download Signed JSON
            </a>
          </div>
          <div>
            <div className="text-[11px] text-slate-400 mb-1">Live Badge Preview:</div>
            <img src={issued.badge_path} alt="CODIT verification badge" />
          </div>
          <div>
            <div className="text-[11px] text-slate-400 mb-1">Markdown Badge Embed:</div>
            <pre className="rounded border border-[#2A2E35] bg-[#0A0B0D] p-2 overflow-x-auto text-slate-200">
              {`[![CODIT](${issued.badge_url})](${issued.verify_url})`}
            </pre>
          </div>
          <div>
            <div className="text-[11px] text-slate-400 mb-1">Offline Verification CLI:</div>
            <pre className="rounded border border-[#2A2E35] bg-[#0A0B0D] p-2 overflow-x-auto text-slate-200">
              {`codit-guard attest verify attestation.json --keys ${window.location.origin}/.well-known/codit-keys.json`}
            </pre>
          </div>
        </section>
      )}
    </div>
  )
}
