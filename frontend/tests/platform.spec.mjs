import { test, expect } from '@playwright/test';

test.describe('Codebase Audit Platform - End-to-End Verification', () => {

  test('Route 1: Ingestion Portal (#/ingest) - Tabs, Form Validations, and Security Defenses', async ({ page }) => {
    const consoleErrors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });

    await page.goto('/#/ingest');
    await page.waitForLoadState('networkidle');

    // 1. Verify Page Headers & Module Label
    const heading = page.locator('h1');
    await expect(heading).toContainText('Ingest Target Codebase');
    const badge = page.locator('text=Module 1 · Multi-Tier Repository Ingestion');
    await expect(badge).toBeVisible();

    // 2. Public GitHub Repo Tab (Default)
    const publicTab = page.locator('button:has-text("Public GitHub Repo")');
    await expect(publicTab).toBeVisible();
    const publicInput = page.locator('input[placeholder="https://github.com/owner/repository"]');
    await expect(publicInput).toBeVisible();
    await expect(publicInput).toHaveValue('https://github.com/charmi-reddy/Dependency-Detective');
    const branchInput = page.locator('input[value="main"]');
    await expect(branchInput).toBeVisible();

    // 3. ZIP Archive Upload Tab
    const zipTab = page.locator('button:has-text("ZIP Archive Upload")');
    await zipTab.click();
    await expect(page.locator('text=Non-Negotiable Privacy & Defense Guarantee')).toBeVisible();
    await expect(page.locator('text=Zip-Slip and Zip-Bomb')).toBeVisible();
    await expect(page.locator('text=permanently destroyed immediately post-audit')).toBeVisible();
    const fileInput = page.locator('input[type="file"]');
    await expect(fileInput).toBeVisible();

    // 4. Private Repo Tab
    const privateTab = page.locator('button:has-text("Private Repo (GitHub App)")');
    await privateTab.click();
    await expect(page.locator('text=GitHub App Integration')).toBeVisible();
    const repoSlugInput = page.locator('input[placeholder="acme-corp/private-service"]');
    await expect(repoSlugInput).toBeVisible();
    const tokenInput = page.locator('input[placeholder="ghs_..."]');
    await expect(tokenInput).toBeVisible();

    // 5. Switch back to Public
    await publicTab.click();
    await expect(publicInput).toBeVisible();

    expect(consoleErrors).toHaveLength(0);
  });

  test('Route 2: Audit Cockpit (#/audit) - Scorecard, Cap Banner, Roadmap, Mermaid, and Findings', async ({ page }) => {
    const consoleErrors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });

    await page.goto('/#/audit');
    await page.waitForLoadState('networkidle');

    // 1. Title & Metadata
    await expect(page.locator('h1')).toContainText('Codebase Audit Cockpit');
    await expect(page.locator('p:has-text("Target:")')).toBeVisible();

    // 2. Deterministic Scorecard Cards
    const overallCard = page.locator('text=Overall Readiness');
    await expect(overallCard).toBeVisible();
    const overallScore = page.locator('span:text-matches("^\\\\d+$")').first();
    await expect(overallScore).toBeVisible();

    // Check dimensions: Security, Tests, Scalability, Duplication, Maintainability
    for (const dim of ['security', 'tests', 'scalability', 'duplication', 'maintainability']) {
      const dimHeader = page.locator(`span:has-text("${dim}")`).first();
      await expect(dimHeader).toBeVisible();
    }

    // 3. Check for Hard Security Cap Alert if critical issue exists
    const blockerAlert = page.locator('text=Hard Constraint Alert: Security Score Capped at 25/100');
    if (await blockerAlert.isVisible()) {
      const secScore = page.locator('div:has(> span:has-text("security")) span.text-rose-400');
      await expect(secScore).toBeVisible();
      const scoreVal = parseInt(await secScore.innerText(), 10);
      expect(scoreVal).toBeLessThanOrEqual(25);
    }

    // 4. Engineering Roadmap: 3 Phased columns
    await expect(page.locator('h2:has-text("Prioritized Engineering Roadmap")')).toBeVisible();
    await expect(page.locator('text=/Phase 1|Immediate/').first()).toBeVisible();
    await expect(page.locator('text=/Phase 2/').first()).toBeVisible();
    await expect(page.locator('text=/Phase 3/').first()).toBeVisible();

    // Check action items inside roadmap
    const actionCards = page.locator('span:text-matches("P0 - Critical|P1 - High|P2 - Medium")');
    expect(await actionCards.count()).toBeGreaterThan(0);

    // 5. Architecture Diagrams & Tabs
    await expect(page.locator('h2:has-text("Architecture & Dependency Traversal")')).toBeVisible();
    const archOverviewBtn = page.locator('button:has-text("Architecture Overview")');
    const blastRadiusBtn = page.locator('button:has-text("Blast-Radius Traversal")');
    await expect(archOverviewBtn).toBeVisible();
    await expect(blastRadiusBtn).toBeVisible();

    // Check Mermaid rendering
    const mermaidSvg = page.locator('svg[id^="mermaid"]');
    await expect(mermaidSvg.first()).toBeVisible({ timeout: 10000 });

    // Switch to Blast-Radius Tab
    await blastRadiusBtn.click();
    const compSelect = page.locator('select');
    await expect(compSelect).toBeVisible();
    await compSelect.selectOption({ index: 1 });
    await page.waitForTimeout(1000);
    await expect(page.locator('svg[id^="mermaid"]').first()).toBeVisible();

    // Switch back to Architecture Overview
    await archOverviewBtn.click();

    // 6. Evidenced Findings Catalog Table & Filtering
    await expect(page.locator('h2:has-text("Evidenced Findings Catalog")')).toBeVisible();
    const searchInput = page.locator('input[placeholder="Search findings or files..."]');
    await expect(searchInput).toBeVisible();

    // Initial finding rows
    const rows = page.locator('tbody tr');
    const initialCount = await rows.count();
    expect(initialCount).toBeGreaterThan(0);

    // Test Search Filter
    await searchInput.fill('.env');
    await page.waitForTimeout(300);
    const filteredEnvCount = await page.locator('tbody tr').count();
    expect(filteredEnvCount).toBeLessThanOrEqual(initialCount);
    await searchInput.fill('');

    // Test Severity Filter Pills
    const critPill = page.locator('button:has-text("CRITICAL")');
    await critPill.click();
    await page.waitForTimeout(200);
    const critRows = await page.locator('tbody tr').count();
    expect(critRows).toBeLessThanOrEqual(initialCount);

    const allPill = page.locator('button:has-text("ALL")').first();
    await allPill.click();

    // Verify Citation column has file paths
    const firstCitation = page.locator('tbody tr td code').first();
    await expect(firstCitation).toBeVisible();
    const citationText = await firstCitation.innerText();
    expect(citationText.length).toBeGreaterThan(0);

    // 7. Parity Export Links
    const mdExportBtn = page.locator('a:has-text("Markdown")');
    await expect(mdExportBtn).toHaveAttribute('href', '/api/report/markdown');
    const pdfExportBtn = page.locator('a:has-text("Print / PDF")');
    await expect(pdfExportBtn).toHaveAttribute('href', '/api/report/html');

    expect(consoleErrors).toHaveLength(0);
  });

  test('Route 3: Graph Explorer (#/) - Inventory Stats, Type Filtering, Search, and Leaderboard', async ({ page }) => {
    const consoleErrors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });

    await page.goto('/#/');
    await page.waitForLoadState('networkidle');

    // 1. Inventory Stat Cards
    for (const type of ['Services', 'Databases', 'APIs', 'Libraries', 'Infra', 'Relations']) {
      const card = page.locator(`div, button:has-text("${type}")`).first();
      await expect(card).toBeVisible();
    }

    // 2. Type filter click (Databases)
    const dbCard = page.locator('button:has-text("Databases")');
    await dbCard.click();
    await page.waitForTimeout(400);
    await expect(page.locator('h2:has-text("Databases")')).toBeVisible();

    // Reset filter
    await dbCard.click();
    await page.waitForTimeout(400);
    await expect(page.locator('h2:has-text("All components")')).toBeVisible();

    // 3. Search Box interaction
    const search = page.locator('input[aria-label="Search components"]');
    await expect(search).toBeVisible();
    await search.fill('PostgreSQL');
    await page.waitForTimeout(400);
    const resultBtn = page.locator('button:has-text("PostgreSQL")').first();
    await expect(resultBtn).toBeVisible();

    // 4. Criticality Leaderboard
    await expect(page.locator('h2:has-text("Most critical components")')).toBeVisible();
    const leaderboardItems = page.locator('ol li a');
    expect(await leaderboardItems.count()).toBeGreaterThan(0);

    expect(consoleErrors).toHaveLength(0);
  });

  test('Route 4: Impact Analysis (#/c/db-postgresql/impact) - Traversal & Dependent Cascade', async ({ page }) => {
    const consoleErrors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });

    await page.goto('/#/c/db-postgresql/impact');
    await page.waitForLoadState('networkidle');

    // 1. Title & Header
    await expect(page.locator('h1')).toContainText('Impact analysis');
    await expect(page.locator('span:has-text("Database")').first()).toBeVisible();

    // 2. Summary Strip
    await expect(page.locator('div:has-text("Components affected")').first()).toBeVisible();
    await expect(page.locator('div:has-text("Direct dependents")').first()).toBeVisible();
    await expect(page.locator('div:has-text("Indirect dependents")').first()).toBeVisible();
    await expect(page.locator('div:has-text("Deepest chain")').first()).toBeVisible();
    await expect(page.locator('div:has-text("Criticality")').first()).toBeVisible();

    // 3. Blast Radius visualization
    await expect(page.locator('h2:has-text("Blast radius")')).toBeVisible();

    // 4. Direct and Indirect Dependents lists
    await expect(page.getByRole('heading', { name: /^Direct dependents/ })).toBeVisible();
    await expect(page.getByRole('heading', { name: /^Indirect dependents/ })).toBeVisible();

    // Check relationship tag in direct list
    const relTag = page.locator('span:has-text("READS_FROM")').first();
    await expect(relTag).toBeVisible();

    expect(consoleErrors).toHaveLength(0);
  });

  test('Route 5: Dependency Path Finder (#/path) - Multi-hop Route Tracing & Alternatives', async ({ page }) => {
    const consoleErrors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });

    await page.goto('/#/path?from=svc-customer-portal&to=db-postgresql');
    await page.waitForLoadState('networkidle');

    // 1. Page Title
    await expect(page.locator('h1')).toContainText('Dependency path finder');

    // 2. Selectors populated
    const fromSelect = page.locator('select').first();
    const toSelect = page.locator('select').nth(1);
    await expect(fromSelect).toHaveValue('svc-customer-portal');
    await expect(toSelect).toHaveValue('db-postgresql');

    // 3. Primary Path Panel
    await expect(page.locator('h2:has-text("How Customer Portal depends on PostgreSQL")')).toBeVisible();

    // 4. Node cards in path
    await expect(page.locator('span:has-text("Customer Portal")').first()).toBeVisible();
    await expect(page.locator('span:has-text("PostgreSQL")').first()).toBeVisible();

    // 5. Alternative routes
    const altPanel = page.locator('h2:has-text("Alternative routes")');
    if (await altPanel.isVisible()) {
      const altButtons = page.locator('ul li button');
      expect(await altButtons.count()).toBeGreaterThan(0);
      // Click an alternative route
      await altButtons.first().click();
      await page.waitForTimeout(300);
    }

    // 6. Test Swap Direction Button
    const swapBtn = page.locator('button[title="Swap direction"]');
    await expect(swapBtn).toBeVisible();
    await swapBtn.click();
    await page.waitForTimeout(500);
    expect(page.url()).toContain('from=db-postgresql');
    expect(page.url()).toContain('to=svc-customer-portal');

    expect(consoleErrors).toHaveLength(0);
  });

});
