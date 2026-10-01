import { expect, test } from '@playwright/test'

test('completes the synthetic Agent Bank Notice MVP workflow', async ({
  page,
}) => {
  const suffix = Date.now().toString()
  const domainName = `Agent Bank Notices ${suffix}`
  const templateName = `Section 6 Notice ${suffix}`

  await page.goto('/domains')
  await page.getByLabel('Name').fill(domainName)
  await page.getByLabel('Description').fill('Synthetic Phase 7 acceptance data')
  await page.getByRole('button', { name: 'Create domain' }).click()
  await expect(page.getByText(domainName)).toBeVisible()
  await page.reload()
  await expect(page.getByText(domainName)).toBeVisible()

  await page.goto('/templates/new')
  await page.getByLabel('Template name').fill(templateName)
  await page.getByLabel('Domain').click()
  await page.getByRole('option', { name: domainName }).click()
  await page
    .getByLabel('Description')
    .fill('Synthetic Agent Bank Notice template for MVP acceptance')

  const columns = [
    ['Notice Date', 'date', 'Extract the notice date.'],
    ['Borrower Name', 'string', 'Extract the borrower name.'],
    ['Interest Amount', 'currency', 'Extract the interest amount.'],
    ['Payment Due Date', 'date', 'Extract the payment due date.'],
  ] as const
  for (const [index, [name, type, prompt]] of columns.entries()) {
    await page.getByRole('button', { name: 'Add column' }).click()
    await page.getByLabel('Column name').nth(index).fill(name)
    if (type !== 'string') {
      await page.getByLabel('Type').nth(index).click()
      await page.getByRole('option', { name: type, exact: true }).click()
    }
    await page.getByLabel('Extraction prompt').nth(index).fill(prompt)
  }

  await page.getByRole('button', { name: 'Save draft' }).click()
  await expect(page).toHaveURL(/\/templates\/[0-9a-f-]+$/)
  await page.reload()
  await expect(page.getByRole('button', { name: 'Publish' })).toBeEnabled()
  await page.getByRole('button', { name: 'Publish' }).click()
  await expect(page.getByText(/published version is immutable/i)).toBeVisible()
  await page.reload()
  await expect(page.getByText(/published version is immutable/i)).toBeVisible()

  await page.goto('/documents/upload')
  await page.getByLabel('Domain (optional)').click()
  await page.getByRole('option', { name: domainName }).click()
  await page.locator('input[type="file"]').setInputFiles({
    name: `agent-bank-notice-${suffix}.txt`,
    mimeType: 'text/plain',
    buffer: Buffer.from(
      [
        'Notice Date: 2026-09-25',
        'Borrower Name: Example Holdings LLC',
        'Interest Amount: definitely-not-money',
        'Payment Due Date: 2026-10-01',
      ].join('\n'),
    ),
  })
  await page.getByRole('button', { name: 'Upload selected files' }).click()
  const openDocument = page.getByRole('link', { name: 'Open document' })
  await expect(openDocument).toBeVisible()
  await openDocument.click()
  await expect(page.getByText('Extraction status: succeeded')).toBeVisible()
  await page.reload()
  await expect(page.getByText('Extraction status: succeeded')).toBeVisible()

  await page
    .getByRole('main')
    .getByRole('link', { name: 'Run parsing' })
    .click()
  await page.getByLabel('Published template').click()
  await page.getByRole('option', { name: templateName }).click()
  await page.getByRole('button', { name: 'Start parsing' }).click()

  const amountRow = page.getByRole('row').filter({ hasText: 'Interest Amount' })
  await expect(amountRow.getByText('needs review')).toBeVisible()
  await expect(amountRow.getByText('Retried 2 times')).toBeVisible()
  await amountRow.getByLabel('Reviewed value').fill('1250.50')
  await amountRow.getByRole('button', { name: 'Save' }).click()
  await expect(amountRow.getByText('Human verified')).toBeVisible()
  await expect(page.getByText('Job status: completed')).toBeVisible()

  await page.getByRole('link', { name: 'Open saved job results' }).click()
  await expect(page).toHaveURL(/\/parsing-jobs\/[0-9a-f-]+$/)
  await page.reload()
  await expect(page.getByText('Job status: completed')).toBeVisible()

  const csvHref = await page
    .getByRole('link', { name: 'Export CSV' })
    .getAttribute('href')
  const jsonHref = await page
    .getByRole('link', { name: 'Export JSON' })
    .getAttribute('href')
  expect(csvHref).toBeTruthy()
  expect(jsonHref).toBeTruthy()

  const csv = await page.request.get(csvHref!)
  expect(csv.ok()).toBeTruthy()
  expect(await csv.text()).toContain(
    'Notice Date,Borrower Name,Interest Amount,Payment Due Date',
  )
  expect(await (await page.request.get(jsonHref!)).json()).toMatchObject({
    results: expect.arrayContaining([
      expect.objectContaining({
        column_name: 'Interest Amount',
        value: '1250.50',
        human_verified: true,
      }),
    ]),
  })
})

test('shows stable empty and API failure states', async ({ page }) => {
  await page.route('**/api/documents', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }),
  )
  await page.goto('/documents')
  await expect(
    page.getByText('No documents have been uploaded yet.'),
  ).toBeVisible()

  await page.route('**/api/domains', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({
        error: { code: 'unavailable', message: 'Synthetic API failure.' },
        request_id: 'playwright-failure',
      }),
    }),
  )
  await page.goto('/domains')
  await expect(
    page.getByText('Synthetic API failure. Request ID: playwright-failure'),
  ).toBeVisible()
})
