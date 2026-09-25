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

Scenarios 1-2 cite NCDs. Scenarios 3-5 cite LCDs, and their member and
provider sit in a state that the LCD's contractor serves.

Adding a scenario: define its quote constants, document texts, and a
_SCENARIO_* dict in a new section below the existing scenarios, then append
it to SCENARIOS. Put the matching ncd-*.json or lcd-*.json file in
data/cms-coverage/ so the policy lookup and the Offline coverage check can
read it; no code changes are needed.

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
# LCD scenarios. An LCD binds only the states of its contractor, so each
# member, provider, and plan sits in one of those states. The Member schema
# has no state field; the state appears in the documents and the hint. Each
# plan applies the local Medicare LCD as its medical policy.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Scenario 3 — LCD L34220 lumbar spine MRI (Noridian JF, Oregon; approval)
# ---------------------------------------------------------------------------

_LMRI_Q_ORDER = (
    "Order electronically signed and dated 09/10/2026 by Sofia Lindqvist, DO, the "
    "treating physician."
)
_LMRI_Q_HISTORY = (
    "Low back pain began 8 weeks ago after he lifted a heavy box at work, and the pain "
    "radiates down the left posterolateral leg to the top of the foot; pain is 7/10 and "
    "the Oswestry Disability Index is 48 percent."
)
_LMRI_Q_NEGATIVES = (
    "He denies fever, chills, unexplained weight loss, any history of cancer, bowel or "
    "bladder changes, and saddle anesthesia."
)
_LMRI_Q_MEDS = (
    "He also completed naproxen 500 mg twice daily and a 6-day methylprednisolone taper "
    "without lasting relief."
)
_LMRI_Q_PRIOR_IMAGING = (
    "Lumbar radiographs on 08/06/2026 showed mild L4-5 disc space narrowing and no "
    "fracture; he has had no prior lumbar MRI or CT."
)
_LMRI_Q_EXAM = (
    "Left straight leg raise is positive at 40 degrees, and the sitting knee extension "
    "test reproduces his left leg pain; left great toe extensor (EHL) strength is 4/5; "
    "light touch is decreased over the dorsum of the left foot; patellar and Achilles "
    "reflexes are 2+ and symmetric; calf circumference is equal on both sides."
)
_LMRI_Q_RED_FLAG = (
    "Left L5 radiculopathy with nerve root compromise and clinically significant motor "
    "weakness of the left great toe extensor, which are red flags that support advanced "
    "imaging."
)
_LMRI_Q_DECISION = (
    "The MRI result will decide the level for a transforaminal epidural steroid "
    "injection or the need for a spine surgery referral."
)
_LMRI_Q_PT = (
    "After 10 visits over 6 weeks plus a daily home exercise program, the patient reports "
    "no meaningful improvement in leg pain or function."
)
_LMRI_Q_UNIT = (
    "Study to be performed without contrast on an FDA-cleared 1.5 tesla MRI unit, "
    "operated within its approved parameters, at Cascade Imaging Center, an accredited "
    "imaging facility."
)
_LMRI_Q_SAFETY = (
    "MRI safety screen is negative: no pacemaker or other implanted device, no aneurysm "
    "clips, and no metal fragments; no contrast will be given, so contrast allergy does "
    "not apply."
)

_LMRI_OFFICE_NOTE = f"""Office visit note — Physical Medicine and Rehabilitation
Patient: Daniel Reyes. Date of service: 09/10/2026. Location: Ridgeline Spine &
Rehabilitation, Portland, Oregon.
Chief complaint: Low back pain with left leg pain.
History of present illness: Mr. Reyes is a 58-year-old warehouse supervisor.
{_LMRI_Q_HISTORY} Pain is worse with sitting and bending, and it does not get worse
when he lies flat. {_LMRI_Q_NEGATIVES}
Treatment to date: Physical therapy from 07/24/2026 to 09/04/2026 (see the physical
therapy discharge summary). {_LMRI_Q_MEDS}
Prior imaging: {_LMRI_Q_PRIOR_IMAGING}
Examination: Antalgic gait; heel walking is weak on the left. {_LMRI_Q_EXAM} No spinal
tenderness to percussion. Hip range of motion is full and painless.
Assessment: {_LMRI_Q_RED_FLAG} ICD-10-CM M54.16.
Plan: MRI of the lumbar spine without contrast. {_LMRI_Q_DECISION} Continue the home
exercise program. Follow up after the MRI."""

_LMRI_ORDER = f"""Diagnostic imaging order — Lumbar spine MRI
Patient: Daniel Reyes. Date of birth: 04/09/1968. Order date: 09/10/2026.
Ordering provider: Sofia Lindqvist, DO (Physical Medicine and Rehabilitation), NPI
1467203958, Ridgeline Spine & Rehabilitation, Portland, Oregon.
Study requested: MRI of the lumbar spine without contrast, CPT 72148. Diagnosis code
M54.16.
Clinical question: Left L5 radiculopathy with great toe extensor weakness after 6 weeks
of failed conservative care. Find the level and cause of nerve root compression to plan
a transforaminal epidural steroid injection or a surgical referral.
{_LMRI_Q_UNIT}
{_LMRI_Q_SAFETY}
{_LMRI_Q_ORDER}"""

_LMRI_PT_DISCHARGE = f"""Physical therapy discharge summary
Patient: Daniel Reyes. Discharge date: 09/04/2026. Therapist: Megan Albright, PT, DPT,
Willamette Physical Therapy, Portland, Oregon.
Referral diagnosis: Low back pain with left leg pain.
Plan of care: Start of care 07/24/2026. Directional preference exercises, core
stabilization, nerve mobility exercises, and manual therapy, with a daily home exercise
program.
Outcome: {_LMRI_Q_PT} The Oswestry Disability Index was 46 percent at the start of care
and 48 percent at discharge. Left great toe extensor weakness persists.
Recommendation: Discharged from therapy and returned to the referring physician for
further workup."""

_SCENARIO_LUMBAR_MRI = {
    "id": "lcd-l34220-lumbar-mri",
    "title": "Lumbar spine MRI — Medicare LCD L34220",
    "summary_subtitle": "58-year-old Oregon member with left L5 radiculopathy after 6 weeks of failed conservative care",
    "scenario_hint": "LCD scenario (Noridian, JE/JF): the commercial plan applies LCD L34220 to Oregon members. Every criterion is documented, and a red flag meets the indication.",
    "expected_path": "approve",
    "member": {
        "name": "Daniel Reyes",
        "member_id": "MBR-61830274",
        "date_of_birth": "1968-04-09",
        "plan_type": "commercial",
        "plan_name": "Pinecrest Health Commercial PPO",
    },
    "provider": {
        "name": "Dr. Sofia Lindqvist DO",
        "npi": "1467203958",
        "specialty": "Physical Medicine and Rehabilitation",
        "organization": "Ridgeline Spine & Rehabilitation",
    },
    "service": {
        "description": "Lumbar spine MRI without contrast",
        "cpt_codes": ["72148"],
        "icd10_codes": ["M54.16"],
        "setting": "outpatient",
        "urgency": "standard",
    },
    "policy": {
        "source_type": "lcd",
        "code": "LCD L34220",
        "title": "Lumbar MRI",
        "version": "40",
        "lcd_id": "L34220",
        "contractor": "Noridian Healthcare Solutions, LLC",
        "source_url": "https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=34220&ver=40",
    },
    "clinical_documents": [
        {
            "id": "lmri-office-note",
            "title": "Office visit note — Physical Medicine and Rehabilitation",
            "doc_type": "office_visit_note",
            "date": "2026-09-10",
            "text": _LMRI_OFFICE_NOTE,
        },
        {
            "id": "lmri-order",
            "title": "Diagnostic imaging order — Lumbar spine MRI",
            "doc_type": "order",
            "date": "2026-09-10",
            "text": _LMRI_ORDER,
        },
        {
            "id": "lmri-pt-discharge",
            "title": "Physical therapy discharge summary",
            "doc_type": "therapy_note",
            "date": "2026-09-04",
            "text": _LMRI_PT_DISCHARGE,
        },
    ],
    "criteria": [
        {
            "criterion_id": "LMRI-1",
            "criterion_text": "The attending or treating physician's order for the MRI is properly signed and dated (Associated Information, Documentation Requirements).",
            "depth": 0,
            "logic": None,
        },
        {
            "criterion_id": "LMRI-2",
            "criterion_text": "The record documents the clinical findings and relevant prior treatment that support the MRI, with a history and a physical exam that evaluates muscle strength, limb circumference, reflexes, sensation, straight leg raise, and sitting knee extension (Documentation Requirements; Coverage Indications, Limitations, and/or Medical Necessity).",
            "depth": 0,
            "logic": None,
        },
        {
            "criterion_id": "LMRI-3",
            "criterion_text": "At least one indication pathway applies: a red flag on history and exam (for example clinically significant motor weakness, other nerve root compromise, a progressive neurologic deficit, a history of cancer, fever, or saddle anesthesia); or no red flag, symptoms for more than 1 month, and no response to at least 4 weeks of conservative care (Coverage Indications, Limitations, and/or Medical Necessity).",
            "depth": 0,
            "logic": "1 or more of the following",
        },
        {
            "criterion_id": "LMRI-4",
            "criterion_text": "The MRI result will be used for medical decision-making, and the record supports a contemplated diagnosis or treatment change; for uncomplicated degenerative disc disease or disc herniation, surgery or another aggressive treatment such as an injection is under consideration (Coverage Indications, Limitations, and/or Medical Necessity; Documentation Requirements).",
            "depth": 0,
            "logic": None,
        },
        {
            "criterion_id": "LMRI-5",
            "criterion_text": "The MRI does not duplicate other imaging such as a spinal CT; normally one lumbar MRI is enough, and a repeat MRI needs a documented reason for comparison (Coverage Indications, Limitations, and/or Medical Necessity; Utilization Guidelines).",
            "depth": 0,
            "logic": None,
        },
        {
            "criterion_id": "LMRI-6",
            "criterion_text": "The MRI unit has FDA pre-market approval and runs within its approved parameters, and no listed contraindication applies: contrast allergy when contrast is used, pregnancy at the primary doctor's discretion, or metallic clips on vascular aneurysms (Coverage Indications, Limitations, and/or Medical Necessity; CMS National Coverage Policy, NCD 220.2).",
            "depth": 0,
            "logic": None,
        },
    ],
    "criteria_facts": {
        "LMRI-1": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _LMRI_Q_ORDER,
                    "source_document": "Diagnostic imaging order — Lumbar spine MRI",
                    "document_date": "2026-09-10",
                }
            ],
            "rationale": "The treating physiatrist signed and dated the order for the lumbar MRI.",
            "confidence": 96,
        },
        "LMRI-2": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _LMRI_Q_HISTORY,
                    "source_document": "Office visit note — Physical Medicine and Rehabilitation",
                    "document_date": "2026-09-10",
                },
                {
                    "quote": _LMRI_Q_EXAM,
                    "source_document": "Office visit note — Physical Medicine and Rehabilitation",
                    "document_date": "2026-09-10",
                },
                {
                    "quote": _LMRI_Q_PT,
                    "source_document": "Physical therapy discharge summary",
                    "document_date": "2026-09-04",
                },
            ],
            "rationale": "The office note records the history and every listed exam element. The therapy discharge summary records the prior treatment and its outcome.",
            "confidence": 95,
        },
        "LMRI-3": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _LMRI_Q_RED_FLAG,
                    "source_document": "Office visit note — Physical Medicine and Rehabilitation",
                    "document_date": "2026-09-10",
                },
                {
                    "quote": _LMRI_Q_EXAM,
                    "source_document": "Office visit note — Physical Medicine and Rehabilitation",
                    "document_date": "2026-09-10",
                },
            ],
            "rationale": "The red-flag pathway applies: the exam shows clinically significant motor weakness (EHL 4/5) and signs of L5 nerve root compromise. Only one pathway is required. The record also shows 6 weeks of failed conservative care.",
            "confidence": 94,
        },
        "LMRI-4": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _LMRI_Q_DECISION,
                    "source_document": "Office visit note — Physical Medicine and Rehabilitation",
                    "document_date": "2026-09-10",
                }
            ],
            "rationale": "The plan names the injection or the surgical referral that depends on the MRI result, as the LCD requires for a suspected disc herniation.",
            "confidence": 95,
        },
        "LMRI-5": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _LMRI_Q_PRIOR_IMAGING,
                    "source_document": "Office visit note — Physical Medicine and Rehabilitation",
                    "document_date": "2026-09-10",
                }
            ],
            "rationale": "Only plain radiographs come before this study. There is no prior lumbar MRI or CT, so the MRI does not duplicate other imaging.",
            "confidence": 93,
        },
        "LMRI-6": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _LMRI_Q_UNIT,
                    "source_document": "Diagnostic imaging order — Lumbar spine MRI",
                    "document_date": "2026-09-10",
                },
                {
                    "quote": _LMRI_Q_SAFETY,
                    "source_document": "Diagnostic imaging order — Lumbar spine MRI",
                    "document_date": "2026-09-10",
                },
            ],
            "rationale": "The study runs without contrast on an FDA-cleared unit, and the safety screen rules out aneurysm clips and the other listed contraindications.",
            "confidence": 94,
        },
    },
}

# ---------------------------------------------------------------------------
# Scenario 4 — LCD L33405 attended in-lab polysomnography (First Coast JN,
# Florida; pend). The packet has no Epworth Sleepiness Scale score: the
# referral form's Epworth field is blank, and sleepiness is described in words.
# ---------------------------------------------------------------------------

_PSG_Q_VISIT = (
    "In-person, face-to-face evaluation for suspected obstructive sleep apnea before any "
    "sleep testing."
)
_PSG_Q_HISTORY = (
    "He has snored loudly every night for more than 5 years, his wife has seen pauses in "
    "his breathing, and he wakes up gasping 2 to 3 times a night."
)
_PSG_Q_SYMPTOMS = (
    "He has morning headaches on most days, and he dozes off while reading and while "
    "watching television in the evening."
)
_PSG_Q_EXAM = (
    "BMI 36.4 kg/m2 and neck circumference 17.5 in (44.5 cm); Mallampati class IV with a "
    "crowded oropharynx and retrognathia; lungs clear to auscultation; heart with a "
    "regular rate and rhythm; trace bilateral ankle edema."
)
_PSG_Q_ASSESSMENT = (
    "High clinical suspicion of obstructive sleep apnea based on loud habitual snoring, "
    "witnessed apneas, nocturnal gasping, morning headaches, daytime sleepiness, obesity, "
    "and a crowded upper airway."
)
_PSG_Q_IN_LAB = (
    "An attended in-laboratory polysomnogram is ordered instead of a home sleep apnea "
    "test, because home testing is not intended for patients with congestive heart "
    "failure."
)
_PSG_Q_CHF = (
    "Chronic heart failure with reduced ejection fraction, LVEF 35 percent on the "
    "echocardiogram of 07/30/2026, NYHA class II, on guideline-directed medical therapy."
)
_PSG_Q_SETTING = (
    "Attended, in-laboratory, overnight diagnostic polysomnography (Type I), with a "
    "technologist physically present all night to supervise the recording and to "
    "intervene as needed."
)
_PSG_Q_INDICATION = (
    "Suspected obstructive sleep apnea (G47.33); diagnostic study to confirm the "
    "diagnosis and grade its severity."
)
_PSG_Q_CHANNELS = (
    "Minimum recording: EEG, EOG, chin EMG, anterior tibialis EMG, ECG, airflow, thoracic "
    "and abdominal respiratory effort, and oxygen saturation, with body position recorded."
)
_PSG_Q_READER = (
    "Interpreting physician: Anika Patel, MD, board certified in sleep medicine by the "
    "American Board of Internal Medicine, a member board of the American Board of Medical "
    "Specialties; she reviews the raw data and interprets the study."
)
_PSG_Q_FACILITY = (
    "Seabreeze Regional Hospital Sleep Center is accredited by the American Academy of "
    "Sleep Medicine, with its accreditation on file, and night studies are attended by "
    "registered polysomnographic technologists (RPSGT)."
)
_PSG_Q_EPWORTH_BLANK = "Epworth Sleepiness Scale score: ______"

_PSG_EVAL_NOTE = f"""Sleep evaluation note — Pulmonary and Sleep Medicine
Patient: Harold Jenkins. Date of service: 09/09/2026. Location: Seabreeze Pulmonary &
Sleep Associates, Tampa, Florida.
Visit type: {_PSG_Q_VISIT}
Referral reason: Snoring and daytime sleepiness, referred by his cardiologist.
Sleep history: {_PSG_Q_HISTORY} {_PSG_Q_SYMPTOMS} He goes to bed at about 10:30 pm and
wakes at 6:00 am on most days. No shift work, no insomnia complaint, and no symptoms of
restless legs. One cup of coffee in the morning and no alcohol in the evening.
Medical history: Chronic heart failure with reduced ejection fraction (see the
cardiology follow-up note of 08/20/2026) and hypertension. No prior home sleep apnea
test or polysomnography.
Examination: {_PSG_Q_EXAM}
Assessment: {_PSG_Q_ASSESSMENT} ICD-10-CM G47.33, with I50.22 and I10.
Plan: {_PSG_Q_IN_LAB} The sleep study order and referral form is sent to the hospital
sleep center. Follow up after the study to review the results and treatment options."""

_PSG_CARDIOLOGY_NOTE = f"""Cardiology follow-up note
Patient: Harold Jenkins. Date of service: 08/20/2026. Cardiologist: Victor Almeida, MD,
Bayshore Heart Associates, Tampa, Florida.
Diagnoses: {_PSG_Q_CHF} Hypertension, controlled.
Interval history: Stable shortness of breath after 2 flights of stairs. No chest pain
and no syncope. His wife reports loud snoring and pauses in his breathing at night.
Examination: Blood pressure 132/78 mmHg, heart rate 68 and regular. Lungs clear. Trace
bilateral ankle edema.
Medications: sacubitril-valsartan, metoprolol succinate, spironolactone, and
dapagliflozin.
Plan: Continue current therapy. Refer to sleep medicine to evaluate suspected sleep
apnea, which can worsen heart failure. Recheck in 3 months."""

_PSG_ORDER_FORM = f"""Sleep study order and referral form — Seabreeze Regional Hospital Sleep Center
Patient: Harold Jenkins. Date of birth: 02/17/1962. Order date: 09/09/2026.
Ordering physician: Lorena Quintero, MD (Pulmonary and Sleep Medicine), NPI 1285730416,
Seabreeze Pulmonary & Sleep Associates, Tampa, Florida.
Study ordered: {_PSG_Q_SETTING} CPT 95810.
Reason for study: {_PSG_Q_INDICATION}
{_PSG_Q_CHANNELS}
{_PSG_Q_READER}
{_PSG_Q_FACILITY}
Prior sleep testing: None.
Pre-test questionnaires (attach completed forms):
{_PSG_Q_EPWORTH_BLANK}
Signed: Lorena Quintero, MD, 09/09/2026."""

_SCENARIO_PSG = {
    "id": "lcd-l33405-psg",
    "title": "In-lab sleep study — Medicare LCD L33405",
    "summary_subtitle": "64-year-old Florida member with suspected sleep apnea and heart failure, attended in-lab study ordered",
    "scenario_hint": "LCD scenario (First Coast, JN): the Medicaid plan applies LCD L33405 to Florida members. The packet has no Epworth Sleepiness Scale score, so the case pends for that one item.",
    "expected_path": "pend",
    "member": {
        "name": "Harold Jenkins",
        "member_id": "MBR-29475016",
        "date_of_birth": "1962-02-17",
        "plan_type": "medicaid",
        "plan_name": "Coral Coast Medicaid Health Plan",
    },
    "provider": {
        "name": "Dr. Lorena Quintero MD",
        "npi": "1285730416",
        "specialty": "Pulmonary and Sleep Medicine",
        "organization": "Seabreeze Pulmonary & Sleep Associates",
    },
    "service": {
        "description": "Attended overnight sleep study in a sleep laboratory (Type I polysomnography)",
        "cpt_codes": ["95810"],
        "icd10_codes": ["G47.33"],
        "setting": "outpatient",
        "urgency": "standard",
    },
    "policy": {
        "source_type": "lcd",
        "code": "LCD L33405",
        "title": "Polysomnography and Sleep Testing",
        "version": "25",
        "lcd_id": "L33405",
        "contractor": "First Coast Service Options, Inc.",
        "source_url": "https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33405&ver=25",
    },
    "clinical_documents": [
        {
            "id": "psg-eval-note",
            "title": "Sleep evaluation note — Pulmonary and Sleep Medicine",
            "doc_type": "office_visit_note",
            "date": "2026-09-09",
            "text": _PSG_EVAL_NOTE,
        },
        {
            "id": "psg-cardiology-note",
            "title": "Cardiology follow-up note",
            "doc_type": "office_visit_note",
            "date": "2026-08-20",
            "text": _PSG_CARDIOLOGY_NOTE,
        },
        {
            "id": "psg-order-form",
            "title": "Sleep study order and referral form — Seabreeze Regional Hospital Sleep Center",
            "doc_type": "order",
            "date": "2026-09-09",
            "text": _PSG_ORDER_FORM,
        },
    ],
    "criteria": [
        {
            "criterion_id": "PSG-1",
            "criterion_text": "Clinical signs and symptoms indicate obstructive sleep apnea (OSA), and the study is used to aid the OSA diagnosis (History/Background, Type I PSG; Covered Indications, 1. Sleep Apnea).",
            "depth": 0,
            "logic": None,
        },
        {
            "criterion_id": "PSG-2",
            "criterion_text": "Before testing, the treating physician completes a face-to-face clinical evaluation for OSA that records the sleep history and symptoms, such as snoring, daytime sleepiness, observed apneas, choking or gasping during sleep, and morning headaches (Covered Indications, 1. Sleep Apnea, item A).",
            "depth": 0,
            "logic": None,
        },
        {
            "criterion_id": "PSG-3",
            "criterion_text": "The pre-test face-to-face evaluation includes an Epworth Sleepiness Scale (Covered Indications, 1. Sleep Apnea, item A; Limitations).",
            "depth": 0,
            "logic": None,
        },
        {
            "criterion_id": "PSG-4",
            "criterion_text": "The pre-test evaluation includes a physical exam that records body mass index, neck circumference, and a focused cardiopulmonary and upper airway evaluation (Covered Indications, 1. Sleep Apnea, item A).",
            "depth": 0,
            "logic": None,
        },
        {
            "criterion_id": "PSG-5",
            "criterion_text": "The study is a Type I PSG attended in a sleep laboratory: a technologist is physically present to supervise the recording and can intervene, trained staff are in constant attendance, and the minimum recording channels are captured (History/Background, Type I PSG).",
            "depth": 0,
            "logic": None,
        },
        {
            "criterion_id": "PSG-6",
            "criterion_text": "A qualified physician reviews the raw data and interprets the study: for example a physician board certified in sleep medicine by an ABMS member board or the AOA, a sleep medicine diplomate, an ABFM diplomate with a sleep medicine CAQ, or an active staff physician of an AASM-, Joint Commission-, or ACHC-accredited sleep facility (Provider Qualifications, Physicians).",
            "depth": 0,
            "logic": "1 or more of the following",
        },
        {
            "criterion_id": "PSG-7",
            "criterion_text": "The sleep facility has accreditation on file from the AASM, ACHC, or the Joint Commission, and the attending technologist holds an appropriate credential such as RPSGT (Provider Qualifications; Facility Accreditation).",
            "depth": 0,
            "logic": None,
        },
    ],
    "criteria_facts": {
        "PSG-1": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _PSG_Q_ASSESSMENT,
                    "source_document": "Sleep evaluation note — Pulmonary and Sleep Medicine",
                    "document_date": "2026-09-09",
                },
                {
                    "quote": _PSG_Q_INDICATION,
                    "source_document": "Sleep study order and referral form — Seabreeze Regional Hospital Sleep Center",
                    "document_date": "2026-09-09",
                },
            ],
            "rationale": "The evaluation lists the signs and symptoms of OSA, and the order states that the study is to diagnose suspected OSA.",
            "confidence": 95,
        },
        "PSG-2": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _PSG_Q_VISIT,
                    "source_document": "Sleep evaluation note — Pulmonary and Sleep Medicine",
                    "document_date": "2026-09-09",
                },
                {
                    "quote": _PSG_Q_HISTORY,
                    "source_document": "Sleep evaluation note — Pulmonary and Sleep Medicine",
                    "document_date": "2026-09-09",
                },
                {
                    "quote": _PSG_Q_SYMPTOMS,
                    "source_document": "Sleep evaluation note — Pulmonary and Sleep Medicine",
                    "document_date": "2026-09-09",
                },
            ],
            "rationale": "A face-to-face visit before testing records snoring, witnessed apneas, gasping, morning headaches, and daytime sleepiness.",
            "confidence": 95,
        },
        "PSG-3": {
            "status": "INSUFFICIENT",
            "evidence": [
                {
                    "quote": _PSG_Q_EPWORTH_BLANK,
                    "source_document": "Sleep study order and referral form — Seabreeze Regional Hospital Sleep Center",
                    "document_date": "2026-09-09",
                }
            ],
            "rationale": "The evaluation describes daytime sleepiness in words only. No Epworth Sleepiness Scale score appears in the packet, and the Epworth field on the referral form is blank. Request the completed Epworth Sleepiness Scale from the pre-test face-to-face evaluation.",
            "confidence": 92,
        },
        "PSG-4": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _PSG_Q_EXAM,
                    "source_document": "Sleep evaluation note — Pulmonary and Sleep Medicine",
                    "document_date": "2026-09-09",
                }
            ],
            "rationale": "The exam records BMI, neck circumference, heart and lung findings, and an upper airway exam.",
            "confidence": 96,
        },
        "PSG-5": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _PSG_Q_SETTING,
                    "source_document": "Sleep study order and referral form — Seabreeze Regional Hospital Sleep Center",
                    "document_date": "2026-09-09",
                },
                {
                    "quote": _PSG_Q_CHANNELS,
                    "source_document": "Sleep study order and referral form — Seabreeze Regional Hospital Sleep Center",
                    "document_date": "2026-09-09",
                },
                {
                    "quote": _PSG_Q_IN_LAB,
                    "source_document": "Sleep evaluation note — Pulmonary and Sleep Medicine",
                    "document_date": "2026-09-09",
                },
                {
                    "quote": _PSG_Q_CHF,
                    "source_document": "Cardiology follow-up note",
                    "document_date": "2026-08-20",
                },
            ],
            "rationale": "The order specifies an attended Type I study in a sleep laboratory with the minimum recording channels. The record also explains the in-lab choice: the member has heart failure, and the LCD says home testing is not intended for patients with congestive heart failure.",
            "confidence": 94,
        },
        "PSG-6": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _PSG_Q_READER,
                    "source_document": "Sleep study order and referral form — Seabreeze Regional Hospital Sleep Center",
                    "document_date": "2026-09-09",
                }
            ],
            "rationale": "The interpreting physician is board certified in sleep medicine by an ABMS member board. Only one qualification is required.",
            "confidence": 94,
        },
        "PSG-7": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _PSG_Q_FACILITY,
                    "source_document": "Sleep study order and referral form — Seabreeze Regional Hospital Sleep Center",
                    "document_date": "2026-09-09",
                }
            ],
            "rationale": "The sleep center has AASM accreditation on file, and RPSGT technologists attend the studies.",
            "confidence": 94,
        },
    },
}

# ---------------------------------------------------------------------------
# Scenario 5 — LCD L39911 total knee arthroplasty (WPS J8, Michigan; approval).
# TKA-1 is met through its advanced joint disease option, which needs all of
# TKA-2, TKA-3, and TKA-4; those three sit at depth 1 under TKA-1.
# ---------------------------------------------------------------------------

_TKA_Q_FUNCTION = (
    "Pain is 8/10 with weight bearing and worse with activity; she can walk only 1 block, "
    "needs the rail to climb stairs, needs help getting in and out of the bathtub, and "
    "wakes with knee pain 2 to 3 nights a week (KOOS JR score 42)."
)
_TKA_Q_CONSERVATIVE = (
    "More than 8 months of non-surgical care has failed: meloxicam 15 mg daily with "
    "acetaminophen, 12 supervised physical therapy visits with the plan of care completed "
    "but daily activities still limited, a daily home exercise program, a cane since the "
    "spring, a 12 lb weight loss (BMI 31.2 to 29.4), and 2 corticosteroid injections that "
    "each gave about 3 weeks of relief, the last one 4 months ago."
)
_TKA_Q_DIAGNOSIS = (
    "Advanced primary osteoarthritis of the right knee (M17.11), with bone-on-bone medial "
    "joint space narrowing on standing radiographs, pain and functional disability that "
    "limit her daily activities, and failed non-surgical care."
)
_TKA_Q_PLAN = (
    "Right total knee arthroplasty that replaces all three compartments (not a "
    "unicompartmental replacement), using an FDA-cleared class II cemented total knee "
    "implant system (21 CFR 888.3560)."
)
_TKA_Q_FINDINGS = (
    "Severe medial joint space narrowing with bone-on-bone contact, large periarticular "
    "osteophytes, subchondral sclerosis, and subchondral cysts in the medial tibial "
    "plateau."
)
_TKA_Q_IMPRESSION = (
    "Severe osteoarthritis of the right knee, worst in the medial compartment, "
    "Kellgren-Lawrence grade 4, with 8 degrees of varus alignment."
)
_TKA_Q_NO_CONTRA = (
    "Skin over the right knee is intact with no open wound or sign of infection; there is "
    "no fever, no joint infection or bacteremia, no peripheral neuropathy or Charcot joint "
    "(normal monofilament sensation in both feet), and no progressive neurologic disease."
)
_TKA_Q_CLEARANCE = (
    "Medically optimized for surgery; the expected benefit of knee replacement outweighs "
    "her surgical risk, and she is cleared to proceed."
)

_TKA_CONSULT_NOTE = f"""Orthopedic surgery consultation note — Adult Reconstruction
Patient: Patricia Nowak. Date of service: 09/15/2026. Location: Northpoint Orthopedics &
Joint Center, Grand Rapids, Michigan.
Chief complaint: Right knee pain.
History of present illness: Ms. Nowak is a 71-year-old retired teacher with right knee
pain for 3 years that has become worse over the last 12 months. {_TKA_Q_FUNCTION}
Non-surgical treatment: {_TKA_Q_CONSERVATIVE}
Examination: Height 174 cm, weight 89 kg, BMI 29.4. Antalgic gait with a cane. Right
knee: small effusion, medial joint line tenderness, 8 degrees of varus that partly
corrects, range of motion 5 to 105 degrees, crepitus, and stable ligaments. Skin intact.
Distal pulses and sensation normal.
Imaging: Standing right knee radiographs of 08/04/2026 reviewed (see the radiology
report).
Assessment: {_TKA_Q_DIAGNOSIS}
Plan: {_TKA_Q_PLAN} Pre-operative medical clearance from her primary care physician.
Risks, benefits, and alternatives were discussed, and she wishes to proceed."""

_TKA_RADIOLOGY_REPORT = f"""Radiology report — Right knee radiographs
Patient: Patricia Nowak. Exam date: 08/04/2026. Interpreting radiologist: Jonathan
Whitaker, MD, Lakeshore Radiology, Grand Rapids, Michigan.
Exam: Right knee, standing AP, lateral, and sunrise views.
Indication: Chronic right knee pain.
Findings: {_TKA_Q_FINDINGS} Mild lateral compartment narrowing. Patellofemoral narrowing
with osteophytes. Small joint effusion. No fracture, no loose body, and no bone
destruction.
Impression: {_TKA_Q_IMPRESSION}"""

_TKA_PREOP_NOTE = f"""Pre-operative medical clearance note — Family Medicine
Patient: Patricia Nowak. Date of service: 09/18/2026. Physician: Karen Holloway, DO,
Grand River Family Medicine, Grand Rapids, Michigan.
Planned procedure: Right total knee arthroplasty by the Northpoint Orthopedics & Joint
Center team.
Medical history: Hypertension, controlled on lisinopril. Type 2 diabetes, controlled on
metformin, with a hemoglobin A1c of 6.8 percent on 09/02/2026.
Examination: Temperature 36.7 C, blood pressure 128/76 mmHg, heart rate 72 and regular.
Lungs clear. {_TKA_Q_NO_CONTRA}
Tests: ECG shows normal sinus rhythm. Complete blood count and basic metabolic panel are
within normal limits.
Assessment: {_TKA_Q_CLEARANCE}"""

_SCENARIO_TKA = {
    "id": "lcd-l39911-tka",
    "title": "Total knee replacement — Medicare LCD L39911",
    "summary_subtitle": "71-year-old Michigan member with end-stage right knee osteoarthritis after 8 months of failed non-surgical care",
    "scenario_hint": "LCD scenario (WPS, J5/J8): the Medicare Advantage plan applies LCD L39911 to Michigan members. TKA-1 is met through advanced joint disease, so TKA-2 to TKA-4 sit under it.",
    "expected_path": "approve",
    "member": {
        "name": "Patricia Nowak",
        "member_id": "MBR-75308142",
        "date_of_birth": "1955-05-03",
        "plan_type": "medicare_advantage",
        "plan_name": "Maplewood Medicare Advantage PPO",
    },
    "provider": {
        "name": "Dr. Thomas Brandt MD",
        "npi": "1639058274",
        "specialty": "Orthopedic Surgery",
        "organization": "Northpoint Orthopedics & Joint Center",
    },
    "service": {
        "description": "Right total knee replacement",
        "cpt_codes": ["27447"],
        "icd10_codes": ["M17.11"],
        "setting": "inpatient",
        "urgency": "standard",
    },
    "policy": {
        "source_type": "lcd",
        "code": "LCD L39911",
        "title": "Total Joint Arthroplasty",
        "version": "10",
        "lcd_id": "L39911",
        "contractor": "WPS Insurance Corporation",
        "source_url": "https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=39911&ver=10",
    },
    "clinical_documents": [
        {
            "id": "tka-consult-note",
            "title": "Orthopedic surgery consultation note — Adult Reconstruction",
            "doc_type": "consult_note",
            "date": "2026-09-15",
            "text": _TKA_CONSULT_NOTE,
        },
        {
            "id": "tka-radiology-report",
            "title": "Radiology report — Right knee radiographs",
            "doc_type": "imaging_report",
            "date": "2026-08-04",
            "text": _TKA_RADIOLOGY_REPORT,
        },
        {
            "id": "tka-preop-note",
            "title": "Pre-operative medical clearance note — Family Medicine",
            "doc_type": "office_visit_note",
            "date": "2026-09-18",
            "text": _TKA_PREOP_NOTE,
        },
    ],
    "criteria": [
        {
            "criterion_id": "TKA-1",
            "criterion_text": "At least one covered TKA indication applies: failed prior osteotomy; distal femur or proximal tibia fracture; malignancy of the knee region; avascular necrosis of the knee; failed prior unicompartmental replacement; or advanced joint disease shown by all of TKA-2, TKA-3, and TKA-4 (Covered Indications, Total knee arthroplasty).",
            "depth": 0,
            "logic": "1 or more of the following",
        },
        {
            "criterion_id": "TKA-2",
            "criterion_text": "Advanced joint disease path under TKA-1: imaging of the operative knee shows at least one of subchondral cysts, subchondral sclerosis, periarticular osteophytes, joint subluxation, joint space narrowing, or avascular necrosis (Covered Indications; A59811 Documentation Requirements).",
            "depth": 1,
            "logic": "1 or more of the following",
        },
        {
            "criterion_id": "TKA-3",
            "criterion_text": "Advanced joint disease path under TKA-1: pain or functional disability from the joint disease interferes with activities of daily living, or increases with activity or weight bearing (Covered Indications; A59811 Documentation Requirements).",
            "depth": 1,
            "logic": None,
        },
        {
            "criterion_id": "TKA-4",
            "criterion_text": "Advanced joint disease path under TKA-1: the pre-procedure record shows unsuccessful conservative therapy, usually for 3 months or more, with 1 or more of anti-inflammatory drugs, analgesics, exercise, supervised physical therapy, activity restriction, an assistive device, weight reduction, or knee injections (Covered Indications; A59811 Documentation Requirements).",
            "depth": 1,
            "logic": "1 or more of the following",
        },
        {
            "criterion_id": "TKA-5",
            "criterion_text": "No contraindication is present: active knee joint infection or systemic bacteremia; active skin infection or open wound at the surgical site; neuropathic arthritis; or rapidly progressing neurological disease (Limitations).",
            "depth": 0,
            "logic": None,
        },
        {
            "criterion_id": "TKA-6",
            "criterion_text": "The planned procedure is a total (not unicompartmental) knee arthroplasty with an FDA class II or class III implant that meets 21 CFR Part 888 (Limitations).",
            "depth": 0,
            "logic": None,
        },
    ],
    "criteria_facts": {
        "TKA-1": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _TKA_Q_DIAGNOSIS,
                    "source_document": "Orthopedic surgery consultation note — Adult Reconstruction",
                    "document_date": "2026-09-15",
                }
            ],
            "rationale": "The advanced joint disease indication applies, and all three of its parts (TKA-2, TKA-3, and TKA-4) are met. Only one indication is required.",
            "confidence": 95,
        },
        "TKA-2": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _TKA_Q_FINDINGS,
                    "source_document": "Radiology report — Right knee radiographs",
                    "document_date": "2026-08-04",
                },
                {
                    "quote": _TKA_Q_IMPRESSION,
                    "source_document": "Radiology report — Right knee radiographs",
                    "document_date": "2026-08-04",
                },
            ],
            "rationale": "Standing radiographs show four listed findings: joint space narrowing, osteophytes, subchondral sclerosis, and subchondral cysts. One finding is enough.",
            "confidence": 97,
        },
        "TKA-3": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _TKA_Q_FUNCTION,
                    "source_document": "Orthopedic surgery consultation note — Adult Reconstruction",
                    "document_date": "2026-09-15",
                }
            ],
            "rationale": "Pain increases with weight bearing and activity, and the note names specific limits on walking, stairs, and bathing.",
            "confidence": 95,
        },
        "TKA-4": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _TKA_Q_CONSERVATIVE,
                    "source_document": "Orthopedic surgery consultation note — Adult Reconstruction",
                    "document_date": "2026-09-15",
                }
            ],
            "rationale": "More than 8 months of care, longer than the usual 3 months, used several listed treatments without lasting benefit. Supervised therapy was completed, and daily activities are still limited.",
            "confidence": 94,
        },
        "TKA-5": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _TKA_Q_NO_CONTRA,
                    "source_document": "Pre-operative medical clearance note — Family Medicine",
                    "document_date": "2026-09-18",
                }
            ],
            "rationale": "The clearance exam rules out each listed contraindication: infection, an open wound at the site, neuropathic arthritis, and progressive neurologic disease.",
            "confidence": 93,
        },
        "TKA-6": {
            "status": "MET",
            "evidence": [
                {
                    "quote": _TKA_Q_PLAN,
                    "source_document": "Orthopedic surgery consultation note — Adult Reconstruction",
                    "document_date": "2026-09-15",
                }
            ],
            "rationale": "The plan names a total, not unicompartmental, knee replacement with an FDA-cleared class II implant under 21 CFR Part 888.",
            "confidence": 95,
        },
    },
}


# ---------------------------------------------------------------------------
# Scenario registry. Append new NCD or LCD scenarios here, in display order.
# ---------------------------------------------------------------------------

SCENARIOS: list[dict] = [
    _SCENARIO_DXA,
    _SCENARIO_TAVR,
    _SCENARIO_LUMBAR_MRI,
    _SCENARIO_PSG,
    _SCENARIO_TKA,
]


def get_scenarios() -> list[dict]:
    return SCENARIOS


def get_scenario(scenario_id: str) -> dict | None:
    for scenario in SCENARIOS:
        if scenario["id"] == scenario_id or scenario.get("scenario_id") == scenario_id:
            return scenario
    return None
