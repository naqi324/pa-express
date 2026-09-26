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

async function openEngineSettings(page: Page, engineName: string) {
  await page.goto('/');
  await page.getByRole('navigation', { name: 'Primary' }).getByRole('button', { name: 'Engine' }).click();

  const row = page.locator('.engine').filter({ hasText: engineName }).first();
  const toggle = row.getByRole('button', { name: 'Connection & model' });
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  await expect(page.getByRole('dialog')).toHaveCount(0);

  return { row, toggle };
}

test('OpenAI GPT settings save the catalog model and reasoning effort', async ({ page }) => {
  const { row: gptRow, toggle } = await openEngineSettings(page, 'OpenAI GPT');

  // The Codex CLI is the default connection, on the newest GPT model.
  await expect(gptRow.getByRole('radio', { name: /^Codex CLI/ })).toBeChecked();
  await expect(gptRow.getByLabel('Model', { exact: true })).toHaveValue('gpt-6-astra');
  await expect(gptRow.getByLabel('Reasoning effort')).toHaveValue('high');

  await gptRow.getByLabel('Reasoning effort').selectOption('ultra');

  const saveRequest = page.waitForRequest((request) => {
    if (!request.url().endsWith('/api/engine-config/openai-gpt')) return false;

    if (request.method() !== 'PUT') return false;

    const body = request.postDataJSON();

    return (
      body.auth_method === 'cli' &&
      body.model_id === 'gpt-6-astra' &&
      body.effort === 'ultra' &&
      body.api_key === null &&
      !('command' in body)
    );
  });

  await gptRow.getByRole('button', { name: 'Save for this session' }).click();
  await saveRequest;

  await expect(gptRow.locator('dd').filter({ hasText: /^Codex CLI · codex$/ })).toBeVisible();
  await expect(gptRow.locator('dd').filter({ hasText: /^GPT-6 Astra$/ })).toBeVisible();
  await expect(gptRow.locator('dd').filter({ hasText: /^Ultra$/ })).toBeVisible();
  await expect(gptRow.getByText('Session override')).toBeVisible();

  // Put the server back on its defaults for the next run.
  await toggle.click();
  await gptRow.getByRole('button', { name: 'Reset to server default' }).click();
  await expect(gptRow.getByText('Session override')).toHaveCount(0);
  await expect(gptRow.locator('dd').filter({ hasText: /^High$/ })).toBeVisible();
});

test('OpenAI GPT API key connection requires a key and never shows it again', async ({ page }) => {
  const { row: gptRow, toggle } = await openEngineSettings(page, 'OpenAI GPT');

  await gptRow.getByRole('radio', { name: /^OpenAI API key/ }).check();
  await expect(gptRow.getByLabel('Reasoning effort')).toHaveValue('high');

  // The API does not take the Codex-only Ultra effort.
  await expect(gptRow.getByLabel('Reasoning effort').locator('option[value="ultra"]')).toHaveCount(0);

  await gptRow.getByRole('button', { name: 'Save for this session' }).click();
  await expect(gptRow.getByText('Enter an API key, or choose another connection.')).toBeVisible();

  const keyField = gptRow.getByLabel('OpenAI API key', { exact: true });
  await expect(keyField).toHaveAttribute('aria-invalid', 'true');
  await expect(keyField).toHaveAttribute('type', 'password');
  await keyField.fill('e2e-fake-key-0000-9876');

  const saveRequest = page.waitForRequest((request) => {
    if (!request.url().endsWith('/api/engine-config/openai-gpt')) return false;

    if (request.method() !== 'PUT') return false;

    const body = request.postDataJSON();

    return body.auth_method === 'api_key' && body.api_key === 'e2e-fake-key-0000-9876';
  });

  await gptRow.getByRole('button', { name: 'Save for this session' }).click();
  await saveRequest;

  await expect(gptRow.locator('dd').filter({ hasText: /^OpenAI API key · key …9876$/ })).toBeVisible();

  // The stored key never comes back; a blank field keeps it.
  await toggle.click();
  await expect(gptRow.getByLabel('OpenAI API key', { exact: true })).toHaveValue('');
  await expect(gptRow.getByText('Key …9876 is stored for this session. Leave blank to keep it.')).toBeVisible();

  await gptRow.getByRole('button', { name: 'Reset to server default' }).click();
  await expect(gptRow.locator('dd').filter({ hasText: /^Codex CLI · codex$/ })).toBeVisible();
});

test('Anthropic Claude settings follow the catalog for each connection', async ({ page }) => {
  const { row: claudeRow, toggle } = await openEngineSettings(page, 'Anthropic Claude');

  await expect(claudeRow.getByRole('radio', { name: /^Claude Code CLI/ })).toBeChecked();
  await expect(claudeRow.getByLabel('Model', { exact: true })).toHaveValue('claude-opus-5-5');
  await expect(claudeRow.getByLabel('Reasoning effort')).toHaveValue('high');

  // Claude Haiku 4.5 takes no effort setting.
  await claudeRow.getByLabel('Model', { exact: true }).selectOption('claude-haiku-4-5-20251001');
  await expect(claudeRow.getByLabel('Reasoning effort')).toBeDisabled();
  await expect(claudeRow.getByText('This model takes no effort setting.')).toBeVisible();

  // Bedrock adds its region and credentials and sends the regional inference profile.
  await claudeRow.getByRole('radio', { name: /^AWS Bedrock/ }).check();
  await expect(claudeRow.getByLabel('Region')).toHaveValue('us-west-2');
  await expect(claudeRow.getByText('Sent as us.anthropic.claude-haiku-4-5-20251001-v1:0.')).toBeVisible();

  // A model with an effort setting starts on its documented default.
  await claudeRow.getByLabel('Model', { exact: true }).selectOption('claude-sonnet-5');
  await expect(claudeRow.getByLabel('Reasoning effort')).toHaveValue('high');

  const saveRequest = page.waitForRequest((request) => {
    if (!request.url().endsWith('/api/engine-config/anthropic-claude')) return false;

    if (request.method() !== 'PUT') return false;

    const body = request.postDataJSON();

    return (
      body.auth_method === 'bedrock' &&
      body.model_id === 'claude-sonnet-5' &&
      body.effort === 'high' &&
      body.bedrock_region === 'us-west-2' &&
      body.bedrock_credentials === 'profile' &&
      body.api_key === null
    );
  });

  await claudeRow.getByRole('button', { name: 'Save for this session' }).click();
  await saveRequest;

  await expect(claudeRow.locator('dd').filter({ hasText: /^AWS Bedrock · .+ · us-west-2$/ })).toBeVisible();
  await expect(claudeRow.locator('dd').filter({ hasText: /^Claude Sonnet 5$/ })).toBeVisible();

  await toggle.click();
  await claudeRow.getByRole('button', { name: 'Reset to server default' }).click();
  await expect(claudeRow.locator('dd').filter({ hasText: /^Claude Opus 5\.5$/ })).toBeVisible();
  await expect(claudeRow.locator('dd').filter({ hasText: /^Claude Code CLI · claude$/ })).toBeVisible();
});
