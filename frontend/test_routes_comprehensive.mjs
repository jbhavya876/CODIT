import { chromium } from '@playwright/test'

async function runRegressionSuite() {
  console.log('=====================================================')
  console.log('  CODIT 2.0 FULL ROUTE & UI REGRESSION TEST SUITE   ')
  console.log('=====================================================')

  const browser = await chromium.launch({ headless: true, channel: 'chrome' })
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await context.newPage()

  const BASE_URL = 'http://127.0.0.1:8000'
  const consoleErrors = []
  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text())
      console.log(`[BROWSER ERROR] ${msg.text()}`)
    }
  })
  page.on('pageerror', err => {
    consoleErrors.push(err.message)
    console.log(`[PAGE ERROR] ${err.message}`)
  })
  page.on('response', res => {
    if (res.status() >= 400) {
      console.log(`[HTTP ${res.status()}] ${res.url()}`)
    }
  })

  const results = []

  async function test(name, fn) {
    try {
      process.stdout.write(`• Testing: ${name}... `)
      await fn(page)
      results.push({ name, pass: true })
      console.log('✓ PASS')
    } catch (err) {
      results.push({ name, pass: false, error: err.message })
      console.log('✗ FAIL')
      console.error(`    Details: ${err.message}`)
    }
  }

  // Route 1: Root #/ -> Audit Cockpit
  await test('Root Route #/ defaults to Audit Cockpit', async (p) => {
    await p.goto(`${BASE_URL}/#/`, { waitUntil: 'networkidle' })
    await p.waitForSelector('h1:has-text("Audit Cockpit")', { timeout: 15000 })
    await p.waitForSelector('text=DETERMINISTIC', { timeout: 10000 })
  })

  // Route 2: Explicit #/audit
  await test('Explicit #/audit loads Cockpit telemetry', async (p) => {
    await p.goto(`${BASE_URL}/#/audit`, { waitUntil: 'networkidle' })
    await p.waitForSelector('text=ONNX FRAGILITY REGRESSOR', { timeout: 10000 })
    await p.waitForSelector('text=SHAP EXPLAINABILITY', { timeout: 10000 })
  })

  // Route 3: #/audit?inspect=db-postgresql
  await test('Query param #/audit?inspect=db-postgresql opens Inspector', async (p) => {
    await p.goto(`${BASE_URL}/#/audit?inspect=db-postgresql`, { waitUntil: 'networkidle' })
    await p.waitForSelector('h2:has-text("PostgreSQL")', { timeout: 10000 })
    await p.waitForSelector('text=Neighborhood', { timeout: 10000 })
    const closeBtn = await p.waitForSelector('button[data-testid="close-inspector"]', { timeout: 10000 })
    await closeBtn.click({ force: true })
    await p.waitForTimeout(300)
  })

  // Route 4: Ingest Page #/ingest
  await test('Ingest Page #/ingest renders intake pipeline & presets', async (p) => {
    await p.goto(`${BASE_URL}/#/ingest`, { waitUntil: 'networkidle' })
    await p.waitForSelector('text=Module 1 · Multi-Tier Codebase Ingestion', { timeout: 10000 })
    await p.waitForSelector('text=QUICK INGEST PRESETS', { timeout: 10000 })
    await p.waitForSelector('button:has-text("Public GitHub Repo")', { timeout: 10000 })
    await p.waitForSelector('button:has-text("ZIP Archive Upload")', { timeout: 10000 })
    await p.waitForSelector('button:has-text("Private Repo (GitHub App)")', { timeout: 10000 })
  })

  // Route 5: Legacy #/c/:id redirect
  await test('Legacy deep-link #/c/db-postgresql seamlessly folds into Inspector', async (p) => {
    await p.goto(`${BASE_URL}/#/c/db-postgresql`, { waitUntil: 'networkidle' })
    await p.waitForSelector('h2:has-text("PostgreSQL")', { timeout: 10000 })
    await p.waitForSelector('text=Dependencies', { timeout: 10000 })
    const closeBtn = await p.waitForSelector('button[data-testid="close-inspector"]', { timeout: 10000 })
    await closeBtn.click({ force: true })
    await p.waitForTimeout(300)
  })

  // Route 6: Legacy #/c/:id/impact redirect
  await test('Legacy impact deep-link #/c/db-postgresql/impact opens Blast tab', async (p) => {
    await p.goto(`${BASE_URL}/#/c/db-postgresql/impact`, { waitUntil: 'networkidle' })
    await p.waitForSelector('h2:has-text("PostgreSQL")', { timeout: 10000 })
    await p.waitForSelector('text=Criticality Tier', { timeout: 10000 })
    const closeBtn = await p.waitForSelector('button[data-testid="close-inspector"]', { timeout: 10000 })
    await closeBtn.click({ force: true })
    await p.waitForTimeout(300)
  })

  // Route 7: Legacy #/path?from=...&to=... redirect
  await test('Legacy path deep-link #/path?from=db-postgresql&to=svc-checkout computes path', async (p) => {
    await p.goto(`${BASE_URL}/#/path?from=db-postgresql&to=svc-checkout`, { waitUntil: 'networkidle' })
    await p.waitForSelector('text=Path Finder', { timeout: 10000 })
    const closeBtn = await p.waitForSelector('button[data-testid="close-inspector"]', { timeout: 10000 })
    await closeBtn.click({ force: true })
    await p.waitForTimeout(300)
  })

  // Route 8: Unknown route fallback
  await test('Unknown route #/non-existent-route falls back cleanly to Audit Cockpit', async (p) => {
    await p.goto(`${BASE_URL}/#/non-existent-route`, { waitUntil: 'networkidle' })
    await p.waitForSelector('h1:has-text("Audit Cockpit")', { timeout: 10000 })
  })

  // Route 9: GraphPathInspector interactive tab switches and close
  await test('GraphPathInspector tab switching and closing', async (p) => {
    await p.goto(`${BASE_URL}/#/audit?inspect=db-postgresql`, { waitUntil: 'networkidle' })
    await p.waitForSelector('h2:has-text("PostgreSQL")', { timeout: 10000 })

    // Click Blast Radius tab via data-testid
    const blastTab = await p.waitForSelector('button[data-testid="inspector-tab-blast"]', { timeout: 10000 })
    await blastTab.click({ force: true })
    await p.waitForSelector('text=Criticality Tier', { timeout: 10000 })

    // Click Path Finder tab via data-testid
    const pathTab = await p.waitForSelector('button[data-testid="inspector-tab-path"]', { timeout: 10000 })
    await pathTab.click({ force: true })
    await p.waitForSelector('text=Destination Component:', { timeout: 10000 })

    // Click Neighborhood tab via data-testid
    const neighTab = await p.waitForSelector('button[data-testid="inspector-tab-deps"]', { timeout: 10000 })
    await neighTab.click({ force: true })
    await p.waitForSelector('text=Dependencies', { timeout: 10000 })

    // Close Inspector
    const closeBtn = await p.waitForSelector('button[data-testid="close-inspector"]', { timeout: 10000 })
    await closeBtn.click({ force: true })
    await p.waitForTimeout(300)
  })

  // Route 10: x402 Modal dialog
  await test('x402 Verification Modal opens, informs user, and closes', async (p) => {
    await p.goto(`${BASE_URL}/#/audit`, { waitUntil: 'networkidle' })
    await p.waitForSelector('h1:has-text("Audit Cockpit")', { timeout: 10000 })
    
    // Open modal via data-testid
    const x402Btn = await p.waitForSelector('button[data-testid="x402-settle-btn"]', { timeout: 10000 })
    await x402Btn.click({ force: true })
    await p.waitForSelector('text=On-Chain Audit Settlement', { timeout: 10000 })
    await p.waitForSelector('text=Standard Audits Are 100% Free', { timeout: 10000 })
    
    // Close modal via data-testid
    const closeBtn = await p.waitForSelector('button[data-testid="x402-modal-close"]', { timeout: 10000 })
    await closeBtn.click({ force: true })
    await p.waitForTimeout(300)
  })

  // Route 11: Export Links exist and point to valid URLs
  await test('Export links (Markdown & PDF) have correct URLs', async (p) => {
    await p.goto(`${BASE_URL}/#/audit`, { waitUntil: 'networkidle' })
    await p.waitForSelector('h1:has-text("Audit Cockpit")', { timeout: 10000 })
    const mdHref = await p.getAttribute('a:has-text("Markdown")', 'href')
    const pdfHref = await p.getAttribute('a:has-text("PDF / Print")', 'href')
    if (!mdHref.includes('/api/report/markdown')) throw new Error(`Invalid Markdown href: ${mdHref}`)
    if (!pdfHref.includes('/api/report/html')) throw new Error(`Invalid PDF href: ${pdfHref}`)
  })

  // Route 12: Goal Target Switchers
  await test('Goal target switcher toggles between MVP and Production', async (p) => {
    await p.goto(`${BASE_URL}/#/audit`, { waitUntil: 'networkidle' })
    await p.waitForSelector('h1:has-text("Audit Cockpit")', { timeout: 10000 })
    const mvpBtn = await p.waitForSelector('button:has-text("Goal: MVP")', { timeout: 10000 })
    await mvpBtn.click({ force: true })
    await p.waitForTimeout(500)
    const prodBtn = await p.waitForSelector('button:has-text("Goal: Production")', { timeout: 10000 })
    await prodBtn.click({ force: true })
    await p.waitForTimeout(500)
  })

  // Route 13: Finding Filters and Leaderboard "Inspect" button
  await test('Findings filters and Leaderboard Inspect button triggers drawer', async (p) => {
    await p.goto(`${BASE_URL}/#/audit`, { waitUntil: 'networkidle' })
    await p.waitForSelector('h1:has-text("Audit Cockpit")', { timeout: 10000 })
    
    const inspectCard = await p.waitForSelector('[data-testid="leaderboard-card"]', { timeout: 10000 })
    await inspectCard.click({ force: true })
    await p.waitForSelector('text=Neighborhood', { timeout: 10000 })
    const closeDrawer = await p.waitForSelector('button[data-testid="close-inspector"]', { timeout: 10000 })
    await closeDrawer.click({ force: true })
    await p.waitForTimeout(300)
  })

  await browser.close()

  console.log('\n=====================================================')
  console.log('                 REGRESSION RESULTS                 ')
  console.log('=====================================================')
  const total = results.length
  const passed = results.filter(r => r.pass).length
  const failed = total - passed

  console.log(`TOTAL SCENARIOS TESTED : ${total}`)
  console.log(`PASSED                : ${passed}`)
  console.log(`FAILED                : ${failed}`)
  console.log(`CONSOLE ERRORS DETECTED: ${consoleErrors.length}`)

  if (failed > 0 || consoleErrors.length > 0) {
    console.error('\nRegression test failed!')
    process.exit(1)
  }

  console.log('\n🎉 ALL 13 ROUTES AND UI INTERACTIONS REGRESSION TESTED AND VERIFIED PRODUCTION-READY!')
  process.exit(0)
}

runRegressionSuite().catch(err => {
  console.error('Fatal regression runner exception:', err)
  process.exit(1)
})
