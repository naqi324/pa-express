// Typed fetch client for Prior Auth Express.
// Mirrors backend/app/schemas.py; session state rides the
// pa_express_session cookie (credentials: 'include').

import type {
  ApiErrorDetail,
  ClaudeConfigInput,
  CoverageCheck,
  Determination,
  EngineConfig,
  EngineId,
  EngineInfo,
  EvaluationStatus,
  HealthStatus,
  HumanActionRequest,
  Letter,
  LetterUpdateRequest,
  LlmInspection,
  OpenAiGptConfigInput,
  PARequest,
  PARequestSummary,
  PolicyDocument,
  ScenarioSummary,
  Urgency,
} from '../types';

export class ApiError extends Error {
  status: number;
  code: string;
  retryGuidance: string | null;
  correlationId: string | null;

  constructor(payload: ApiErrorDetail) {
    super(payload.message);
    this.name = 'ApiError';
    this.status = payload.status;
    this.code = payload.code;
    this.retryGuidance = payload.retry_guidance;
    this.correlationId = payload.correlation_id;
  }
}

// The backend error envelope, read defensively: any field can be missing when
// a proxy or crash returns a body the backend did not write.
interface ErrorEnvelope {
  error?: Partial<ApiErrorDetail> | null;
}

interface CreateRequestBody {
  scenario_id: string;
  engine: EngineId;
  urgency?: Urgency;
}

async function readErrorDetail(response: Response): Promise<ApiErrorDetail> {
  const envelope: ErrorEnvelope | null = await response.json().catch(() => null);
  const detail = envelope?.error;

  return {
    status: detail?.status ?? response.status,
    code: detail?.code ?? 'HTTP_ERROR',
    message: detail?.message ?? `Request failed with status ${response.status}`,
    retry_guidance: detail?.retry_guidance ?? null,
    correlation_id: detail?.correlation_id ?? null,
  };
}

async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;

  try {
    response = await fetch(path, {
      credentials: 'include',
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError({
      status: 0,
      code: 'NETWORK_ERROR',
      message: 'Cannot reach the Prior Auth Express backend. Is it running on port 8004?',
      retry_guidance: 'Start the backend with `pnpm dev:backend`, then retry.',
      correlation_id: null,
    });
  }

  if (!response.ok) {
    throw new ApiError(await readErrorDetail(response));
  }

  // SAFETY: every caller names the response model that backend/app/main.py
  // declares for this route, and FastAPI validates the body against it.
  return (await response.json()) as T;
}

function requestPath(requestId: string, suffix = ''): string {
  return `/api/requests/${encodeURIComponent(requestId)}${suffix}`;
}

function createRequestBody(scenarioId: string, engine: EngineId, urgency: Urgency | null): CreateRequestBody {
  const body: CreateRequestBody = { scenario_id: scenarioId, engine };

  if (urgency !== null) body.urgency = urgency;

  return body;
}

export const api = {
  health: () => apiJson<HealthStatus>('/api/health'),
  scenarios: () => apiJson<ScenarioSummary[]>('/api/scenarios'),
  engines: () => apiJson<EngineInfo[]>('/api/engines'),
  requests: () => apiJson<PARequestSummary[]>('/api/requests'),
  createRequest: (scenarioId: string, engine: EngineId, urgency: Urgency | null) =>
    apiJson<PARequest>('/api/requests', {
      method: 'POST',
      body: JSON.stringify(createRequestBody(scenarioId, engine, urgency)),
    }),
  seedRequests: (engine: EngineId) =>
    apiJson<PARequestSummary[]>('/api/requests/seed', {
      method: 'POST',
      body: JSON.stringify({ engine }),
    }),
  request: (id: string) => apiJson<PARequest>(requestPath(id)),
  startEvaluation: (requestId: string, engine: EngineId) =>
    apiJson<EvaluationStatus>(requestPath(requestId, '/evaluations'), {
      method: 'POST',
      body: JSON.stringify({ engine }),
    }),
  evaluation: (requestId: string, evalId: string) =>
    apiJson<EvaluationStatus>(requestPath(requestId, `/evaluations/${encodeURIComponent(evalId)}`)),
  determination: (requestId: string) => apiJson<Determination>(requestPath(requestId, '/determination')),
  llmInspection: (requestId: string) => apiJson<LlmInspection>(requestPath(requestId, '/llm-inspection')),
  submitAction: (requestId: string, action: HumanActionRequest) =>
    apiJson<PARequest>(requestPath(requestId, '/actions'), {
      method: 'POST',
      body: JSON.stringify(action),
    }),
  // The server dates the letter in the reviewer's own time zone.
  letter: (requestId: string) =>
    apiJson<Letter>(
      `${requestPath(requestId, '/letter')}?tz=${encodeURIComponent(Intl.DateTimeFormat().resolvedOptions().timeZone)}`,
    ),
  updateLetter: (requestId: string, update: LetterUpdateRequest) =>
    apiJson<Letter>(requestPath(requestId, '/letter'), {
      method: 'POST',
      body: JSON.stringify(update),
    }),
  policy: (policyId: string) => apiJson<PolicyDocument>(`/api/policies/${encodeURIComponent(policyId)}`),
  coverage: (policyId: string) => apiJson<CoverageCheck>(`/api/coverage/${encodeURIComponent(policyId)}`),
  engineConfig: () => apiJson<EngineConfig[]>('/api/engine-config'),
  setAnthropicClaudeConfig: (config: ClaudeConfigInput) =>
    apiJson<EngineConfig>('/api/engine-config/anthropic-claude', {
      method: 'PUT',
      body: JSON.stringify(config),
    }),
  clearAnthropicClaudeConfig: () => apiJson<EngineConfig>('/api/engine-config/anthropic-claude', { method: 'DELETE' }),
  setOpenAiGptConfig: (config: OpenAiGptConfigInput) =>
    apiJson<EngineConfig>('/api/engine-config/openai-gpt', {
      method: 'PUT',
      body: JSON.stringify(config),
    }),
  clearOpenAiGptConfig: () => apiJson<EngineConfig>('/api/engine-config/openai-gpt', { method: 'DELETE' }),
};

const POLL_INTERVAL_MS = 900;

const POLL_TIMEOUT_MS = 120_000;

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Polls GET /api/requests/{id}/evaluations/{evalId} every ~900ms until the
 * evaluation reaches `completed` or `failed` (or the timeout elapses).
 * `onTick` fires with each intermediate status so callers can render the
 * live "analyzing" state.
 */
export async function pollEvaluation(
  requestId: string,
  evalId: string,
  onTick?: (status: EvaluationStatus) => void,
): Promise<EvaluationStatus> {
  const startedAt = Date.now();

  for (;;) {
    const status = await api.evaluation(requestId, evalId);

    onTick?.(status);

    if (status.status === 'completed' || status.status === 'failed') {
      return status;
    }

    if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
      throw new ApiError({
        status: 0,
        code: 'EVALUATION_TIMEOUT',
        message: 'The evaluation did not finish within two minutes.',
        retry_guidance: 'Re-run the determination or check the backend logs.',
        correlation_id: null,
      });
    }

    await sleep(POLL_INTERVAL_MS);
  }
}
