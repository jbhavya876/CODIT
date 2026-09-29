import { chromium } from '@playwright/test'
import path from 'path'
import fs from 'fs'

async function captureArtifacts() {
  const outDir = path.resolve('..', 'docs', 'screenshots_forensic')
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true })
  }

  const browser = await chromium.launch({ headless: true, channel: 'chrome' })
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await context.newPage()
  const BASE_URL = 'http://127.0.0.1:8000'

  console.log('Capturing 1: Chamber Audit Cockpit...')
  await page.goto(`${BASE_URL}/#/audit`, { waitUntil: 'networkidle' })
  await page.waitForSelector('h1:has-text("Audit Cockpit")', { timeout: 10000 })
  await page.waitForTimeout(1000)
  await page.screenshot({ path: path.join(outDir, '01_forensic_audit_cockpit_chamber.png'), fullPage: true })

  console.log('Capturing 2: Dossier Paper Audit Cockpit...')
  const dossierBtn = await page.waitForSelector('button:has-text("Dossier View")', { timeout: 5000 })
  await dossierBtn.click()
  await page.waitForTimeout(600)
  await page.screenshot({ path: path.join(outDir, '02_forensic_audit_cockpit_dossier.png'), fullPage: true })

  console.log('Capturing 3: Ingestion Portal...')
  await page.goto(`${BASE_URL}/#/ingest`, { waitUntil: 'networkidle' })
  await page.waitForSelector('h1:has-text("Target Codebase Ingestion")', { timeout: 10000 })
  await page.waitForTimeout(600)
  await page.screenshot({ path: path.join(outDir, '03_forensic_ingest_page.png') })

  console.log('Capturing 4: Graph Inspector Drawer...')
  await page.goto(`${BASE_URL}/#/audit?inspect=db-postgresql`, { waitUntil: 'networkidle' })
  await page.waitForSelector('h2:has-text("PostgreSQL")', { timeout: 10000 })
  await page.waitForTimeout(800)
  await page.screenshot({ path: path.join(outDir, '04_forensic_graph_inspector_drawer.png') })

  console.log('Capturing 5: Design System Specimen Route...')
  await page.goto(`${BASE_URL}/#/design-system`, { waitUntil: 'networkidle' })
  await page.waitForSelector('h1:has-text("CODIT Metrology & Design System")', { timeout: 10000 })
  await page.waitForTimeout(1000)
  await page.screenshot({ path: path.join(outDir, '05_forensic_design_system.png'), fullPage: true })

  console.log('Capturing 6: Mobile 375px Cockpit...')
  const mobileCtx = await browser.newContext({ viewport: { width: 375, height: 812 } })
  const mobilePage = await mobileCtx.newPage()
  await mobilePage.goto(`${BASE_URL}/#/audit`, { waitUntil: 'networkidle' })
  await mobilePage.waitForSelector('h1:has-text("Audit Cockpit")', { timeout: 10000 })
  await mobilePage.waitForTimeout(800)
  await mobilePage.screenshot({ path: path.join(outDir, '06_forensic_mobile_375.png') })

  await browser.close()
  console.log('✓ All Forensic Luxury screenshots captured successfully in docs/screenshots_forensic/')
}

captureArtifacts().catch((err) => {
  console.error('Screenshot capture failed:', err)
  process.exit(1)
})
