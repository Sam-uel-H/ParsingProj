import { expect, test } from '@playwright/test'
import { waitForExtraction } from './helpers'

const api = 'http://127.0.0.1:8000'

test('finishes queued jobs after navigation and preserves extraction history', async ({
  page,
  request,
}) => {
  const domain = await (
    await request.post(`${api}/domains`, {
      data: { name: `Durable ${Date.now()}` },
    })
  ).json()
  const template = await (
    await request.post(`${api}/templates`, {
      data: {
        domain_id: domain.id,
        name: 'Twenty column acceptance',
        columns: Array.from({ length: 20 }, (_, i) => ({
          name: `Field ${i}`,
          column_type: 'integer',
          display_order: i,
          prompt_text: `Extract Field ${i}.`,
        })),
      },
    })
  ).json()
  await request.post(`${api}/templates/${template.id}/publish`, {
    data: { expected_lock_version: template.current_version.lock_version },
  })
  const started = Date.now()
  const upload = await (
    await request.post(`${api}/documents/upload`, {
      multipart: {
        domain_id: domain.id,
        files: {
          name: 'ten-pages.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from(
            Array.from(
              { length: 10 },
              (_, page) =>
                `Field ${page * 2}: ${page * 2}\nField ${page * 2 + 1}: ${page * 2 + 1}\n`,
            ).join('\f\n'),
          ),
        },
      },
    })
  ).json()
  const documentId = upload.results[0].document.id
  await request.post(`${api}/documents/${documentId}/extract`)
  const extraction = await waitForExtraction(request, documentId)
  expect(extraction.pages).toHaveLength(10)
  const queued = await (
    await request.post(`${api}/parsing-jobs`, {
      data: {
        document_id: documentId,
        template_id: template.id,
        strategy: 'batch',
      },
    })
  ).json()
  expect(['queued', 'parsing', 'completed']).toContain(queued.status)
  await page.goto(`/parsing-jobs/${queued.id}`)
  await page.goto('/parse')
  await expect(
    page.getByRole('link', { name: new RegExp(queued.id.slice(0, 8)) }),
  ).toBeVisible()
  await page
    .getByRole('link', { name: new RegExp(queued.id.slice(0, 8)) })
    .click()
  await page.reload()
  await expect(
    page.getByText('Job status: completed', { exact: true }),
  ).toBeVisible()
  const elapsed = Date.now() - started
  expect(elapsed).toBeLessThan(30_000)
  test.info().annotations.push({
    type: 'synthetic-20-column-10-page-ms',
    description: String(elapsed),
  })
  await page.goto(`/documents/${documentId}`)
  await page.getByRole('button', { name: 'Reprocess extraction' }).click()
  await expect
    .poll(
      async () =>
        (
          await (
            await request.get(`${api}/documents/${documentId}/extraction`)
          ).json()
        ).version_number,
    )
    .toBe(2)
  await waitForExtraction(request, documentId)
  await page.reload()
  await page.getByLabel('Extraction version').click()
  await page.getByRole('option', { name: 'Version 1 · succeeded' }).click()
  await page.getByRole('button', { name: 'Extracted text' }).click()
  await expect(page.getByText('Field 0: 0', { exact: false })).toBeVisible()
  await page.screenshot({
    path: test.info().outputPath('extraction-history-desktop.png'),
    fullPage: true,
  })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({
    path: test.info().outputPath('extraction-history-mobile.png'),
    fullPage: true,
  })
  const originalJob = await (
    await request.get(`${api}/parsing-jobs/${queued.id}`)
  ).json()
  expect(originalJob.document_extraction_id).toBe(extraction.id)
})
