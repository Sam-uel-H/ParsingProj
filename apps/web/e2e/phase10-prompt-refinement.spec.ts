import { expect, test } from '@playwright/test'
import { waitForExtraction } from './helpers'

const api = 'http://127.0.0.1:8000'

test('generates, refines, dry-runs, verifies evidence, and accepts a prompt', async ({
  page,
  request,
}) => {
  const suffix = Date.now()
  const domain = await (
    await request.post(`${api}/domains`, {
      data: { name: `Prompt Loop ${suffix}` },
    })
  ).json()
  const template = await (
    await request.post(`${api}/templates`, {
      data: {
        domain_id: domain.id,
        name: `Prompt Loop ${suffix}`,
        columns: [
          { name: 'Notice Date', column_type: 'date', display_order: 0 },
          { name: 'Amount', column_type: 'currency', display_order: 1 },
        ],
      },
    })
  ).json()
  const upload = await (
    await request.post(`${api}/documents/upload`, {
      multipart: {
        domain_id: domain.id,
        files: {
          name: 'notice.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from('Notice Date: 2026-09-28\nAmount: $17'),
        },
      },
    })
  ).json()
  const documentId = upload.results[0].document.id as string
  await request.post(`${api}/documents/${documentId}/extract`)
  const extraction = await waitForExtraction(request, documentId)
  const columnId = template.current_version.columns[0].id as string
  expect(
    (
      await request.post(`${api}/templates/${template.id}/tagged-examples`, {
        data: {
          template_column_id: columnId,
          document_id: documentId,
          document_extraction_id: extraction.id,
          page_number: 1,
          selected_text: '2026-09-28',
          expected_value: '2026-09-28',
          rectangles: [{ x: 0.2, y: 0.1, width: 0.2, height: 0.03 }],
        },
      })
    ).ok(),
  ).toBeTruthy()

  await page.goto(
    `/templates/${template.id}/prompt-helper?document=${documentId}`,
  )
  await expect(
    page.getByRole('heading', { name: 'Prompt workspace' }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Generate prompt' }).click()
  const editor = page.getByRole('textbox', { name: 'Prompt' })
  await expect(editor).toHaveValue(/2026-09-28/)
  await editor.fill('Extract the notice date and return ISO JSON.')
  const sidebarDialog = new Promise<void>((resolve) => {
    page.once('dialog', async (dialog) => {
      await dialog.dismiss()
      resolve()
    })
  })
  await page
    .getByRole('navigation', { name: 'Main navigation' })
    .getByRole('link', { name: 'Dashboard' })
    .click()
  await sidebarDialog
  await expect(page).toHaveURL(/\/prompt-helper/)
  await expect(editor).toHaveValue(
    'Extract the notice date and return ISO JSON.',
  )
  const columnDialog = new Promise<void>((resolve) => {
    page.once('dialog', async (dialog) => {
      await dialog.dismiss()
      resolve()
    })
  })
  await page.getByRole('combobox', { name: 'Active column' }).click()
  await page.getByRole('option', { name: 'Amount' }).click()
  await columnDialog
  await expect(editor).toHaveValue(
    'Extract the notice date and return ISO JSON.',
  )
  await page.getByRole('button', { name: 'Save draft' }).click()
  await expect(page.getByRole('button', { name: 'Dry run' })).toBeEnabled()
  await page.getByRole('button', { name: 'Dry run' }).click()
  await expect(page.getByText('Matches expected value')).toBeVisible()
  await page.getByRole('button', { name: 'Show evidence' }).click()
  await expect(
    page.locator('.prompt-helper-text-page mark').first(),
  ).toContainText('Notice Date:')
  await page.getByRole('button', { name: 'Accept prompt' }).click()
  await expect(page.getByText('Accepted', { exact: false })).toBeVisible()
  await page.reload()
  await expect(editor).toHaveValue(
    'Extract the notice date and return ISO JSON.',
  )
  await expect(page.getByText('Matches expected value')).toBeVisible()
  await page.getByRole('combobox', { name: 'Active column' }).click()
  await page.getByRole('option', { name: 'Amount' }).click()
  await expect(editor).toHaveCount(0)
  await page.getByRole('combobox', { name: 'Active column' }).click()
  await page.getByRole('option', { name: 'Notice Date' }).click()
  await expect(editor).toHaveValue(
    'Extract the notice date and return ISO JSON.',
  )
  const updated = await (
    await request.get(`${api}/templates/${template.id}`)
  ).json()
  expect(updated.current_version.columns[0].prompt_text).toBe(
    'Extract the notice date and return ISO JSON.',
  )
})
