import { expect, test, type Page } from '@playwright/test';

// Intake: pick a scenario, choose urgency, submit. Analysis starts
// automatically; the case opens and the verdict lands in the decision column.
async function createRequestFromScenario(page: Page, scenarioTitle: string): Promise<void> {
  await page.goto('/');
  await expect(page.getByText('Prior Auth Express').first()).toBeVisible();
  await page.getByRole('navigation', { name: 'Primary' }).getByRole('button', { name: 'New request' }).click();
  await page.getByText(scenarioTitle, { exact: true }).click();
  await page.getByRole('button', { name: 'Submit request' }).click();
}

async function waitForVerdict(page: Page): Promise<void> {
  await expect(
    page.getByRole('heading', {
      name: /(Meets criteria — recommend approval|Documentation incomplete — recommend requesting information)/,
    }),
  ).toBeVisible({ timeout: 20_000 });
}

test('DXA scenario analyzes at intake, approves, and sends the letter', async ({ page }) => {
  await createRequestFromScenario(page, 'DXA bone density — Medicare NCD 150.3');

  // No "Run determination" step exists; analysis is ambient.
  await expect(page.getByRole('button', { name: /run determination/i })).toHaveCount(0);
  await waitForVerdict(page);

  await expect(page.getByRole('heading', { name: /Meets criteria — recommend approval/ })).toBeVisible();
  await expect(page.getByText('5/5 required criteria met').first()).toBeVisible();

  // The criteria grid names the policy and links to it on cms.gov.
  await expect(page.getByText(/NCD 150\.3/).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Open NCD 150.3 on cms.gov' }).first()).toBeVisible();

  // Attribution names the offline engine.
  await expect(page.getByText('Recommendation source: Rules engine')).toBeVisible();

  // The sign-off strip stays open until the reviewer decides.
  const signOff = page.getByRole('region', { name: /Sign-off/ });
  await expect(signOff.getByText('Not signed').first()).toBeVisible();

  // Dispose: approve with the default 90-day validity window, confirmed inline.
  const decision = page.getByRole('complementary', { name: 'Decision' });
  await decision.getByRole('button', { name: 'Approve', exact: true }).click();
  await expect(decision.getByRole('heading', { name: 'Approve this request?' })).toBeVisible();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await decision.locator('form').getByRole('button', { name: 'Approve', exact: true }).click();

  // Lands on the letter view with a clean, editable draft.
  await expect(page.getByRole('heading', { name: 'Approval letter' })).toBeVisible();
  const letterBody = page.getByLabel('Letter body');
  await expect(letterBody).toBeVisible();
  await expect(letterBody).toHaveValue(/150\.3/);
  await expect(letterBody).toHaveValue(/Valid From/);
  await expect(letterBody).not.toHaveValue(/PLACEHOLDER/);
  await expect(page.getByText(/Drafted from the criterion-level determination/i).first()).toBeVisible();

  // Send it; the case completes and the worklist returns.
  await page.getByRole('button', { name: 'Send to provider' }).click();
  await expect(page.getByRole('heading', { name: 'Worklist' })).toBeVisible();
  await expect(page.getByRole('cell', { name: /^Approved\s*, letter sent$/ }).first()).toBeVisible();
});

test('criteria grid moves between cells with the keyboard', async ({ page }) => {
  await createRequestFromScenario(page, 'DXA bone density — Medicare NCD 150.3');
  await waitForVerdict(page);

  const grid = page.getByRole('grid');
  await expect(grid).toBeVisible();

  const active = grid.locator('[role="gridcell"][tabindex="0"]');
  await expect(active).toHaveCount(1);

  const detail = page.locator('#detail-title');
  const before = await detail.textContent();

  await active.focus();
  await page.keyboard.press('ArrowDown');

  await expect(grid.locator('[role="gridcell"][tabindex="0"]')).toBeFocused();
  await expect(grid.locator('[role="gridcell"][aria-selected="true"]')).toHaveCount(1);
  await expect(detail).not.toHaveText(before ?? '');
});

test('decision tab exposes the engine calls behind the recommendation', async ({ page }) => {
  await createRequestFromScenario(page, 'DXA bone density — Medicare NCD 150.3');
  await waitForVerdict(page);

  await page.getByRole('tab', { name: 'Decision & audit' }).click();

  await expect(page.getByRole('heading', { name: 'Engine calls' })).toBeVisible();
  await expect(page.getByText('0 engine calls')).toBeVisible();
  await expect(
    page.getByText('No model or network request was sent. The rules engine checked each criterion locally.'),
  ).toBeVisible();
});

test('sleep study scenario pends with a reviewer-curated information request', async ({ page }) => {
  await createRequestFromScenario(page, 'In-lab sleep study — Medicare LCD L33405');
  await waitForVerdict(page);

  await expect(
    page.getByRole('heading', { name: /Documentation incomplete — recommend requesting information/ }),
  ).toBeVisible();
  await expect(page.getByText('6/7 required criteria met').first()).toBeVisible();

  // The specific unmet criterion is surfaced as a gap, and the blank form
  // field in the record is called out on the quote.
  await expect(page.getByText(/Epworth Sleepiness Scale/i).first()).toBeVisible();
  await expect(page.getByText('Field blank in record')).toBeVisible();

  // There is no deny action anywhere.
  await expect(page.getByRole('button', { name: /deny/i })).toHaveCount(0);

  // Dispose: request information. Items are pre-checked from unmet criteria.
  const decision = page.getByRole('complementary', { name: 'Decision' });
  await decision.getByRole('button', { name: 'Request information', exact: true }).click();
  await expect(decision.getByRole('heading', { name: 'Request information from the provider' })).toBeVisible();
  const checkboxes = decision.getByRole('checkbox');
  expect(await checkboxes.count()).toBeGreaterThan(0);
  await decision.getByRole('button', { name: /Request \d+ items?/ }).click();

  // The pend letter lists the requested items and a response deadline.
  await expect(page.getByRole('heading', { name: 'Information request letter' })).toBeVisible();
  const letterBody = page.getByLabel('Letter body');
  await expect(letterBody).toBeVisible();
  await expect(letterBody).toHaveValue(/Epworth Sleepiness Scale/i);
  await expect(letterBody).toHaveValue(/Response Deadline/);
});

test('refer to MD requires a summary and produces no provider letter', async ({ page }) => {
  await createRequestFromScenario(page, 'Lumbar spine MRI — Medicare LCD L34220');
  await waitForVerdict(page);

  const decision = page.getByRole('complementary', { name: 'Decision' });
  await decision.getByRole('button', { name: 'Refer to MD', exact: true }).click();
  const referButton = decision.getByRole('button', { name: 'Refer case' });
  await expect(referButton).toBeDisabled();
  await decision
    .locator('form textarea')
    .fill('Documentation is borderline on conservative care duration; requesting MD judgment.');
  await referButton.click();

  // Referral is an internal handoff: back to the worklist, no letter.
  await expect(page.getByRole('heading', { name: 'Worklist' })).toBeVisible();
  await expect(page.getByText('Referred to MD').first()).toBeVisible();
});

test('worklist shows single case status and recommendation per row', async ({ page }) => {
  await createRequestFromScenario(page, 'Lumbar spine MRI — Medicare LCD L34220');
  await waitForVerdict(page);

  await page.getByRole('button', { name: 'Back to worklist' }).first().click();
  await expect(page.getByText('Daniel Reyes').first()).toBeVisible();
  // One status face per case, never the raw two-axis internals.
  await expect(page.getByText('Needs review').first()).toBeVisible();
  await expect(page.getByText(/Recommendation:\s*Meets criteria/).first()).toBeVisible();
  await expect(page.getByText(/\d+[dhm].* left/).first()).toBeVisible();
  // The primary action opens the top case awaiting review.
  await expect(page.getByRole('button', { name: 'Review next case' })).toBeEnabled();
});

test('LCD case opens the full coverage policy inline', async ({ page }) => {
  await createRequestFromScenario(page, 'Total knee replacement — Medicare LCD L39911');
  await waitForVerdict(page);

  await expect(page.getByText(/LCD L39911/).first()).toBeVisible();

  // "View policy" opens the public LCD text inline, never in a dialog.
  await page.getByRole('button', { name: 'View policy', exact: true }).first().click();
  await expect(page.getByRole('heading', { name: /LCD L39911 — Total Joint Arthroplasty/ })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Coverage criteria' })).toBeVisible();
  await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('engine settings explains each engine and shows the current selection', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('navigation', { name: 'Primary' }).getByRole('button', { name: 'Engine' }).click();

  await expect(page.getByRole('heading', { name: 'Reasoning engine' })).toBeVisible();
  await expect(page.getByText('Current engine — new requests start here.')).toBeVisible();
  await expect(page.getByRole('radio', { name: /Rules engine/ })).toBeChecked();
  await expect(page.getByText(/Backend connected — v/)).toBeVisible();
});

test('OpenAI GPT settings save scalar model and reasoning effort values', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('navigation', { name: 'Primary' }).getByRole('button', { name: 'Engine' }).click();

  const gptRow = page.locator('.engine').filter({ hasText: 'OpenAI GPT' }).first();
  const toggle = gptRow.getByRole('button', { name: 'Model & reasoning' });
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  await expect(page.getByRole('dialog')).toHaveCount(0);

  await gptRow.getByLabel('Reasoning effort').selectOption('medium');

  const saveRequest = page.waitForRequest((request) => {
    if (!request.url().endsWith('/api/engine-config/openai-gpt')) return false;

    if (request.method() !== 'PUT') return false;

    const body = request.postDataJSON();

    return body.command === 'codex' && body.model_id === 'gpt-5.5' && body.effort === 'medium';
  });

  await gptRow.getByRole('button', { name: 'Save for this session' }).click();
  await saveRequest;

  await expect(gptRow.locator('dd').filter({ hasText: /^gpt-5\.5$/ })).toBeVisible();
  await expect(gptRow.locator('dd').filter({ hasText: /^Medium$/ })).toBeVisible();
  await expect(gptRow.locator('dd').filter({ hasText: /^codex CLI$/ })).toBeVisible();
  await expect(gptRow.getByText('Session override')).toBeVisible();

  // Put the server back on its defaults for the next run.
  await toggle.click();
  await gptRow.getByRole('button', { name: 'Reset to server default' }).click();
  await expect(gptRow.getByText('Session override')).toHaveCount(0);
  await expect(gptRow.locator('dd').filter({ hasText: /^Extra high$/ })).toBeVisible();
});
