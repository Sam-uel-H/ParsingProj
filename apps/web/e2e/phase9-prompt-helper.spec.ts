import { expect, test, type Page } from '@playwright/test'

const api = 'http://127.0.0.1:8000'

async function selectText(page: Page, containerSelector: string, text: string) {
  await page.evaluate(
    ({ containerSelector, text }) => {
      const container = document.querySelector(containerSelector)
      if (!container) throw new Error('Selectable page not found')
      const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT)
      const nodes: Text[] = []
      while (walker.nextNode()) nodes.push(walker.currentNode as Text)
      const allText = nodes.map((node) => node.textContent ?? '').join('')
      const start = allText.indexOf(text)
      if (start < 0) throw new Error(`Selected text not found: ${text}`)
      const end = start + text.length
      let position = 0
      let startNode: Text | undefined
      let endNode: Text | undefined
      let startOffset = 0
      let endOffset = 0
      for (const node of nodes) {
        const next = position + (node.textContent?.length ?? 0)
        if (!startNode && start >= position && start < next) {
          startNode = node
          startOffset = start - position
        }
        if (endNode === undefined && end > position && end <= next) {
          endNode = node
          endOffset = end - position
        }
        position = next
      }
      if (!startNode || !endNode)
        throw new Error('Selection endpoints were not found')
      const range = document.createRange()
      range.setStart(startNode, startOffset)
      range.setEnd(endNode, endOffset)
      const selection = window.getSelection()
      selection?.removeAllRanges()
      selection?.addRange(range)
      container.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }))
    },
    { containerSelector, text },
  )
}

test('tags, reloads, replaces, and deletes spans on multiple text pages', async ({
  page,
  request,
}) => {
  const suffix = Date.now()
  const domain = await (
    await request.post(`${api}/domains`, {
      data: { name: `Tagging ${suffix}` },
    })
  ).json()
  const template = await (
    await request.post(`${api}/templates`, {
      data: {
        domain_id: domain.id,
        name: `Notice Tags ${suffix}`,
        columns: [
          { name: 'Notice Date', column_type: 'date', display_order: 0 },
          { name: 'Amount', column_type: 'currency', display_order: 1 },
        ],
      },
    })
  ).json()
  const content = 'Notice Date: 2026-09-27\nAmount: 17\fLater Date: 2026-10-01'
  const upload = await (
    await request.post(`${api}/documents/upload`, {
      multipart: {
        domain_id: domain.id,
        files: {
          name: 'sample.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from(content),
        },
      },
    })
  ).json()
  const documentId = upload.results[0].document.id as string
  expect(
    (await request.post(`${api}/documents/${documentId}/extract`)).ok(),
  ).toBeTruthy()

  await page.goto(`/templates/${template.id}`)
  await page.getByRole('link', { name: 'Prompt Helper' }).first().click()
  await expect(
    page.getByRole('heading', { name: 'Prompt Helper' }),
  ).toBeVisible()
  await expect(
    page.getByLabel('Selectable extracted text page 1'),
  ).toBeVisible()

  await selectText(page, '.prompt-helper-text-page', '2026-09-27')
  await expect(page.getByText('2026-09-27', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Save tag' }).click()
  await expect(page.getByText('Saved tag')).toBeVisible()
  await page.reload()
  await expect(page.getByText('Saved tag')).toBeVisible()
  await expect(page.locator('.prompt-helper-text-page mark')).toContainText(
    '2026-09-27',
  )

  await selectText(page, '.prompt-helper-text-page', 'Notice Date: 2026-09-27')
  await page.getByRole('button', { name: 'Replace tag' }).click()
  await expect(
    page.getByText('Notice Date: 2026-09-27', { exact: true }).last(),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Delete saved tag' }).click()
  await expect(page.getByText('Saved tag')).toHaveCount(0)

  await page.getByLabel('Active column').click()
  await page.getByRole('option', { name: 'Amount' }).click()
  await page.getByRole('button', { name: 'Next page' }).click()
  await expect(
    page.getByLabel('Selectable extracted text page 2'),
  ).toBeVisible()
  await selectText(page, '.prompt-helper-text-page', '2026-10-01')
  await page.getByRole('button', { name: 'Save tag' }).click()
  await page.reload()
  await expect(page.getByText('Saved tag')).toBeVisible()
  await page.getByRole('button', { name: 'Page 2' }).last().click()
  await expect(page.locator('.prompt-helper-text-page mark')).toContainText(
    '2026-10-01',
  )
})

test('renders a selectable PDF text layer and maps its selection', async ({
  page,
  request,
  context,
}) => {
  const suffix = Date.now()
  const domain = await (
    await request.post(`${api}/domains`, {
      data: { name: `PDF Tagging ${suffix}` },
    })
  ).json()
  const template = await (
    await request.post(`${api}/templates`, {
      data: {
        domain_id: domain.id,
        name: `PDF Template ${suffix}`,
        columns: [{ name: 'Code', column_type: 'string', display_order: 0 }],
      },
    })
  ).json()
  const printable = await context.newPage()
  await printable.setContent(
    '<html><body><p>UniqueCodePhaseNine42</p></body></html>',
  )
  const pdf = await printable.pdf({ format: 'Letter' })
  await printable.close()
  const upload = await (
    await request.post(`${api}/documents/upload`, {
      multipart: {
        domain_id: domain.id,
        files: { name: 'sample.pdf', mimeType: 'application/pdf', buffer: pdf },
      },
    })
  ).json()
  const documentId = upload.results[0].document.id as string
  const extraction = await (
    await request.post(`${api}/documents/${documentId}/extract`)
  ).json()
  expect(extraction.full_text).toContain('UniqueCodePhaseNine42')

  await page.goto(
    `/templates/${template.id}/prompt-helper?document=${documentId}`,
  )
  const pdfPage = page.getByLabel('Selectable PDF page 1')
  await expect(pdfPage).toBeVisible()
  await expect(
    pdfPage
      .locator('.textLayer span')
      .filter({ hasText: 'UniqueCodePhaseNine42' }),
  ).toBeVisible({ timeout: 20_000 })
  await selectText(page, '.prompt-pdf-text-layer', 'UniqueCodePhaseNine42')
  await page.getByRole('button', { name: 'Save tag' }).click()
  await expect(page.getByText('Saved tag')).toBeVisible()
  await page.reload()
  await expect(page.locator('.prompt-tag-highlight')).toBeVisible()
})
