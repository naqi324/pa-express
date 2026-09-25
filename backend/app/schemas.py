"""Pydantic schemas — the API contract. Mirrored 1:1 in src/types.ts."""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

PlanType = Literal["commercial", "medicare_advantage", "medicaid"]
Urgency = Literal["standard", "expedited"]
ProcessingStatus = Literal["queued", "analyzing", "completed", "failed"]
DeterminationStatus = Literal["in_review", "approved", "pended", "referred_md"]
CriterionStatus = Literal["MET", "NOT_MET", "INSUFFICIENT"]
Recommendation = Literal["approve", "pend"]
EngineId = Literal["offline", "anthropic_claude", "openai_gpt"]
HumanAction = Literal["approve", "pend", "refer_md"]
LetterType = Literal["approval", "pend"]
PolicySourceType = Literal["ncd", "lcd"]
ClaudeReasoningEffort = Literal["low", "medium", "high", "max"]
OpenAiReasoningEffort = Literal["low", "medium", "high", "xhigh"]
ClaudeModelId = Literal[
    "us.anthropic.claude-sonnet-5",
    "us.anthropic.claude-opus-4-8",
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "us.anthropic.claude-fable-5",
]
OpenAiGptModelId = Literal["gpt-5.5", "gpt-5.4", "gpt-5.4-mini"]


class Member(BaseModel):
    name: str
    member_id: str
    date_of_birth: str
    plan_type: PlanType
    plan_name: str


class Provider(BaseModel):
    name: str
    npi: str
    specialty: str
    organization: str


class ServiceRequest(BaseModel):
    description: str
    cpt_codes: list[str]
    icd10_codes: list[str]
    setting: str
    urgency: Urgency


class ClinicalDocument(BaseModel):
    id: str
    title: str
    doc_type: str
    date: str
    text: str


class AuditEvent(BaseModel):
    timestamp: str
    actor: str
    event: str
    from_state: Optional[str] = None
    to_state: Optional[str] = None


class PolicyRef(BaseModel):
    """The Medicare coverage policy a request is reviewed against."""

    source_type: PolicySourceType
    # Display code, e.g. "NCD 150.3" or "LCD L12345".
    code: str
    title: str
    version: Optional[str] = None
    ncd_id: Optional[str] = None
    ncd_version: Optional[str] = None
    lcd_id: Optional[str] = None
    # LCDs are issued by a Medicare Administrative Contractor.
    contractor: Optional[str] = None
    source_url: Optional[str] = None


class PARequest(BaseModel):
    id: str
    scenario_id: Optional[str] = None
    member: Member
    provider: Provider
    service: ServiceRequest
    clinical_documents: list[ClinicalDocument]
    processing_status: ProcessingStatus
    determination_status: DeterminationStatus
    policy: Optional[PolicyRef] = None
    sla_due_at: str
    created_at: str
    audit_trail: list[AuditEvent]
    scenario_hint: Optional[str] = None
    # Set by human dispositions.
    auth_valid_from: Optional[str] = None
    auth_valid_through: Optional[str] = None
    requested_items: list[str] = Field(default_factory=list)
    md_summary: Optional[str] = None
    # Set when the provider letter is finalized.
    notified_at: Optional[str] = None
    # Most recent evaluation for this request (evaluations auto-start at intake).
    latest_eval_id: Optional[str] = None


class PARequestSummary(BaseModel):
    id: str
    scenario_id: Optional[str] = None
    member_name: str
    service_description: str
    cpt_codes: list[str]
    plan_type: PlanType
    urgency: Urgency
    processing_status: ProcessingStatus
    determination_status: DeterminationStatus
    recommendation: Optional[Recommendation] = None
    sla_due_at: str
    created_at: str
    notified_at: Optional[str] = None


class EvidenceCitation(BaseModel):
    quote: str
    source_document: str
    document_date: Optional[str] = None


class CriterionEvaluation(BaseModel):
    criterion_id: str
    criterion_text: str
    depth: int = 0
    logic: Optional[str] = None
    status: CriterionStatus
    evidence: list[EvidenceCitation] = Field(default_factory=list)
    rationale: str = ""
    confidence: int = 0


class CoverageCheck(BaseModel):
    """Coverage summary read from a local file in data/cms-coverage/."""

    # Canonical policy id: "150.3" for an NCD, "L12345" for an LCD.
    policy_id: str
    source_type: PolicySourceType
    version: Optional[str] = None
    title: str
    covered: bool
    summary: str
    source_url: str
    ncd_id: Optional[str] = None
    ncd_version: Optional[str] = None
    lcd_id: Optional[str] = None
    contractor: Optional[str] = None


class Attribution(BaseModel):
    engine: EngineId
    engine_label: str
    model_id: Optional[str] = None
    policy_source_type: Optional[PolicySourceType] = None
    policy_code: Optional[str] = None
    policy_title: Optional[str] = None
    policy_version: Optional[str] = None
    ncd_id: Optional[str] = None
    ncd_version: Optional[str] = None
    lcd_id: Optional[str] = None
    contractor: Optional[str] = None
    evaluated_at: str


class Determination(BaseModel):
    id: str
    request_id: str
    recommendation: Recommendation
    rationale: str
    criteria_evaluations: list[CriterionEvaluation]
    criteria_met: str
    gaps: list[str] = Field(default_factory=list)
    coverage_check: Optional[CoverageCheck] = None
    attribution: Attribution


class LlmTrace(BaseModel):
    provider: Literal["bedrock", "openai"]
    engine: EngineId
    engine_label: str
    model_id: Optional[str] = None
    created_at: str
    status: Literal["succeeded", "failed"]
    prompt: str
    request_payload: dict[str, Any]
    raw_response: str
    response_text: str = ""
    parsed_response: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    redactions: list[str] = Field(default_factory=list)


class LlmInspection(BaseModel):
    request_id: str
    evaluation_id: str
    final_engine: EngineId
    final_engine_label: str
    traces: list[LlmTrace] = Field(default_factory=list)


class EvaluationStatus(BaseModel):
    id: str
    request_id: str
    status: ProcessingStatus
    engine: EngineId
    determination: Optional[Determination] = None
    error: Optional[str] = None


class EngineInfo(BaseModel):
    id: EngineId
    label: str
    description: str
    available: bool
    availability_note: str = ""
    model_id: Optional[str] = None


class Letter(BaseModel):
    request_id: str
    letter_type: LetterType
    subject: str
    body: str
    generated_at: str
    status: Literal["draft", "ready"] = "draft"


class HumanActionRequest(BaseModel):
    action: HumanAction
    note: str = ""
    actor: str = "UM Reviewer"
    # Pend: the specific items the provider must submit (CMS-0057-F specificity).
    requested_items: list[str] = Field(default_factory=list)
    # Approve: authorization validity window (ISO dates).
    valid_from: Optional[str] = None
    valid_through: Optional[str] = None


class LetterUpdateRequest(BaseModel):
    body: str
    action: Literal["save", "mark_ready"] = "save"


class EvaluationRequest(BaseModel):
    engine: EngineId = "offline"


BedrockAuthMethod = Literal["profile", "access_keys"]


class ClaudeConfigInput(BaseModel):
    """Runtime Claude-on-Bedrock settings for a session (secrets are write-only)."""

    auth_method: BedrockAuthMethod
    region: str
    model_id: ClaudeModelId
    effort: ClaudeReasoningEffort = "high"
    aws_profile: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None

    @field_validator("region")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("model_id", mode="before")
    @classmethod
    def normalize_bedrock_model_id(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().removesuffix("[1m]")
        return value


class OpenAiGptConfigInput(BaseModel):
    command: str
    model_id: OpenAiGptModelId
    effort: OpenAiReasoningEffort = "xhigh"

    @field_validator("command")
    @classmethod
    def validate_codex_command(cls, value: str) -> str:
        normalized = value.strip()
        if normalized != "codex":
            raise ValueError("OpenAI GPT runs through the fixed local codex CLI command.")
        return normalized

    @field_validator("model_id")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        return value.strip()


class ClaudeConfig(BaseModel):
    """Claude provider settings echoed back to the UI (never returns secrets)."""

    auth_method: BedrockAuthMethod
    region: str
    model_id: ClaudeModelId
    effort: ClaudeReasoningEffort = "high"
    aws_profile: str = ""
    access_key_id_hint: Optional[str] = None
    access_keys_configured: bool = False
    is_override: bool = False


class OpenAiGptConfig(BaseModel):
    command: str
    model_id: OpenAiGptModelId
    effort: OpenAiReasoningEffort = "xhigh"
    is_override: bool = False


class EngineConfig(BaseModel):
    """The provider configuration for one engine, in the shape its UI form needs."""

    engine: EngineId
    # auth_style tells the UI which form to render for this engine.
    auth_style: Literal["none", "aws_bedrock", "codex_cli"]
    anthropic_claude: Optional[ClaudeConfig] = None
    openai_gpt: Optional[OpenAiGptConfig] = None


class RuntimeCapabilities(BaseModel):
    anthropic_claude_enabled: bool
    openai_gpt_enabled: bool


class HealthStatus(BaseModel):
    status: str
    version: str
    capabilities: RuntimeCapabilities


class ScenarioSummary(BaseModel):
    id: str
    title: str
    subtitle: str
    expected_path: Recommendation
    policy_label: str
    plan_type: PlanType


class PolicyCriterion(BaseModel):
    """One coverage criterion as written in the local policy file."""

    id: str
    text: str
    category: Optional[str] = None
    required: bool = True
    logic: Optional[str] = None
    options: list[str] = Field(default_factory=list)
    check_hints: list[str] = Field(default_factory=list)


class PolicySection(BaseModel):
    """A block of source text from the policy file (for example, the NCD full text)."""

    key: str
    title: str
    paragraphs: list[str] = Field(default_factory=list)


class ReviewCriterion(BaseModel):
    """A criterion that the engines evaluate, as authored in a scenario."""

    criterion_id: str
    criterion_text: str
    depth: int = 0
    logic: Optional[str] = None


class ReviewCriteriaSet(BaseModel):
    """The authored review criteria of one scenario that cites this policy."""

    scenario_id: str
    scenario_title: str
    criteria: list[ReviewCriterion] = Field(default_factory=list)


class PolicyDocument(BaseModel):
    """A Medicare NCD or LCD, assembled only from local files and scenario data."""

    policy_id: str
    source_type: PolicySourceType
    code: str
    title: str
    version: Optional[str] = None
    contractor: Optional[str] = None
    effective_date: Optional[str] = None
    last_updated: Optional[str] = None
    benefit_category: Optional[str] = None
    coverage_model: Optional[str] = None
    summary: str = ""
    source_url: Optional[str] = None
    api_url: Optional[str] = None
    # False when no local policy file exists and the document is built from
    # scenario metadata only.
    local_file_available: bool = True
    criteria: list[PolicyCriterion] = Field(default_factory=list)
    non_covered: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    sections: list[PolicySection] = Field(default_factory=list)
    review_criteria: list[ReviewCriteriaSet] = Field(default_factory=list)


class ApiErrorDetail(BaseModel):
    status: int
    code: str
    message: str
    retry_guidance: Optional[str] = None
    correlation_id: Optional[str] = None


class ApiErrorBody(BaseModel):
    error: ApiErrorDetail
