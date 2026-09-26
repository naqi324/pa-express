// Display-only presentation per engine. Backend labels stay in the verdict
// attribution for audit; the settings screen and top bar use these names.

import type {
  ClaudeModelId,
  ClaudeReasoningEffort,
  EngineId,
  OpenAiGptModelId,
  OpenAiReasoningEffort,
} from './types';

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
    tagline: 'Claude on Bedrock with the prior-auth review skill.',
    how: 'Reads submitted documents, maps evidence to criteria, and returns strict auditable JSON.',
    readyNote: 'Ready — using the configured Claude model and reasoning effort.',
  },
  openai_gpt: {
    name: 'OpenAI GPT',
    tagline: 'GPT through the signed-in Codex CLI.',
    how: 'Uses the same review skill and strict auditable JSON contract.',
    readyNote: 'Ready — using the configured GPT model and reasoning effort.',
  },
};

export const ENGINE_ORDER: EngineId[] = ['offline', 'anthropic_claude', 'openai_gpt'];

export interface EffortOption<Effort extends string> {
  label: string;
  value: Effort;
}

export const BEDROCK_REGIONS = ['us-west-2', 'us-east-1', 'us-east-2', 'eu-central-1', 'eu-west-1', 'ap-southeast-2'];

export const CLAUDE_MODELS = [
  'us.anthropic.claude-sonnet-5',
  'us.anthropic.claude-opus-4-8',
  'us.anthropic.claude-haiku-4-5-20251001-v1:0',
  'us.anthropic.claude-fable-5',
] satisfies ClaudeModelId[];

export const CLAUDE_EFFORTS = [
  { label: 'High', value: 'high' },
  { label: 'Medium', value: 'medium' },
  { label: 'Low', value: 'low' },
  { label: 'Max', value: 'max' },
] satisfies EffortOption<ClaudeReasoningEffort>[];

export const OPENAI_GPT_MODELS = ['gpt-5.5', 'gpt-5.4', 'gpt-5.4-mini'] satisfies OpenAiGptModelId[];

export const OPENAI_GPT_EFFORTS = [
  { label: 'Extra high', value: 'xhigh' },
  { label: 'High', value: 'high' },
  { label: 'Medium', value: 'medium' },
  { label: 'Low', value: 'low' },
] satisfies EffortOption<OpenAiReasoningEffort>[];

export function effortLabel<Effort extends string>(options: EffortOption<Effort>[], effort: Effort): string {
  return options.find((option) => option.value === effort)?.label ?? effort;
}
