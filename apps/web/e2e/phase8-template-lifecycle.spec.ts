import { expect, test } from '@playwright/test'

test('manages the complete template lifecycle', async ({ page, request }) => {
  const suffix = Date.now().toString()
  const templateName = `Lifecycle Notice ${suffix}`
  const cloneName = `Independent Copy ${suffix}`
  const domainResponse = await request.post('http://127.0.0.1:8000/domains', {
    data: { name: `Lifecycle Domain ${suffix}` },
  })
  expect(domainResponse.ok()).toBeTruthy()
  const domain = await domainResponse.json()
  const templateResponse = await request.post(
    'http://127.0.0.1:8000/templates',
    {
      data: {
        domain_id: domain.id,
        name: templateName,
        description: 'Synthetic Phase 8 lifecycle template',
        columns: [
          {
            name: 'Notice Date',
            column_type: 'date',
            prompt_text: 'Extract the notice date.',
            display_order: 0,
          },
          {
            name: 'Amount',
            column_type: 'currency',
            prompt_text: 'Extract the amount.',
            display_order: 1,
          },
        ],
      },
    },
  )
  expect(templateResponse.ok()).toBeTruthy()
  const template = await templateResponse.json()
  const publishResponse = await request.post(
    `http://127.0.0.1:8000/templates/${template.id}/publish`,
    {
      data: {
        expected_lock_version: template.current_version.lock_version,
      },
    },
  )
  expect(publishResponse.ok()).toBeTruthy()

  await page.goto('/templates')
  await page.getByLabel('Search name or description').fill(templateName)
  const templateCard = page.locator('.MuiCard-root').filter({
    has: page.getByRole('heading', { name: templateName }),
  })
  await expect(templateCard).toBeVisible()
  await templateCard.getByRole('link', { name: 'History' }).click()
  await expect(page.getByText(`Version 1: ${templateName}`)).toBeVisible()
  await page.getByRole('button', { name: 'Create new version' }).click()

  await expect(page).toHaveURL(new RegExp(`/templates/${template.id}$`))
  await expect(page.getByRole('button', { name: 'Save draft' })).toBeVisible()
  await page.getByRole('button', { name: 'Move Notice Date down' }).click()
  await expect(page.getByLabel('Column name').first()).toHaveValue('Amount')
  await page.getByRole('button', { name: 'Publish' }).click()
  await expect(page.getByText(/published version is immutable/i)).toBeVisible()

  await page.getByRole('link', { name: 'Version history' }).click()
  await expect(page.getByText(`Version 2: ${templateName}`)).toBeVisible()
  await expect(page.getByText(`Version 1: ${templateName}`)).toBeVisible()

  await page.goto('/templates')
  await page.getByLabel('Search name or description').fill(templateName)
  await templateCard.getByRole('button', { name: 'Clone' }).click()
  const cloneDialog = page.getByRole('dialog', { name: 'Clone template' })
  await cloneDialog.getByLabel('New template name').fill(cloneName)
  await cloneDialog.getByRole('button', { name: 'Clone' }).click()
  await expect(page.getByLabel('Template name')).toHaveValue(cloneName)
  await expect(page.getByRole('button', { name: 'Save draft' })).toBeVisible()

  await page.goto('/templates')
  await page.getByLabel('Search name or description').fill(templateName)
  page.once('dialog', (dialog) => dialog.accept())
  await templateCard.getByRole('button', { name: 'Archive' }).click()
  await page.getByLabel('Status').click()
  await page.getByRole('option', { name: 'Archived' }).click()
  await expect(templateCard.getByText('archived v2')).toBeVisible()
})
