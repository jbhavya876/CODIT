import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 45000,
  retries: 0,
  workers: 1,
  use: {
    baseURL: 'http://localhost:8000',
    channel: 'chrome',
    headless: true,
    viewport: { width: 1440, height: 900 },
    screenshot: 'on',
    video: 'off',
    trace: 'off',
  },
  projects: [
    {
      name: 'Google Chrome',
      use: {
        channel: 'chrome',
      },
    },
  ],
});
