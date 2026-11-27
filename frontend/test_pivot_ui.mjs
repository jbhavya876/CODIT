import { chromium } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

const BASE_URL = 'http://127.0.0.1:8000'

function assertNoSeriousAxeViolations(results, label) {
  const bad = (results.violations || []).filter((v) => v.impact === 'serious' || v.impact === 'critical')
  if (bad.length > 0) {
    const details = bad.map((b) => ({
      id: b.id,
      impact: b.impact,
      targets: b.nodes.map((n) => ({ target: n.target, html: n.html.slice(0, 120) })),
    }))
    throw new Error(`Axe serious/critical violations on ${label}: ${JSON.stringify(details)}`)
  }
}

async function runPivotUiSuite() {
  console.log('=====================================================')
  console.log('  CODIT 3.0 PIVOT UI + AXE ACCESSIBILITY SUITE       ')
  console.log('=====================================================')

  const browser = process.env.CI
    ? await chromium.launch({ headless: true })
    : await chromium.launch({ headless: true }).catch(() => chromium.launch({ headless: true, channel: 'chrome' }))
  const consoleErrors = []

  try {
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
    const page = await context.newPage()
    page.on('console', (m) => {
      if (m.type() === 'error') consoleErrors.push(m.text())
    })
    page.on('pageerror', (e) => consoleErrors.push(e.message))

    const mockAuditId = 'aud_ui_test_1'
    const mockReport = {
      report_id: 'audit-ui-1',
      audit_id: mockAuditId,
      target_name: 'acme/ui-demo',
      target_type: 'public',
      access_tier: 'free_public',
      created_at: 1700000000,
      rubric_version: '2.0.0',
      scorecard: {
        rubric_version: '2.0.0',
        overall: 74,
        overall_score: 74,
        phase: 'MVP',
        has_critical_blocker: false,
        blockers: [],
        phase_qualifiers: [],
        dimensions: {
          security: { score: 90, assessed: true, findings_count: 1, critical_count: 0, high_count: 0 },
          tests: { score: 80, assessed: true, findings_count: 1, critical_count: 0, high_count: 1 },
          agent_integrity: { score: 60, assessed: true, findings_count: 1, critical_count: 0, high_count: 1 },
          scalability: { score: 90, assessed: true, findings_count: 0, critical_count: 0, high_count: 0 },
          licenses: { score: 70, assessed: true, findings_count: 1, critical_count: 0, high_count: 1 },
          duplication: { score: 95, assessed: true, findings_count: 0, critical_count: 0, high_count: 0 },
          maintainability: { score: 95, assessed: true, findings_count: 0, critical_count: 0, high_count: 0 },
        },
      },
      findings: [
        {
          id: 'agt-1',
          rule_id: 'AGT-001',
          dimension: 'agent_integrity',
          severity: 'high',
          confidence: 'high',
          basis: 'HISTORY PROOF',
          evidence_file: 'tests/test_auth.py',
          evidence_line: 12,
          commit_sha: '1111111111111111111111111111111111111111',
          fingerprint: 'fp_agt_1',
          description: 'Removed test_auth_bypass in commit modifying auth module.',
          remediation: 'Restore regression test coverage.',
        },
      ],
      roadmap: { goal: 'production', summary_narrative: 'Fix high items.', blockers_summary: 'None', phases: [] },
      architecture_diagram_mermaid: 'flowchart TD\nA-->B\n',
      criticality_leaderboard: [],
      stats: {},
      ml_insights: { onnx_metrics: { fragility_score: 0.32, defect_risk_tier: 'Moderate' }, shap_explainability: { baseline_score: 95, attributions: [] } },
      effort: { effort_model_version: '1.0.0', person_days: { min: 1, likely: 2, max: 4 }, hours: { min: 8, likely: 16, max: 32 } },
    }

    await page.route('**/api/health', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'ok',
          mode: 'demo',
          runtime_posture: {
            lines_executed: 0,
            zip_guards_active: true,
            sandbox_isolated: false,
            walltime_seconds: 180,
            memory_limit_mb: 1024,
            source_retention_seconds: 0,
            results_retention_hours: 24,
          },
        }),
      })
    })

    let pollCount = 0
    await page.route('**/api/audits', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 202,
          contentType: 'application/json',
          body: JSON.stringify({ audit_id: mockAuditId, status: 'queued' }),
        })
      } else {
        await route.continue()
      }
    })

    await page.route(`**/api/audits/${mockAuditId}`, async (route) => {
      pollCount += 1
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          audit_id: mockAuditId,
          status: 'completed',
          stage: 'deliver',
          source_kind: 'public',
          source_ref: 'https://github.com/acme/ui-demo',
          rubric_version: '2.0.0',
          coverage: { files_scanned: 14, files_total: 14, history: { assessed: true, commits_analyzed: 18 } },
          scorecard: mockReport.scorecard,
        }),
      })
    })

    await page.route(`**/api/audits/${mockAuditId}/events*`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(
          pollCount <= 1
            ? [
                { id: 1, ts: '2026-11-27T00:00:00Z', stage: 'ingest', level: 'info', code: 'ingest_started', data: {} },
                { id: 2, ts: '2026-11-27T00:00:01Z', stage: 'history', level: 'info', code: 'history_done', data: { commits: 18 } },
                { id: 3, ts: '2026-11-27T00:00:02Z', stage: 'deliver', level: 'info', code: 'report_ready', data: {} },
              ]
            : []
        ),
      })
    })

    await page.route(`**/api/audits/${mockAuditId}/process`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          assessed: true,
          coverage: { assessed: true, commits_analyzed: 18 },
          head_tooling_present: true,
          attribution: { total_commits: 18, declared_commits: 6, declared_fraction: 0.33 },
          series: [
            { bucket: '2026-W01', tests_end: 8, assertions_end: 20, skipped_end: 0, commits: 10 },
            { bucket: '2026-W02', tests_end: 7, assertions_end: 18, skipped_end: 1, commits: 8 },
          ],
          flagged_commits: [
            { sha: '1111111111111111111111111111111111111111', short: '1111111', date: '2026-11-20T00:00:00Z', attribution_basis: 'trailer' },
            { sha: '2222222222222222222222222222222222222222', short: '2222222', date: '2026-11-22T00:00:00Z', attribution_basis: 'unknown' },
          ],
        }),
      })
    })

    await page.route(`**/api/audits/${mockAuditId}/licenses`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          disclaimer: 'Automated license classification. Not legal advice. Verify with counsel before relying on it.',
          project_license: { spdx_id: 'MIT', license_class: 'permissive' },
          coverage: { total: 2, resolved: 2, unresolved: 0, resolved_pct: 100 },
          register: [
            { package: 'gpl-lib', version: '1.0.0', ecosystem: 'npm', scope: 'prod', spdx_id: 'GPL-3.0-only', license_class: 'strong_copyleft', rule_id: 'LIC-001', evidence_file: 'package-lock.json', evidence_line: 10 },
            { package: 'ms', version: '2.1.3', ecosystem: 'npm', scope: 'prod', spdx_id: 'MIT', license_class: 'permissive', rule_id: null, evidence_file: 'package-lock.json', evidence_line: 20 },
          ],
        }),
      })
    })

    await page.route(`**/api/audits/${mockAuditId}/report*`, async (route) => {
      const url = new URL(route.request().url())
      const prof = url.searchParams.get('profile') || 'technical'
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(
          prof === 'underwriting'
            ? { schema: 'codit.underwriting.v1', scores: { overall: 74, phase: 'MVP' } }
            : prof === 'executive'
            ? { profile: 'executive', rubric_version: '2.0.0', verdict_seal: { overall_score: 74, phase: 'MVP' }, themes: [{ title: 'Process Risk', rationale: '1 high event' }], actions: [{ text: 'Restore test', finding_ids: ['agt-1'] }], what_this_does_not_cover: ['Runtime execution'], methodology: 'Static analysis.' }
            : prof === 'diligence'
            ? { profile: 'diligence', rubric_version: '2.0.0', verdict_and_coverage: { overall_score: 74, phase: 'MVP', coverage: { files_scanned: 14, files_total: 14 }, not_assessed: [] }, red_flag_register: [], ip_and_licensing_register: { disclaimer: 'Automated license classification. Not legal advice. Verify with counsel before relying on it.' }, process_integrity_timeline: { assessed: true, attribution_limitation: 'Attribution reflects declarations in commit metadata.' }, key_person_exposure: { assessed: false, status_text: 'Not assessed' }, remediation_estimate: { person_days: { min: 1, likely: 2, max: 4 } }, methodology_and_limitations: { methodology: 'Static analysis.' } }
            : { profile: 'technical', rubric_version: '2.0.0', scorecard: mockReport.scorecard, effort: mockReport.effort, methodology: 'Static analysis.', process: { assessed: true, coverage: { commits_analyzed: 18 } }, licenses: { disclaimer: 'Automated license classification. Not legal advice. Verify with counsel before relying on it.' } }
        ),
      })
    })

    await page.route('**/api/attest/challenge', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ repo: 'acme/ui-demo', nonce: 'testnonce123', file_path: '.codit/verify', content: 'codit-verify=testnonce123\n', expires_at: '2026-12-01T00:00:00Z' }),
      })
    })

    await page.route('**/api/report', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(mockReport) })
    })

    // 1. TrustStrip honesty snapshot + Ingest one-shot flow
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto(`${BASE_URL}/#/ingest`, { waitUntil: 'networkidle' })
    const stripText = await page.getByTestId('trust-strip').innerText()
    if (!stripText.includes('0 lines executed') || stripText.includes('Ephemeral Sandbox') || !stripText.includes('Static analysis only')) {
      throw new Error(`TrustStrip text failed honesty check: ${stripText}`)
    }
    assertNoSeriousAxeViolations(await new AxeBuilder({ page }).analyze(), 'Ingest Page')

    await page.click('button:has-text("Last 100 commits")')
    await page.click('button:has-text("Start Audit")')
    await page.waitForSelector('text=AUDIT COMPLETE', { timeout: 10000 })
    await page.click('button:has-text("Open Audit Cockpit")')
    await page.waitForSelector('h1:has-text("Audit Cockpit")', { timeout: 10000 })
    assertNoSeriousAxeViolations(await new AxeBuilder({ page }).analyze(), 'Audit Cockpit Overview')

    // 2. Process Tab: Integrity Ledger keyboard navigation + table toggle + attribution limitation
    await page.getByTestId('audit-subtab-process').click()
    await page.waitForSelector('[data-testid="process-coverage-banner"]', { timeout: 10000 })
    await page.waitForSelector('text=Attribution reflects declarations in commit metadata', { timeout: 10000 })
    const marker0 = page.getByTestId('ledger-marker-0')
    await marker0.focus()
    await page.keyboard.press('Enter')
    await page.waitForSelector('[data-testid="commit-detail-panel"]', { timeout: 10000 })
    await page.keyboard.press('ArrowRight')
    assertNoSeriousAxeViolations(await new AxeBuilder({ page }).analyze(), 'Process Tab (Chart)')

    await page.getByTestId('ledger-view-toggle').click()
    await page.waitForSelector('table th:has-text("Commit")', { timeout: 10000 })

    // 3. Licenses Tab + filter
    await page.getByTestId('audit-subtab-licenses').click()
    await page.waitForSelector('[data-testid="license-coverage-line"]', { timeout: 10000 })
    await page.selectOption('[data-testid="license-class-filter"]', 'strong_copyleft')
    await page.waitForSelector('text=gpl-lib', { timeout: 10000 })
    assertNoSeriousAxeViolations(await new AxeBuilder({ page }).analyze(), 'Licenses Tab')

    // 4. Reports Tab + ProfileSwitcher
    await page.getByTestId('audit-subtab-reports').click()
    await page.getByTestId('profile-switch-diligence').click()
    await page.waitForSelector('text=Due Diligence Technical', { timeout: 10000 })
    await page.getByTestId('profile-switch-underwriting').click()
    await page.waitForSelector('text=codit.underwriting.v1', { timeout: 10000 })
    assertNoSeriousAxeViolations(await new AxeBuilder({ page }).analyze(), 'Reports Tab')

    // 5. Attest Tab + challenge step + consent
    await page.getByTestId('audit-subtab-attest').click()
    await page.getByTestId('request-challenge-btn').click()
    await page.waitForSelector('[data-testid="challenge-box"]', { timeout: 10000 })
    await page.waitForSelector('text=codit-verify=testnonce123', { timeout: 10000 })
    assertNoSeriousAxeViolations(await new AxeBuilder({ page }).analyze(), 'Attest Tab')

    // 6. Guard Drawer + copy
    await page.getByTestId('open-guard-drawer-btn').click()
    await page.waitForSelector('text=Only the CI check, set as a required status check, is authoritative.', { timeout: 10000 })
    await page.getByTestId('copy-guard-claude').click()
    assertNoSeriousAxeViolations(await new AxeBuilder({ page }).analyze(), 'Guard Drawer')
    await page.getByTestId('close-guard-drawer').click()

    // 7. Mobile 360px responsive layout & table default check on Process tab
    await page.setViewportSize({ width: 360, height: 740 })
    await page.goto(`${BASE_URL}/#/audit?tab=process&id=${mockAuditId}`, { waitUntil: 'networkidle' })
    await page.waitForSelector('table th:has-text("Commit")', { timeout: 10000 })

    // 8. Non-assessed state check
    await page.route(`**/api/audits/${mockAuditId}/process`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          assessed: false,
          reason: 'zip_without_git',
          status_text: 'Not assessed — archive upload contained no .git history directory.',
        }),
      })
    })
    await page.reload({ waitUntil: 'networkidle' })
    await page.waitForSelector('text=Not assessed — archive upload contained no .git history directory.', { timeout: 10000 })

    if (consoleErrors.length > 0) {
      throw new Error(`Console/page errors detected: ${consoleErrors.join('; ')}`)
    }
    console.log('✓ ALL PIVOT UI + AXE + RESPONSIVE CHECKS PASSED!')
  } finally {
    await browser.close()
  }
}

runPivotUiSuite().catch((err) => {
  console.error(err)
  process.exit(1)
})
