// API contract types. Mirrors backend/app/schemas.py 1:1.

export type PlanType = 'commercial' | 'medicare_advantage' | 'medicaid';

export type Urgency = 'standard' | 'expedited';

export type ProcessingStatus = 'queued' | 'analyzing' | 'completed' | 'failed';

export type DeterminationStatus = 'in_review' | 'approved' | 'pended' | 'referred_md';

export type CriterionStatus = 'MET' | 'NOT_MET' | 'INSUFFICIENT';

export type Recommendation = 'approve' | 'pend';

export type EngineId = 'offline' | 'anthropic_claude' | 'openai_gpt';

export type HumanAction = 'approve' | 'pend' | 'refer_md';

export type LetterType = 'approval' | 'pend';

export type PolicySourceType = 'ncd' | 'lcd';

export type ClaudeReasoningEffort = 'low' | 'medium' | 'high' | 'max';

export type OpenAiReasoningEffort = 'low' | 'medium' | 'high' | 'xhigh';

export type ClaudeModelId =
  | 'us.anthropic.claude-sonnet-5'
  | 'us.anthropic.claude-opus-4-8'
  | 'us.anthropic.claude-haiku-4-5-20251001-v1:0'
  | 'us.anthropic.claude-fable-5';

export type OpenAiGptModelId = 'gpt-5.5' | 'gpt-5.4' | 'gpt-5.4-mini';

export type BedrockAuthMethod = 'profile' | 'access_keys';

export type EngineAuthStyle = 'none' | 'aws_bedrock' | 'codex_cli';

// Engine payloads are free-form JSON; they are only rendered, never read by key.
export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

export interface Member {
  name: string;
  member_id: string;
  date_of_birth: string;
  plan_type: PlanType;
  plan_name: string;
}

export interface Provider {
  name: string;
  npi: string;
  specialty: string;
  organization: string;
}

export interface ServiceRequest {
  description: string;
  cpt_codes: string[];
  icd10_codes: string[];
  setting: string;
  urgency: Urgency;
}

export interface ClinicalDocument {
  id: string;
  title: string;
  doc_type: string;
  date: string;
  text: string;
}

export interface AuditEvent {
  timestamp: string;
  actor: string;
  event: string;
  from_state: string | null;
  to_state: string | null;
}

export interface PolicyRef {
  source_type: PolicySourceType;
  code: string;
  title: string;
  version: string | null;
  ncd_id: string | null;
  ncd_version: string | null;
  lcd_id: string | null;
  contractor: string | null;
  source_url: string | null;
}

export interface PARequest {
  id: string;
  scenario_id: string | null;
  member: Member;
  provider: Provider;
  service: ServiceRequest;
  clinical_documents: ClinicalDocument[];
  processing_status: ProcessingStatus;
  determination_status: DeterminationStatus;
  policy: PolicyRef | null;
  sla_due_at: string;
  created_at: string;
  audit_trail: AuditEvent[];
  scenario_hint: string | null;
  auth_valid_from: string | null;
  auth_valid_through: string | null;
  requested_items: string[];
  md_summary: string | null;
  notified_at: string | null;
  latest_eval_id: string | null;
}

export interface PARequestSummary {
  id: string;
  scenario_id: string | null;
  member_name: string;
  service_description: string;
  cpt_codes: string[];
  plan_type: PlanType;
  urgency: Urgency;
  processing_status: ProcessingStatus;
  determination_status: DeterminationStatus;
  recommendation: Recommendation | null;
  sla_due_at: string;
  created_at: string;
  notified_at: string | null;
}

export interface EvidenceCitation {
  quote: string;
  source_document: string;
  document_date: string | null;
}

export interface CriterionEvaluation {
  criterion_id: string;
  criterion_text: string;
  depth: number;
  logic: string | null;
  status: CriterionStatus;
  evidence: EvidenceCitation[];
  rationale: string;
  confidence: number;
}

export interface CoverageCheck {
  policy_id: string;
  source_type: PolicySourceType;
  version: string | null;
  title: string;
  covered: boolean;
  summary: string;
  source_url: string;
  ncd_id: string | null;
  ncd_version: string | null;
  lcd_id: string | null;
  contractor: string | null;
}

export interface Attribution {
  engine: EngineId;
  engine_label: string;
  model_id: string | null;
  policy_source_type: PolicySourceType | null;
  policy_code: string | null;
  policy_title: string | null;
  policy_version: string | null;
  ncd_id: string | null;
  ncd_version: string | null;
  lcd_id: string | null;
  contractor: string | null;
  evaluated_at: string;
}

export interface Determination {
  id: string;
  request_id: string;
  recommendation: Recommendation;
  rationale: string;
  criteria_evaluations: CriterionEvaluation[];
  criteria_met: string;
  gaps: string[];
  coverage_check: CoverageCheck | null;
  attribution: Attribution;
}

export interface LlmTrace {
  provider: 'bedrock' | 'openai';
  engine: EngineId;
  engine_label: string;
  model_id: string | null;
  created_at: string;
  status: 'succeeded' | 'failed';
  prompt: string;
  request_payload: { [key: string]: JsonValue };
  raw_response: string;
  response_text: string;
  parsed_response: { [key: string]: JsonValue } | null;
  error: string | null;
  redactions: string[];
}

export interface LlmInspection {
  request_id: string;
  evaluation_id: string;
  final_engine: EngineId;
  final_engine_label: string;
  traces: LlmTrace[];
}

export interface EvaluationStatus {
  id: string;
  request_id: string;
  status: ProcessingStatus;
  engine: EngineId;
  determination: Determination | null;
  error: string | null;
}

export interface EngineInfo {
  id: EngineId;
  label: string;
  description: string;
  available: boolean;
  availability_note: string;
  model_id: string | null;
}

export interface Letter {
  request_id: string;
  letter_type: LetterType;
  subject: string;
  body: string;
  generated_at: string;
  status: 'draft' | 'ready';
}

export interface HumanActionRequest {
  action: HumanAction;
  note: string;
  actor: string;
  requested_items?: string[];
  valid_from?: string | null;
  valid_through?: string | null;
}

export interface LetterUpdateRequest {
  body: string;
  action: 'save' | 'mark_ready';
}

export interface ClaudeConfigInput {
  auth_method: BedrockAuthMethod;
  region: string;
  model_id: ClaudeModelId;
  effort: ClaudeReasoningEffort;
  aws_profile?: string | null;
  aws_access_key_id?: string | null;
  aws_secret_access_key?: string | null;
  aws_session_token?: string | null;
}

export interface OpenAiGptConfigInput {
  command: string;
  model_id: OpenAiGptModelId;
  effort: OpenAiReasoningEffort;
}

export interface ClaudeConfig {
  auth_method: BedrockAuthMethod;
  region: string;
  model_id: ClaudeModelId;
  effort: ClaudeReasoningEffort;
  aws_profile: string;
  access_key_id_hint: string | null;
  access_keys_configured: boolean;
  is_override: boolean;
}

export interface OpenAiGptConfig {
  command: string;
  model_id: OpenAiGptModelId;
  effort: OpenAiReasoningEffort;
  is_override: boolean;
}

export interface EngineConfig {
  engine: EngineId;
  auth_style: EngineAuthStyle;
  anthropic_claude: ClaudeConfig | null;
  openai_gpt: OpenAiGptConfig | null;
}

export interface RuntimeCapabilities {
  anthropic_claude_enabled: boolean;
  openai_gpt_enabled: boolean;
}

export interface HealthStatus {
  status: string;
  version: string;
  capabilities: RuntimeCapabilities;
}

export interface ScenarioSummary {
  id: string;
  title: string;
  subtitle: string;
  expected_path: Recommendation;
  policy_label: string;
  plan_type: PlanType;
}

export interface PolicyCriterion {
  id: string;
  text: string;
  category: string | null;
  required: boolean;
  logic: string | null;
  options: string[];
  check_hints: string[];
}

export interface PolicySection {
  key: string;
  title: string;
  paragraphs: string[];
}

export interface ReviewCriterion {
  criterion_id: string;
  criterion_text: string;
  depth: number;
  logic: string | null;
}

export interface ReviewCriteriaSet {
  scenario_id: string;
  scenario_title: string;
  criteria: ReviewCriterion[];
}

export interface PolicyDocument {
  policy_id: string;
  source_type: PolicySourceType;
  code: string;
  title: string;
  version: string | null;
  contractor: string | null;
  effective_date: string | null;
  last_updated: string | null;
  benefit_category: string | null;
  coverage_model: string | null;
  summary: string;
  source_url: string | null;
  api_url: string | null;
  local_file_available: boolean;
  criteria: PolicyCriterion[];
  non_covered: string[];
  notes: string[];
  sections: PolicySection[];
  review_criteria: ReviewCriteriaSet[];
}

export interface ApiErrorDetail {
  status: number;
  code: string;
  message: string;
  retry_guidance: string | null;
  correlation_id: string | null;
}

export interface ApiErrorBody {
  error: ApiErrorDetail;
}
