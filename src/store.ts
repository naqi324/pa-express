// Plain reactive app store (no pinia, no router). One module-level singleton
// shared by every component via import.

import { computed, reactive } from 'vue';
import { api, ApiError, pollEvaluation, sleep } from './api/client';
import type {
  ClaudeConfigInput,
  Determination,
  EngineConfig,
  EngineId,
  EngineInfo,
  EvaluationStatus,
  HealthStatus,
  HumanActionRequest,
  Letter,
  LlmInspection,
  OpenAiGptConfigInput,
  PARequest,
  PARequestSummary,
  RuntimeCapabilities,
  ScenarioSummary,
  Urgency,
} from './types';

export type ViewName = 'queue' | 'new-request' | 'workspace' | 'letter-audit' | 'connection';

interface AppState {
  view: ViewName;
  health: HealthStatus | null;
  scenarios: ScenarioSummary[];
  engines: EngineInfo[];
  engineConfig: EngineConfig[];
  requests: PARequestSummary[];
  currentRequest: PARequest | null;
  currentDetermination: Determination | null;
  currentLlmInspection: LlmInspection | null;
  currentLetter: Letter | null;
  defaultEngine: EngineId;
  evaluating: boolean;
  evaluationNotice: string | null;
  globalError: string | null;
  loadingRequests: boolean;
}

const state = reactive<AppState>({
  view: 'queue',
  health: null,
  scenarios: [],
  engines: [],
  engineConfig: [],
  requests: [],
  currentRequest: null,
  currentDetermination: null,
  currentLlmInspection: null,
  currentLetter: null,
  defaultEngine: 'offline',
  evaluating: false,
  evaluationNotice: null,
  globalError: null,
  loadingRequests: false,
});

function describeError(error: Error): string {
  if (error instanceof ApiError && error.retryGuidance) {
    return `${error.message} ${error.retryGuidance}`;
  }

  return error.message;
}

function isNotFound(error: Error): boolean {
  return error instanceof ApiError && error.status === 404;
}

// Runs one store operation. A failure becomes the global error toast and
// resolves to null, so callers only branch on success.
async function attempt<T>(operation: () => Promise<T>): Promise<T | null> {
  try {
    return await operation();
  } catch (error) {
    state.globalError = error instanceof Error ? describeError(error) : 'Something went wrong.';

    return null;
  }
}

function clearGlobalError(): void {
  state.globalError = null;
}

function navigate(view: ViewName): void {
  state.view = view;
  clearGlobalError();
}

function setDefaultEngine(engine: EngineId): void {
  state.defaultEngine = engine;
}

function resetCaseDetail(): void {
  state.currentDetermination = null;
  state.currentLlmInspection = null;
  state.currentLetter = null;
}

async function refreshHealth(): Promise<void> {
  const health = await attempt(() => api.health());

  state.health = health;
}

async function refreshScenarios(): Promise<void> {
  const scenarios = await attempt(() => api.scenarios());

  if (scenarios) state.scenarios = scenarios;
}

async function refreshEngines(): Promise<void> {
  const engines = await attempt(() => api.engines());

  if (engines) state.engines = engines;
}

async function refreshRequests(): Promise<void> {
  state.loadingRequests = true;

  const requests = await attempt(() => api.requests());

  if (requests) {
    state.requests = requests;
    clearGlobalError();
  }

  state.loadingRequests = false;
}

// Silent variant for background polling; never surfaces transient errors.
async function pollRequestsOnce(): Promise<void> {
  try {
    state.requests = await api.requests();
  } catch {
    // The next tick retries.
  }
}

async function loadDetermination(id: string): Promise<void> {
  try {
    state.currentDetermination = await api.determination(id);
  } catch (error) {
    // DETERMINATION_NOT_READY (404) is the normal mid-analysis state.
    if (!(error instanceof Error && isNotFound(error))) throw error;
  }
}

async function loadLlmInspection(id: string): Promise<LlmInspection | null> {
  try {
    state.currentLlmInspection = await api.llmInspection(id);
  } catch (error) {
    state.currentLlmInspection = null;

    if (!(error instanceof Error && isNotFound(error))) {
      state.globalError = error instanceof Error ? describeError(error) : 'Something went wrong.';
    }
  }

  return state.currentLlmInspection;
}

const OPEN_POLL_INTERVAL_MS = 1200;

function isWatching(id: string): boolean {
  const status = state.currentRequest?.id === id ? state.currentRequest.processing_status : null;

  return status === 'queued' || status === 'analyzing';
}

// If the opened case is still analyzing, keep watching it until the verdict lands.
async function watchCurrentRequest(id: string): Promise<void> {
  while (isWatching(id)) {
    await sleep(OPEN_POLL_INTERVAL_MS);

    if (state.currentRequest?.id !== id) return;

    try {
      const request = await api.request(id);

      if (state.currentRequest?.id !== id) return;

      state.currentRequest = request;

      if (request.processing_status === 'completed') {
        await loadDetermination(id);
        await loadLlmInspection(id);
        void refreshRequests();
      }
    } catch {
      // Transient; keep watching.
    }
  }
}

async function openRequest(id: string): Promise<void> {
  const opened = await attempt(async () => {
    state.currentRequest = await api.request(id);
    resetCaseDetail();
    await loadDetermination(id);
    await loadLlmInspection(id);

    return true;
  });

  if (!opened) return;

  navigate('workspace');
  void watchCurrentRequest(id);
}

async function createRequest(scenarioId: string, urgency: Urgency | null): Promise<boolean> {
  const request = await attempt(() => api.createRequest(scenarioId, state.defaultEngine, urgency));

  if (!request) return false;

  state.currentRequest = request;
  resetCaseDetail();
  await refreshRequests();
  navigate('workspace');
  void watchCurrentRequest(request.id);

  return true;
}

async function seedRequests(): Promise<boolean> {
  const requests = await attempt(() => api.seedRequests(state.defaultEngine));

  if (requests) state.requests = requests;

  return requests !== null;
}

async function runEvaluation(engine?: EngineId): Promise<EvaluationStatus | null> {
  const request = state.currentRequest;

  if (!request) return null;

  state.evaluating = true;
  state.evaluationNotice = null;

  const finished = await attempt(async () => {
    const started = await api.startEvaluation(request.id, engine ?? state.defaultEngine);

    resetCaseDetail();

    const result = await pollEvaluation(request.id, started.id);

    if (result.error) state.evaluationNotice = result.error;

    if (result.determination) {
      state.currentDetermination = result.determination;
      await loadLlmInspection(request.id);
    }

    // Refresh the request so processing status and the audit trail are current.
    state.currentRequest = await api.request(request.id);
    await refreshRequests();

    return result;
  });

  state.evaluating = false;

  return finished;
}

async function submitAction(action: HumanActionRequest): Promise<boolean> {
  const request = state.currentRequest;

  if (!request) return false;

  const updated = await attempt(() => api.submitAction(request.id, action));

  if (!updated) return false;

  state.currentRequest = updated;
  await refreshRequests();

  return true;
}

async function loadLetter(): Promise<boolean> {
  const request = state.currentRequest;

  if (!request) return false;

  const letter = await attempt(() => api.letter(request.id));

  if (letter) state.currentLetter = letter;

  return letter !== null;
}

async function saveLetter(body: string, markReady: boolean): Promise<boolean> {
  const request = state.currentRequest;

  if (!request) return false;

  const saved = await attempt(async () => {
    state.currentLetter = await api.updateLetter(request.id, {
      body,
      action: markReady ? 'mark_ready' : 'save',
    });
    state.currentRequest = await api.request(request.id);

    if (markReady) await refreshRequests();

    return true;
  });

  return saved === true;
}

async function refreshEngineConfig(): Promise<void> {
  const config = await attempt(() => api.engineConfig());

  if (config) state.engineConfig = config;
}

function mergeEngineConfig(config: EngineConfig): void {
  const index = state.engineConfig.findIndex((entry) => entry.engine === config.engine);

  if (index === -1) state.engineConfig.push(config);
  else state.engineConfig[index] = config;
}

async function applyEngineConfig(operation: () => Promise<EngineConfig>): Promise<boolean> {
  const config = await attempt(operation);

  if (!config) return false;

  mergeEngineConfig(config);
  await refreshEngines();

  return true;
}

function saveAnthropicClaudeConfig(config: ClaudeConfigInput): Promise<boolean> {
  return applyEngineConfig(() => api.setAnthropicClaudeConfig(config));
}

function resetAnthropicClaudeConfig(): Promise<boolean> {
  return applyEngineConfig(() => api.clearAnthropicClaudeConfig());
}

function saveOpenAiGptConfig(config: OpenAiGptConfigInput): Promise<boolean> {
  return applyEngineConfig(() => api.setOpenAiGptConfig(config));
}

function resetOpenAiGptConfig(): Promise<boolean> {
  return applyEngineConfig(() => api.clearOpenAiGptConfig());
}

async function bootstrap(): Promise<void> {
  await Promise.all([refreshHealth(), refreshRequests(), refreshEngines(), refreshScenarios()]);
}

const capabilities = computed<RuntimeCapabilities | null>(() => state.health?.capabilities ?? null);

const hasActiveEvaluations = computed(() =>
  state.requests.some((request) => request.processing_status === 'queued' || request.processing_status === 'analyzing'),
);

export function useAppStore() {
  return {
    state,
    capabilities,
    hasActiveEvaluations,
    navigate,
    clearGlobalError,
    bootstrap,
    refreshHealth,
    refreshScenarios,
    refreshEngines,
    refreshRequests,
    pollRequestsOnce,
    setDefaultEngine,
    openRequest,
    createRequest,
    seedRequests,
    runEvaluation,
    submitAction,
    loadLetter,
    loadLlmInspection,
    saveLetter,
    refreshEngineConfig,
    saveAnthropicClaudeConfig,
    resetAnthropicClaudeConfig,
    saveOpenAiGptConfig,
    resetOpenAiGptConfig,
  };
}
