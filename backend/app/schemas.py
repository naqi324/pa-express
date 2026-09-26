"""Pydantic schemas — the API contract. Mirrored 1:1 in src/types.ts."""

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
# Every reasoning effort any provider accepts. The model catalog in
# engines/catalog.py says which ones each model and auth method supports.
ReasoningEffort = Literal["none", "low", "medium", "high", "xhigh", "max", "ultra"]
AuthMethod = Literal["cli", "api_key", "bedrock"]
ClaudeAuthMethod = AuthMethod
OpenAiGptAuthMethod = Literal["cli", "api_key"]
BedrockCredentials = Literal["profile", "access_keys"]
ClaudeModelId = Literal[
    "claude-fable-5-1",
    "claude-opus-5-5",
    "claude-sonnet-5",
    "claude-haiku-4-5-20251001",
]
OpenAiGptModelId = Literal["gpt-6-astra", "gpt-6-sol", "gpt-6-luna"]
LlmProvider = Literal["anthropic", "bedrock", "openai"]


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
    provider: LlmProvider
    engine: EngineId
    engine_label: str
    auth_method: Optional[AuthMethod] = None
    model_id: Optional[str] = None
    effort: Optional[ReasoningEffort] = None
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
    auth_method: Optional[AuthMethod] = None
    model_id: Optional[str] = None
    effort: Optional[ReasoningEffort] = None


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


def _blank_to_none(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class ClaudeConfigInput(BaseModel):
    """Session settings for Anthropic Claude. Secrets are write-only."""

    # Commands and endpoints are server configuration; reject any attempt to set them.
    model_config = ConfigDict(extra="forbid")

    auth_method: ClaudeAuthMethod
    model_id: ClaudeModelId
    # None selects the model's default effort (or no effort for models without one).
    effort: Optional[ReasoningEffort] = None
    api_key: Optional[str] = None
    bedrock_region: str = Field(default="us-west-2", pattern=r"^[a-z]{2}(-[a-z]+)+-\d+$")
    bedrock_credentials: BedrockCredentials = "profile"
    aws_profile: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None

    @field_validator("bedrock_region", mode="before")
    @classmethod
    def strip_region(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator(
        "api_key",
        "aws_profile",
        "aws_access_key_id",
        "aws_secret_access_key",
        "aws_session_token",
    )
    @classmethod
    def blank_secret_is_absent(cls, value: Optional[str]) -> Optional[str]:
        return _blank_to_none(value)


class OpenAiGptConfigInput(BaseModel):
    """Session settings for OpenAI GPT. The API key is write-only."""

    model_config = ConfigDict(extra="forbid")

    auth_method: OpenAiGptAuthMethod
    model_id: OpenAiGptModelId
    effort: Optional[ReasoningEffort] = None
    api_key: Optional[str] = None

    @field_validator("api_key")
    @classmethod
    def blank_secret_is_absent(cls, value: Optional[str]) -> Optional[str]:
        return _blank_to_none(value)


class ClaudeConfig(BaseModel):
    """Claude settings echoed back to the UI. Never carries a secret."""

    auth_method: ClaudeAuthMethod
    model_id: ClaudeModelId
    effort: Optional[ReasoningEffort] = None
    command: str = "claude"
    api_key_hint: Optional[str] = None
    api_key_configured: bool = False
    bedrock_region: str = "us-west-2"
    bedrock_credentials: BedrockCredentials = "profile"
    aws_profile: str = ""
    access_key_id_hint: Optional[str] = None
    access_keys_configured: bool = False
    is_override: bool = False


class OpenAiGptConfig(BaseModel):
    """OpenAI GPT settings echoed back to the UI. Never carries a secret."""

    auth_method: OpenAiGptAuthMethod
    model_id: OpenAiGptModelId
    effort: Optional[ReasoningEffort] = None
    command: str = "codex"
    api_key_hint: Optional[str] = None
    api_key_configured: bool = False
    is_override: bool = False


class ModelMethodSupport(BaseModel):
    """How one auth method runs one model."""

    auth_method: AuthMethod
    # The id sent to the provider (Bedrock uses a regional inference profile).
    provider_model_id: str
    efforts: list[ReasoningEffort] = Field(default_factory=list)
    # The provider's documented default; None when the model takes no effort.
    default_effort: Optional[ReasoningEffort] = None


class ModelOption(BaseModel):
    id: str
    label: str
    summary: str
    methods: list[ModelMethodSupport] = Field(default_factory=list)


class AuthMethodOption(BaseModel):
    """One way to reach an engine's provider, with a cheap readiness probe."""

    id: AuthMethod
    label: str
    summary: str
    ready: bool
    note: str = ""


class EngineConfig(BaseModel):
    """The provider configuration for one engine, with the options its form offers."""

    engine: EngineId
    # Empty for the rules engine, which needs no provider.
    auth_methods: list[AuthMethodOption] = Field(default_factory=list)
    models: list[ModelOption] = Field(default_factory=list)
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
