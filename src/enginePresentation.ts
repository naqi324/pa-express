// Display-only presentation per engine. Backend labels stay in the verdict
// attribution for audit; the settings screen and top bar use these names.
// Models and efforts come from the backend catalog in EngineConfig.models.

import type { AuthMethod, EngineId, ModelMethodSupport, ModelOption, ReasoningEffort } from './types';

export interface EnginePresentation {
  name: string;
  tagline: string;
  how: string;
  readyNote: string;
}

export const ENGINE_PRESENTATION: Record<EngineId, EnginePresentation> = {
  offline: {
    name: 'Rules engine',
    tagline: 'Fixed coverage rules. No model or network call.',
    how: 'Checks case facts against each policy criterion locally.',
    readyNote: 'Ready — always available. This is the automatic fallback for every other engine.',
  },
  anthropic_claude: {
    name: 'Anthropic Claude',
    tagline: 'Claude through the Claude Code CLI, an Anthropic API key, or AWS Bedrock.',
    how: 'Reads submitted documents, maps evidence to criteria, and returns strict auditable JSON.',
    readyNote: 'Ready — using the configured connection, model, and reasoning effort.',
  },
  openai_gpt: {
    name: 'OpenAI GPT',
    tagline: 'GPT through the Codex CLI or an OpenAI API key.',
    how: 'Uses the same review skill and strict auditable JSON contract.',
    readyNote: 'Ready — using the configured connection, model, and reasoning effort.',
  },
};

export const ENGINE_ORDER: EngineId[] = ['offline', 'anthropic_claude', 'openai_gpt'];

export const BEDROCK_REGIONS = ['us-west-2', 'us-east-1', 'us-east-2', 'eu-central-1', 'eu-west-1', 'ap-southeast-2'];

export const EFFORT_LABELS: Record<ReasoningEffort, string> = {
  none: 'None',
  low: 'Low',
  medium: 'Medium',
  high: 'High',
  xhigh: 'Extra high',
  max: 'Max',
  ultra: 'Ultra',
};

// A null effort means the model takes no effort setting.
export function effortLabel(effort: ReasoningEffort | null): string {
  return effort === null ? 'Not adjustable' : EFFORT_LABELS[effort];
}

export function methodSupport(model: ModelOption | undefined, method: AuthMethod): ModelMethodSupport | undefined {
  return model?.methods.find((support) => support.auth_method === method);
}

// Where the chosen effort goes, so a reviewer can match it to the engine-call payload.
export function effortHint(engine: EngineId, method: AuthMethod): string {
  if (engine === 'openai_gpt') {
    return method === 'api_key'
      ? 'Sent to the Responses API as reasoning.effort.'
      : 'Passed to the codex CLI as model_reasoning_effort.';
  }

  if (method === 'cli') return 'Passed to the claude CLI as --effort.';

  if (method === 'api_key') return 'Sent to the Claude API as the adaptive thinking effort.';

  return 'Sent to Bedrock as the adaptive thinking effort.';
}
