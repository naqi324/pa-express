"""Demo scenario data for Prior Auth Express.

Contract (backend core depends on exactly this):
- SCENARIOS: list[dict] — each dict carries the static parts of a PARequest
  (see backend/app/schemas.py) plus authoring extras:
    "id": scenario id, e.g. "ncd-150-3-dxa"
    "title": short display title (ScenarioSummary.title)
    "summary_subtitle": str (ScenarioSummary.subtitle)
    "member" / "provider" / "service" / "clinical_documents": schema-shaped dicts
    "policy": PolicyRef-shaped dict (source_type "ncd" or "lcd")
    "expected_path": "approve" | "pend"
    "criteria": ordered list of {criterion_id, criterion_text, depth, logic}
    "criteria_facts": dict criterion_id -> {status: MET|NOT_MET|INSUFFICIENT,
        evidence: [{quote, source_document, document_date}], rationale, confidence}
- get_scenarios() -> list[dict]
- get_scenario(scenario_id: str) -> dict | None
Dynamic fields (request id, created_at, sla_due_at, audit_trail, statuses) are
filled in by the case store at request-creation time — never stored here.

Data invariants (backend/tests/test_scenarios.py checks each one):
- Every evidence quote appears verbatim inside the text of the clinical
  document named by its source_document, and document_date matches that
  document's date. To make this hold by construction, quotes are defined as
  constants and interpolated into the document texts below.
- Every criteria_facts key is a criterion_id in "criteria", and every
  criterion has a fact. criterion_id values are unique within a scenario.
- expected_path is "approve" only when every fact is MET; otherwise "pend".
- A MET fact carries at least one evidence citation.
- "policy" names a Medicare NCD (ncd_id, ncd_version) or LCD (lcd_id,
  contractor). "code" is the display code ("NCD 150.3", "LCD L12345") and
  "version" is the policy document version.
- Scenario ids are unique.

Adding an LCD scenario: define its quote constants, document texts, and a
_SCENARIO_* dict in a new section below the NCD scenarios, then append it to
SCENARIOS. Put the matching lcd-*.json file in data/cms-coverage/ so the
policy lookup and the Offline coverage check can read it; no code changes
are needed.

All members, providers, NPIs, and identifiers are synthetic.
"""

# ---------------------------------------------------------------------------
# Scenario 1 — NCD 150.3 DXA bone mineral density (clean Medicare approval)
# ---------------------------------------------------------------------------

_DXA_Q_ORDERED = (
    "After evaluation of her fracture risk factors and review of the medically "
    "appropriate options, I am ordering a central DXA scan of the lumbar spine and hip."
)
_DXA_Q_DEVICE = (
    "Study to be performed on the facility's FDA-cleared Hologic Horizon A central DXA "
    "bone densitometer, with formal interpretation of results by the supervising radiologist."
)
_DXA_Q_SUPERVISION = (
    "The study will be performed under the required level of physician supervision in "
    "accordance with 42 CFR 410.32(b) and facility imaging policy."
)
_DXA_Q_CATEGORY = (
    "Ms. Olsen is a postmenopausal woman who is not receiving estrogen replacement "
    "therapy, and I have determined that she is estrogen-deficient and at clinical risk "
    "for osteoporosis based on her medical history and examination findings."
)
_DXA_Q_FREQUENCY = (
    "Claims and imaging history review confirms no prior bone mass measurement of any "
    "modality for this member."
)

_DXA_OFFICE_NOTE = f"""Office visit note — Internal Medicine
Patient: Margaret Olsen. Date of service: 06/12/2026.
Chief complaint: Preventive visit; concern for bone health.
History of present illness: Ms. Olsen is a 68-year-old woman, natural menopause at age
51, never treated with hormone replacement therapy. Family history is notable for a
maternal osteoporotic hip fracture at age 74. She reports a low dietary calcium intake
(estimated 500 mg/day), a mostly sedentary lifestyle since retirement, three units of
alcohol per week, and a 22-year remote smoking history (quit at age 46). She has lost
approximately 2 cm of measured height over the last five years (163 cm to 161 cm). No
prior fragility fracture, no back pain, and no glucocorticoid, aromatase-inhibitor, or
anticonvulsant use.
Risk stratification: FRAX 10-year probability without BMD is 18 percent for major
osteoporotic fracture and 3.2 percent for hip fracture. Recent labs — serum calcium
9.4 mg/dL, 25-hydroxyvitamin D 28 ng/mL, TSH normal, creatinine 0.8 mg/dL — show no
secondary cause requiring workup before densitometry.
Examination: Height 161 cm, weight 54 kg, BMI 20.8. Mild thoracic kyphosis. No spinal
tenderness; no focal neurologic deficit.
Assessment: {_DXA_Q_CATEGORY}
Plan: {_DXA_Q_ORDERED} Counseled on calcium and vitamin D supplementation and
weight-bearing exercise. Results will guide any decision on pharmacologic therapy."""

_DXA_ORDER = f"""Diagnostic imaging order — Bone mineral density study
Patient: Margaret Olsen. Order date: 06/12/2026.
Ordering provider: Alan Whitfield, MD (Internal Medicine), NPI 1932406857, the treating
physician for this beneficiary.
Study requested: Dual-energy X-ray absorptiometry (DXA), axial skeleton (lumbar spine
L1-L4 and left hip), CPT 77080. Diagnosis codes Z13.820 (screening for osteoporosis) and
Z78.0 (asymptomatic postmenopausal status).
{_DXA_Q_DEVICE}
{_DXA_Q_SUPERVISION}
Clinical indication: Estrogen-deficient postmenopausal woman at clinical risk for
osteoporosis; first-time baseline assessment to establish T-scores and direct therapy.
Reference database: manufacturer young-adult normative data; results to be reported as
T-scores and Z-scores per ISCD 2019 Official Positions."""

_DXA_HISTORY = f"""Utilization history summary — Imaging and claims review
Patient: Margaret Olsen. Review date: 06/13/2026. Prepared by: UM intake automation.
{_DXA_Q_FREQUENCY}
Lookback: 84 months of available Medicare Advantage claims reviewed. No prior DXA (CPT
77080/77081/77085), quantitative CT (77078), or bone sonometry (76977) appears for this
member. The 23-month frequency standard at 42 CFR 410.31(c) is therefore not implicated
for this first-ever study, and no medical-necessity exception for early re-testing is
required. No duplicate or overlapping bone-density order is pending with another
provider."""

_SCENARIO_DXA = {
    "id": "ncd-150-3-dxa",
    "title": "DXA bone density — Medicare NCD 150.3",
    "summary_subtitle": "68-year-old postmenopausal woman, baseline bone-density study ordered",
    "scenario_hint": "Flagship NCD scenario: every 42 CFR 410.31 condition is documented.",
    "expected_path": "approve",
    "member": {
        "name": "Margaret Olsen",
        "member_id": "MBR-83920157",
        "date_of_birth": "1958-03-14",
        "plan_type": "medicare_advantage",
        "plan_name": "SecureCare Medicare Advantage HMO",
    },
    "provider": {
        "name": "Dr. Alan Whitfield MD",
        "npi": "1932406857",
        "specialty": "Internal Medicine",
        "organization": "Lakeside Primary Care",
    },
    "service": {
        "description": "DXA bone mineral density study, axial skeleton",
        "cpt_codes": ["77080"],
        "icd10_codes": ["Z13.820", "Z78.0"],
        "setting": "outpatient",
        "urgency": "standard",
    },
    "policy": {
        "source_type": "ncd",
        "code": "NCD 150.3",
        "title": "Bone (Mineral) Density Studies",
        "version": "2",
        "ncd_id": "150.3",
        "ncd_version": "2",
        "source_url": "https://www.cms.gov/medicare-coverage-database/view/ncd.aspx?ncdid=256&ncdver=2",
    },
    "clinical_documents": [
        {
            "id": "dxa-office-note",
            "title": "Office visit note — Internal Medicine",
            "doc_type": "office_visit_note",
            "date": "2026-06-12",
            "text": _DXA_OFFICE_NOTE,
        },
        {
            "id": "dxa-order",
            "title": "Diagnostic imaging order — Bone mineral density study",
            "doc_type": "order",
            "date": "2026-06-12",
            "text": _DXA_ORDER,
        },
        {
            "id": "dxa-history",
            "title": "Utilization history summary — Imaging and claims review",
            "doc_type": "utilization_summary",
            "date": "2026-06-13",
            "text": _DXA_HISTORY,
        },
    ],
    "criteria": [
        {
            "criterion_id": "BMD-1",
            "criterion_text": "Ordered by the physician or qualified nonphysician practitioner treating the beneficiary, following an evaluation of the need for the measurement (42 CFR 410.31(b)(1)(i)).",
            "depth": 0,
            "logic": None,
        },
        {
            "criterion_id": "BMD-2",
            "criterion_text": "Performed with an FDA-cleared or FDA-approved bone densitometer or sonometer (other than single- or dual-photon absorptiometry), including a physician's interpretation of the results (42 CFR 410.31(a)).",
            "depth": 0,
            "logic": None,
        },
        {
            "criterion_id": "BMD-3",
            "criterion_text": "Performed under the appropriate level of physician supervision per 42 CFR 410.32(b) (42 CFR 410.31(b)(1)(ii)).",
            "depth": 0,
            "logic": None,
        },
        {
            "criterion_id": "BMD-4",
            "criterion_text": "Beneficiary meets at least one qualifying category (42 CFR 410.31(d)): estrogen-deficient woman at clinical risk for osteoporosis; vertebral abnormality on x-ray; glucocorticoid therapy >= 5.0 mg prednisone-equivalent/day for > 3 months; primary hyperparathyroidism; or monitoring of FDA-approved osteoporosis drug therapy.",
            "depth": 0,
            "logic": "1 or more of the following",
        },
        {
            "criterion_id": "BMD-5",
            "criterion_text": "At least 23 months have passed since the last covered bone mass measurement, or a medical-necessity exception applies (42 CFR 410.31(c)).",
            "depth": 0,
            "logic": None,
        },
    ],
    "criteria_facts": {
        "BMD-1": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _DXA_Q_ORDERED,
                    "source_document": "Office visit note — Internal Medicine",
                    "document_date": "2026-06-12",
                }
            ],
            "rationale": "The treating internist personally evaluated fracture risk and ordered the study, satisfying the ordering condition.",
            "confidence": 96,
        },
        "BMD-2": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _DXA_Q_DEVICE,
                    "source_document": "Diagnostic imaging order — Bone mineral density study",
                    "document_date": "2026-06-12",
                }
            ],
            "rationale": "Central DXA on an FDA-cleared densitometer with named physician interpretation satisfies the technical condition.",
            "confidence": 95,
        },
        "BMD-3": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _DXA_Q_SUPERVISION,
                    "source_document": "Diagnostic imaging order — Bone mineral density study",
                    "document_date": "2026-06-12",
                }
            ],
            "rationale": "The order attests to the required supervision level under 42 CFR 410.32(b).",
            "confidence": 92,
        },
        "BMD-4": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _DXA_Q_CATEGORY,
                    "source_document": "Office visit note — Internal Medicine",
                    "document_date": "2026-06-12",
                }
            ],
            "rationale": "The treating physician documents the estrogen-deficient-woman-at-clinical-risk qualifying category; only one category is required.",
            "confidence": 97,
        },
        "BMD-5": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _DXA_Q_FREQUENCY,
                    "source_document": "Utilization history summary — Imaging and claims review",
                    "document_date": "2026-06-13",
                }
            ],
            "rationale": "First-ever bone mass measurement; the 23-month frequency standard is satisfied by definition.",
            "confidence": 94,
        },
    },
}

# ---------------------------------------------------------------------------
# Scenario 2 — NCD 20.32 TAVR (Medicare, multi-attestation approval)
# ---------------------------------------------------------------------------

_TAVR_Q_ECHO = (
    "Severe aortic stenosis with aortic valve area 0.7 cm2, mean gradient 46 mmHg, and "
    "peak aortic jet velocity 4.4 m/s."
)
_TAVR_Q_SYMPTOMS = (
    "She reports progressive exertional dyspnea, fatigue, and one episode of near-syncope, "
    "consistent with NYHA class III symptoms attributable to aortic stenosis."
)
_TAVR_Q_DEVICE = (
    "The procedure will be performed with the Edwards SAPIEN 3 transcatheter heart valve "
    "system, which holds FDA premarket approval for the planned indication."
)
_TAVR_Q_TEAM = (
    "The multidisciplinary heart team — cardiac surgery, interventional cardiology, cardiac "
    "anesthesia, imaging cardiology, advanced practice providers, valve program nursing, and "
    "program administration — reviewed the case in valve conference."
)
_TAVR_Q_DUAL_EVAL = (
    "Dr. Okafor (cardiac surgery) and Dr. Chen (interventional cardiology) each "
    "independently examined the patient face-to-face, evaluated her suitability for SAVR, "
    "TAVR, and medical therapy, and documented and shared their rationale with the heart "
    "team; STS predicted risk of mortality is 9.1 percent."
)
_TAVR_Q_JOINT_OP = (
    "The heart team's interventional cardiologist and cardiac surgeon will jointly "
    "participate in the intra-operative technical aspects of the TAVR procedure."
)
_TAVR_Q_FACILITY = (
    "The hospital maintains on-site heart valve surgery and interventional cardiology "
    "programs and a post-procedure cardiovascular intensive care unit staffed by personnel "
    "experienced in managing open-heart valve patients."
)
_TAVR_Q_VOLUME = (
    "In the prior 12 months the program performed 68 aortic valve replacements, including "
    "31 TAVR procedures, and 412 percutaneous coronary interventions, with two physicians "
    "holding cardiac surgery privileges and three holding interventional cardiology "
    "privileges."
)
_TAVR_Q_REGISTRY = (
    "The heart team and hospital participate in the STS/ACC TVT Registry, enrolling TAVR "
    "patients consecutively with follow-up for at least one year."
)
_TAVR_Q_BENEFIT = (
    "The heart team concluded that no existing comorbidity precludes the expected benefit "
    "from correction of the aortic stenosis, with anticipated survival beyond 12 months and "
    "meaningful quality-of-life improvement."
)

_TAVR_ECHO_REPORT = f"""Transthoracic echocardiogram report
Patient: Eleanor Vance. Study date: 06/10/2026. Interpreting physician: R. Menon, MD.
Indication: Progressive dyspnea; evaluate aortic valve.
Findings: Heavily calcified trileaflet aortic valve with severely restricted leaflet
excursion. {_TAVR_Q_ECHO} Dimensionless index 0.22. Left ventricular ejection fraction
55 percent with normal cavity size and concentric remodeling; stroke volume index
38 mL/m2 (normal-flow, high-gradient physiology). Grade 1 diastolic dysfunction.
Estimated right ventricular systolic pressure 34 mmHg. Mild mitral regurgitation, trace
aortic regurgitation. No pericardial effusion.
Impression: Severe symptomatic aortic stenosis (ICD-10 I35.0) by valve area, mean
gradient, and peak velocity criteria. Correlates with gated cardiac CT: annulus 468 mm2
(24.4 mm mean diameter), Agatston aortic-valve calcium score 3120, and suitable
transfemoral iliofemoral access bilaterally."""

_TAVR_HEART_TEAM_NOTE = f"""Heart team conference note — Structural Heart Program
Patient: Eleanor Vance, 84-year-old female. Conference date: 06/18/2026.
{_TAVR_Q_SYMPTOMS}
{_TAVR_Q_TEAM}
{_TAVR_Q_DUAL_EVAL}
Frailty and geriatric assessment: gait speed 0.7 m/s (5-meter walk), grip strength
16 kg, Katz ADL 6/6 (independent), Clinical Frailty Scale 4, Mini-Cog 4/5; albumin
3.9 g/dL. Comorbidities: controlled hypertension, CKD stage 3a (eGFR 52), paroxysmal
atrial fibrillation on anticoagulation; no prior sternotomy, no severe COPD, no cirrhosis.
Consensus: transfemoral TAVR is preferred over SAVR given age, frailty, porcelain-free
but heavily calcified valve, and elevated surgical risk. {_TAVR_Q_JOINT_OP}
{_TAVR_Q_BENEFIT}"""

_TAVR_ATTESTATION = f"""Facility and registry attestation letter — St. Vincent Medical Center
Re: Eleanor Vance. Date: 06/19/2026. Signed: Valve Program Medical Director.
{_TAVR_Q_DEVICE}
{_TAVR_Q_FACILITY}
{_TAVR_Q_VOLUME}
{_TAVR_Q_REGISTRY}
Tracked registry outcomes include stroke, all-cause mortality, transient ischemic
attacks, major vascular events, acute kidney injury, repeat aortic valve procedures,
new permanent pacemaker implantation, and quality of life."""

_SCENARIO_TAVR = {
    "id": "ncd-20-32-tavr",
    "title": "TAVR — Medicare NCD 20.32",
    "summary_subtitle": "84-year-old with severe symptomatic aortic stenosis, heart-team TAVR referral",
    "scenario_hint": "Complex NCD showcase: nine coverage conditions spanning clinical, team, facility, and registry attestations.",
    "expected_path": "approve",
    "member": {
        "name": "Eleanor Vance",
        "member_id": "MBR-47201938",
        "date_of_birth": "1942-01-22",
        "plan_type": "medicare_advantage",
        "plan_name": "SecureCare Medicare Advantage HMO",
    },
    "provider": {
        "name": "Dr. Marcus Chen MD",
        "npi": "1750392648",
        "specialty": "Interventional Cardiology",
        "organization": "St. Vincent Heart & Vascular Institute",
    },
    "service": {
        "description": "Transcatheter aortic valve replacement (TAVR), transfemoral approach",
        "cpt_codes": ["33361"],
        "icd10_codes": ["I35.0"],
        "setting": "inpatient",
        "urgency": "standard",
    },
    "policy": {
        "source_type": "ncd",
        "code": "NCD 20.32",
        "title": "Transcatheter Aortic Valve Replacement (TAVR)",
        "version": "2",
        "ncd_id": "20.32",
        "ncd_version": "2",
        "source_url": "https://www.cms.gov/medicare-coverage-database/view/ncd.aspx?ncdid=355&ncdver=2",
    },
    "clinical_documents": [
        {
            "id": "tavr-echo",
            "title": "Transthoracic echocardiogram report",
            "doc_type": "imaging_report",
            "date": "2026-06-10",
            "text": _TAVR_ECHO_REPORT,
        },
        {
            "id": "tavr-heart-team",
            "title": "Heart team conference note — Structural Heart Program",
            "doc_type": "conference_note",
            "date": "2026-06-18",
            "text": _TAVR_HEART_TEAM_NOTE,
        },
        {
            "id": "tavr-attestation",
            "title": "Facility and registry attestation letter — St. Vincent Medical Center",
            "doc_type": "attestation",
            "date": "2026-06-19",
            "text": _TAVR_ATTESTATION,
        },
    ],
    "criteria": [
        {
            "criterion_id": "TAVR-1",
            "criterion_text": "Symptomatic severe aortic valve stenosis.",
            "depth": 0,
            "logic": "All of the following",
        },
        {
            "criterion_id": "TAVR-2",
            "criterion_text": "Procedure furnished with a complete valve and implantation system that has received FDA premarket approval for its FDA-approved indication.",
            "depth": 0,
            "logic": None,
        },
        {
            "criterion_id": "TAVR-3",
            "criterion_text": "Patient is under the pre- and post-operative care of a cohesive multidisciplinary heart team including a cardiac surgeon and an interventional cardiologist experienced in aortic stenosis.",
            "depth": 0,
            "logic": None,
        },
        {
            "criterion_id": "TAVR-4",
            "criterion_text": "The cardiac surgeon and interventional cardiologist have each independently examined the patient face-to-face, evaluated suitability for SAVR, TAVR, or medical therapy, and documented and shared their rationale with the heart team.",
            "depth": 0,
            "logic": None,
        },
        {
            "criterion_id": "TAVR-5",
            "criterion_text": "The heart team's interventional cardiologist(s) and cardiac surgeon(s) jointly participate in the intra-operative technical aspects of TAVR.",
            "depth": 0,
            "logic": None,
        },
        {
            "criterion_id": "TAVR-6",
            "criterion_text": "Hospital has appropriate infrastructure: on-site heart valve surgery and interventional cardiology programs and a post-procedure intensive care facility experienced with open-heart valve patients.",
            "depth": 0,
            "logic": None,
        },
        {
            "criterion_id": "TAVR-7",
            "criterion_text": "Hospital program meets NCD volume qualifications (>= 50 AVRs/year including >= 20 TAVRs in the prior year, or >= 100 AVRs/2 years including >= 40 TAVRs; >= 2 cardiac surgeons; >= 1 interventional cardiologist; >= 300 PCIs/year).",
            "depth": 0,
            "logic": None,
        },
        {
            "criterion_id": "TAVR-8",
            "criterion_text": "Heart team and hospital participate in a prospective, national, audited registry (STS/ACC TVT Registry) with consecutive enrollment and >= 1 year follow-up.",
            "depth": 0,
            "logic": None,
        },
        {
            "criterion_id": "TAVR-9",
            "criterion_text": "Existing co-morbidities would not preclude the expected benefit from correction of the aortic stenosis (NCD Section C exclusion check).",
            "depth": 0,
            "logic": None,
        },
    ],
    "criteria_facts": {
        "TAVR-1": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _TAVR_Q_ECHO,
                    "source_document": "Transthoracic echocardiogram report",
                    "document_date": "2026-06-10",
                },
                {
                    "quote": _TAVR_Q_SYMPTOMS,
                    "source_document": "Heart team conference note — Structural Heart Program",
                    "document_date": "2026-06-18",
                },
            ],
            "rationale": "Echo meets severe-stenosis thresholds (valve area <= 1.0 cm2, gradient >= 40 mmHg, velocity >= 4.0 m/s) and NYHA class III symptoms are documented.",
            "confidence": 97,
        },
        "TAVR-2": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _TAVR_Q_DEVICE,
                    "source_document": "Facility and registry attestation letter — St. Vincent Medical Center",
                    "document_date": "2026-06-19",
                }
            ],
            "rationale": "A named PMA-approved valve system is specified for an FDA-approved indication.",
            "confidence": 95,
        },
        "TAVR-3": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _TAVR_Q_TEAM,
                    "source_document": "Heart team conference note — Structural Heart Program",
                    "document_date": "2026-06-18",
                }
            ],
            "rationale": "A cohesive multidisciplinary heart team with the required composition is documented.",
            "confidence": 94,
        },
        "TAVR-4": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _TAVR_Q_DUAL_EVAL,
                    "source_document": "Heart team conference note — Structural Heart Program",
                    "document_date": "2026-06-18",
                }
            ],
            "rationale": "Independent face-to-face evaluations by both specialists with documented shared rationale and STS risk score.",
            "confidence": 96,
        },
        "TAVR-5": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _TAVR_Q_JOINT_OP,
                    "source_document": "Heart team conference note — Structural Heart Program",
                    "document_date": "2026-06-18",
                }
            ],
            "rationale": "Joint intra-operative participation is attested in the procedure plan.",
            "confidence": 92,
        },
        "TAVR-6": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _TAVR_Q_FACILITY,
                    "source_document": "Facility and registry attestation letter — St. Vincent Medical Center",
                    "document_date": "2026-06-19",
                }
            ],
            "rationale": "Facility attests to the required on-site programs and ICU capability.",
            "confidence": 93,
        },
        "TAVR-7": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _TAVR_Q_VOLUME,
                    "source_document": "Facility and registry attestation letter — St. Vincent Medical Center",
                    "document_date": "2026-06-19",
                }
            ],
            "rationale": "Reported volumes (68 AVRs incl. 31 TAVRs; 412 PCIs) and physician staffing exceed every NCD threshold for experienced programs.",
            "confidence": 94,
        },
        "TAVR-8": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _TAVR_Q_REGISTRY,
                    "source_document": "Facility and registry attestation letter — St. Vincent Medical Center",
                    "document_date": "2026-06-19",
                }
            ],
            "rationale": "TVT Registry participation with consecutive enrollment and one-year follow-up is attested.",
            "confidence": 95,
        },
        "TAVR-9": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _TAVR_Q_BENEFIT,
                    "source_document": "Heart team conference note — Structural Heart Program",
                    "document_date": "2026-06-18",
                }
            ],
            "rationale": "Heart team explicitly documents expected benefit and anticipated survival beyond 12 months, clearing the Section C exclusion.",
            "confidence": 91,
        },
    },
}


# ---------------------------------------------------------------------------
# Scenario registry. Append new NCD or LCD scenarios here, in display order.
# ---------------------------------------------------------------------------

SCENARIOS: list[dict] = [
    _SCENARIO_DXA,
    _SCENARIO_TAVR,
]


def get_scenarios() -> list[dict]:
    return SCENARIOS


def get_scenario(scenario_id: str) -> dict | None:
    for scenario in SCENARIOS:
        if scenario["id"] == scenario_id or scenario.get("scenario_id") == scenario_id:
            return scenario
    return None
