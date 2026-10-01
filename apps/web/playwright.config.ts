import { defineConfig, devices } from '@playwright/test'

const apiCommand =
  process.platform === 'win32'
    ? '"..\\api\\.venv\\Scripts\\python.exe" -m uvicorn app.main:app --app-dir "..\\api" --host 127.0.0.1 --port 8000'
    : 'python -m uvicorn app.main:app --app-dir ../api --host 127.0.0.1 --port 8000'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: apiCommand,
      url: 'http://127.0.0.1:8000/health',
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5173',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
})
