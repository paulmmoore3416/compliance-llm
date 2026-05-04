"Synthetic dataset generator for the Compliance-Llama \"Regulatory Gold Set\".\n\nProduces JSONL files matching the schema expected by training/src/data.py:\n\n    {\"device_context\": \"...\", \"instruction\": \"...\", \"target\": \"...\"}\n\nEach row pairs a *Device Context* (Class, IFU, Risk Profile, Intended User)\nwith a Drafted SOP that explicitly cites ISO 13485 / 21 CFR 820 clauses.\n\nThree modes:\n  - \"deterministic\"   — combinatorial expansion of curated templates. Fast,\n                         reproducible, no API calls. This is the default and\n                         what we ship in `train.jsonl` / `eval.jsonl`.\n  - \"augment\"          — adds light surface variation (paraphrase via\n                         template alternation) on top of the deterministic\n                         set.\n  - \"llm\"              — optional: calls a teacher model (any OpenAI-compatible\n                         endpoint, including a self-hosted vLLM running plain\n                         Llama 3.1) to expand the gold set. Off by default.\n\nUsage:\n    python -m data.synthetic.build_dataset \\n        --output-dir data/synthetic --train-eval-split 0.9 --seed 42\n"

from __future__ import annotations

import argparse
import itertools
import json
import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

logger = logging.getLogger("compliance-llama.dataset")


# ---------------------------------------------------------------------------
# Vocabulary — the building blocks of synthetic device contexts
# ---------------------------------------------------------------------------

DEVICE_CLASSES = ["Class I", "Class II", "Class III", "SaMD Class II", "SaMD Class III"]

DEVICE_TYPES = [
    ("Continuous Glucose Monitor",           "Class II",  "moderate"),
    ("Implantable Cardiac Pacemaker",        "Class III", "high"),
    ("Surgical Stapler",                     "Class II",  "moderate"),
    ("Tongue Depressor",                     "Class I",   "low"),
    ("Insulin Infusion Pump",                "Class II",  "high"),
    ("Coronary Drug-Eluting Stent",          "Class III", "high"),
    ("AI-Enabled Radiology Triage Software", "SaMD Class II",  "moderate"),
    ("Portable Defibrillator (AED)",         "Class III", "high"),
    ("Sterile Surgical Gloves",              "Class I",   "low"),
    ("Powered Wheelchair",                   "Class II",  "moderate"),
    ("MRI-Compatible Patient Monitor",       "Class II",  "moderate"),
    ("Bone-Anchored Hearing Implant",        "Class III", "high"),
    ("Single-Use Endoscope",                 "Class II",  "moderate"),
    ("Digital Stethoscope",                  "Class II",  "low"),
    ("Robotic Surgical Manipulator",         "Class II",  "high"),
    ("Cloud-Based Clinical Decision Support", "SaMD Class III", "high"),
    ("Genomic Analysis Pipeline",            "SaMD Class II", "moderate"),
    ("Telehealth Patient Monitoring App",    "SaMD Class II", "moderate"),
]

INTENDED_USERS = [
    "trained clinicians in a hospital setting",
    "home-care patients with manufacturer training",
    "EMS first responders",
    "anesthesiologists in operating theatres",
    "diabetes self-management patients aged 14+",
    "interventional cardiologists in cath labs",
    "radiologists supervising AI-assisted reads",
    "data scientists and bioinformaticians",
    "remote care nurses and triage staff",
]

ENVIRONMENTS = [
    "operating room", "patient home", "ambulance", "ICU bedside",
    "outpatient clinic", "MRI suite", "cardiac cath lab", "primary care office",
    "cloud infrastructure (AWS/Azure/GCP)", "hospital IT network",
]

# ---------------------------------------------------------------------------
# Artifact templates — each yields one (instruction, target) pair given a
# device context. Targets cite specific ISO 13485 and 21 CFR 820 clauses.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DeviceContext:
    name: str
    device_class: str
    risk_profile: str        # low / moderate / high
    intended_user: str
    environment: str
    indication: str          # short Indication for Use string

    def render(self) -> str:
        return (
            f"Device Name: {self.name}\n"
            f"Device Class: {self.device_class}\n"
            f"Risk Profile: {self.risk_profile.title()}\n"
            f"Intended User: {self.intended_user}\n"
            f"Use Environment: {self.environment}\n"
            f"Indication for Use: {self.indication}"
        )


def _indication_for(name: str, environment: str) -> str:
    return (
        f"The {name} is intended for use in the {environment} to support "
        f"diagnosis, monitoring, or treatment in accordance with its labeled "
        f"clinical workflow."
    )


def iter_contexts(rng: random.Random, limit: int) -> Iterable[DeviceContext]:
    """Yield up to `limit` device contexts via Cartesian sampling."""
    seen = set()
    pool = list(itertools.product(DEVICE_TYPES, INTENDED_USERS, ENVIRONMENTS))
    rng.shuffle(pool)
    for (name, klass, risk), user, env in pool:
        key = (name, user, env)
        if key in seen:
            continue
        seen.add(key)
        yield DeviceContext(
            name=name,
            device_class=klass,
            risk_profile=risk,
            intended_user=user,
            environment=env,
            indication=_indication_for(name, env),
        )
        if len(seen) >= limit:
            return


# ---------------------------------------------------------------------------
# Artifact: Design & Development Planning SOP
# ---------------------------------------------------------------------------

def sop_design_controls(ctx: DeviceContext) -> tuple[str, str]:
    instruction = (
        f"Draft a 'Design and Development Planning' SOP for the device described below, "
        f"in compliance with ISO 13485:2016 §7.3 and 21 CFR 820.30. Include explicit clause citations."
    )
    target = f"""# SOP-DC-001: Design and Development Planning — {ctx.name}

## 1. Purpose
This Standard Operating Procedure establishes the design and development planning
requirements for the {ctx.name} ({ctx.device_class}) to ensure compliance with
ISO 13485:2016 §7.3.2 and 21 CFR 820.30(b).

## 2. Scope
This SOP applies to all design and development activities for the {ctx.name},
from initial concept through design transfer. It covers the planning,
documentation, review, verification, validation, and transfer activities
required to produce a safe and effective device for {ctx.intended_user}
operating in the {ctx.environment}.

## 3. Responsibilities
- **Design Project Manager** — maintains the Design and Development Plan;
  ensures clause-by-clause traceability per ISO 13485 §7.3.2(a)–(g).
- **Quality Assurance** — verifies the plan meets 21 CFR 820.30(b) and the
  Quality System Record per 21 CFR 820.186.
- **Regulatory Affairs** — confirms intended use and risk classification
  ({ctx.device_class}, {ctx.risk_profile} risk).
- **Cross-functional reviewers** — participate in formal Design Reviews per
  ISO 13485 §7.3.5.

## 4. Definitions
- **Design Input**: physical and performance requirements per 21 CFR 820.30(c).
- **Design Output**: documents and specifications per 21 CFR 820.30(d).
- **Design Transfer**: the activity of correctly translating the design into
  production specifications per 21 CFR 820.30(h) and ISO 13485 §7.3.8.

## 5. Procedure

### 5.1 Plan Initiation (ISO 13485 §7.3.2; 21 CFR 820.30(b))
The Design Project Manager shall draft a Design and Development Plan that
includes:
  (a) the stages of design and development;
  (b) review, verification, and validation activities appropriate to each stage;
  (c) responsibilities and authorities;
  (d) methods to ensure traceability between inputs and outputs;
  (e) resources required, including competence per ISO 13485 §6.2.

### 5.2 Risk Management Integration (ISO 14971; ISO 13485 §7.1)
Given the {ctx.risk_profile} risk profile, risk management activities per
ISO 14971 shall be planned alongside design activities. A Risk Management File
shall be maintained and referenced in every Design Review.

### 5.3 Design Review Cadence (ISO 13485 §7.3.5; 21 CFR 820.30(e))
Formal Design Reviews shall be held at minimum at: concept, prototype,
verification, validation, and transfer. Each review shall include an
independent reviewer with no direct responsibility for the stage being
reviewed.

### 5.4 Plan Updates
The plan shall be updated as design and development progresses, and approved
changes shall be documented per ISO 13485 §7.3.9 and 21 CFR 820.30(i).

## 6. Records
The following records shall be retained in the Design History File (DHF) per
21 CFR 820.30(j) and the corresponding Design and Development File per
ISO 13485 §7.3.10:
- Approved Design and Development Plan (this document, signed)
- Design Review minutes and action items
- Verification and validation protocols and reports
- Design transfer records

## 7. References
- ISO 13485:2016, §7.3.2, §7.3.5, §7.3.8, §7.3.9, §7.3.10, §6.2, §7.1
- 21 CFR Part 820.30(b), (c), (d), (e), (h), (i), (j); 820.186
- ISO 14971:2019 — Application of risk management to medical devices

## 8. Revision History
| Rev | Date       | Author | Description       |
|-----|------------|--------|-------------------|
| 01  | YYYY-MM-DD | TBD    | Initial release   |
"""
    return instruction, target


# ---------------------------------------------------------------------------
# Artifact: CAPA SOP
# ---------------------------------------------------------------------------

def sop_capa(ctx: DeviceContext) -> tuple[str, str]:
    instruction = (
        f"Draft a Corrective and Preventive Action (CAPA) SOP scoped to the device "
        f"below, citing ISO 13485 §8.5.2/§8.5.3 and 21 CFR 820.100."
    )
    target = f"""# SOP-CAPA-001: Corrective and Preventive Action — {ctx.name}

## 1. Purpose
To define the procedure for identifying, investigating, and resolving
nonconformities and potential nonconformities related to the {ctx.name},
in accordance with ISO 13485:2016 §8.5.2 (Corrective Action), §8.5.3
(Preventive Action), and 21 CFR 820.100.

## 2. Scope
Applies to all CAPA activities arising from complaints, nonconforming product,
audit findings, service reports, and post-market surveillance signals related
to the {ctx.name} ({ctx.device_class}, {ctx.risk_profile} risk) used by
{ctx.intended_user}.

## 3. Responsibilities
- **CAPA Coordinator** — maintains the CAPA register; ensures each record
  meets 21 CFR 820.100(a)(1)–(7).
- **Investigator(s)** — perform root cause analysis per ISO 13485 §8.5.2(b).
- **Quality Manager** — approves effectiveness verification per 21 CFR 820.100(a)(4).
- **Management Representative** — reports CAPA status to top management per
  ISO 13485 §5.6.2(f).

## 4. Procedure

### 4.1 Trigger and Intake (21 CFR 820.100(a)(1))
A CAPA shall be opened upon any of:
  - Complaint trend exceeding the threshold defined in the Post-Market
    Surveillance Plan;
  - Nonconforming product per ISO 13485 §8.3;
  - Internal/external audit finding;
  - Service or returned-goods analysis indicating a recurring fault.

### 4.2 Investigation (ISO 13485 §8.5.2(b); 21 CFR 820.100(a)(2))
Root cause analysis shall use a structured technique (e.g., 5-Why, Ishikawa,
Fault Tree Analysis). For {ctx.risk_profile}-risk devices, investigations
shall include a re-evaluation of the Risk Management File per ISO 14971 §10.

### 4.3 Action Determination (ISO 13485 §8.5.2(d); 21 CFR 820.100(a)(3))
Selected actions shall be commensurate with the magnitude of the problem and
the risk encountered. Actions may include design changes (managed per
21 CFR 820.30(i)), process changes, training, supplier controls, or labelling.

### 4.4 Implementation and Records (21 CFR 820.100(a)(5)–(7))
All CAPA activities and their results shall be documented. Records shall be
retained as part of the Quality System Record per 21 CFR 820.186.

### 4.5 Effectiveness Verification (ISO 13485 §8.5.2(e); 21 CFR 820.100(a)(4))
Verification shall be performed after a defined monitoring period (typically
≥ 90 days) using objective evidence. A CAPA may not be closed until
effectiveness is confirmed.

### 4.6 Management Review Input (ISO 13485 §5.6.2)
CAPA status, trends, and overdue items shall be presented at every
Management Review.

## 6. Records
- CAPA register (with unique CAPA IDs and statuses)
- Investigation reports
- Effectiveness verification evidence
- Linkage to complaints (ISO 13485 §8.2.2) and post-market surveillance

## 7. References
- ISO 13485:2016 §8.5.2, §8.5.3, §8.3, §8.2.2, §5.6.2
- 21 CFR 820.100, 820.198, 820.30(i), 820.186
- ISO 14971:2019 §10

## 8. Revision History
| Rev | Date       | Author | Description     |
|-----|------------|--------|-----------------|
| 01  | YYYY-MM-DD | TBD    | Initial release |
"""
    return instruction, target


# ---------------------------------------------------------------------------
# Artifact: Risk Management SOP
# ---------------------------------------------------------------------------

def sop_risk_management(ctx: DeviceContext) -> tuple[str, str]:
    instruction = (
        f"Draft a Risk Management SOP for the device below, aligning ISO 14971 "
        f"with ISO 13485 §7.1 and 21 CFR 820.30(g)."
    )
    target = f"""# SOP-RM-001: Risk Management — {ctx.name}

## 1. Purpose
To establish the risk management process for the {ctx.name} per
ISO 14971:2019, integrated with the Quality Management System under
ISO 13485:2016 §7.1 and design controls per 21 CFR 820.30(g).

## 2. Scope
Covers the entire product lifecycle of the {ctx.name} ({ctx.device_class},
{ctx.risk_profile} risk) — from concept through post-market — for users
described as {ctx.intended_user} operating in the {ctx.environment}.

## 3. Responsibilities
- **Risk Management Lead** — maintains the Risk Management File per
  ISO 14971 §4.5.
- **Cross-functional Risk Team** — performs hazard identification, risk
  estimation, and risk evaluation per ISO 14971 §5–§7.
- **Top Management** — provides resources and reviews residual risk
  acceptability per ISO 14971 §4.2.

## 4. Procedure

### 4.1 Risk Management Plan (ISO 14971 §4.4)
Before design activities begin, a device-specific Risk Management Plan shall
be approved. It shall define the scope, responsibilities, the risk
acceptability criteria, verification activities, and the post-market
information collection plan.

### 4.2 Hazard Identification (ISO 14971 §5.4)
Identify reasonably foreseeable hazards across all lifecycle phases including
normal use and reasonably foreseeable misuse, particularly relevant given the
intended use environment ({ctx.environment}) and operator profile.

### 4.3 Risk Estimation and Evaluation (ISO 14971 §5.5–§6)
For each hazardous situation, estimate severity and probability of harm and
evaluate against the risk acceptability criteria.

### 4.4 Risk Control (ISO 14971 §7)
Apply control measures in priority order:
  (a) inherently safe design;
  (b) protective measures in the device itself or manufacturing;
  (c) information for safety (labelling, IFU).
Verify implementation and effectiveness of each control.

### 4.5 Residual Risk Evaluation (ISO 14971 §7.4–§8)
Evaluate residual risk individually and overall against the criteria in the
Risk Management Plan. Document the benefit-risk analysis where applicable.

### 4.6 Production and Post-Production Information (ISO 14971 §10)
Establish and maintain a system to collect and review information from
production and post-production phases. New information that affects the
risk assessment shall trigger a CAPA per SOP-CAPA-001.

## 5. Records
- Risk Management Plan
- Risk Management File (FMEA / hazard analysis tables, control verifications)
- Risk Management Report at design transfer (ISO 14971 §9)
- Periodic post-market risk reviews

## 6. References
- ISO 14971:2019 — full standard
- ISO/TR 24971:2020 — guidance on application of ISO 14971
- ISO 13485:2016 §7.1
- 21 CFR 820.30(g)

## 7. Revision History
| Rev | Date       | Author | Description     |
|-----|------------|--------|-----------------|
| 01  | YYYY-MM-DD | TBD    | Initial release |
"""
    return instruction, target


# ---------------------------------------------------------------------------
# Artifact: Advanced Regulatory Scenarios & Cybersecurity (NEW)
# ---------------------------------------------------------------------------

def advanced_regulatory_scenario(ctx: DeviceContext) -> tuple[str, str]:
    instruction = (
        f"Provide an advanced regulatory compliance scenario and impact analysis for the {ctx.name} "
        f"({ctx.device_class}, {ctx.risk_profile} risk, for {ctx.intended_user} in {ctx.environment}). "
        f"Address the convergence of ISO 13485, EU MDR (or IVDR if applicable), FDA Cybersecurity Guidance (2023), "
        f"ISO/IEC 27001, and IEC 62304/81001-5-1. Detail current regulatory issues, recent changes, and required fixes."
    )
    
    target = f"""# Advanced Regulatory Scenario & Impact Analysis: {ctx.name}

## 1. Scenario Context & Device Profile
- **Device**: {ctx.name}
- **Classification**: {ctx.device_class}
- **Risk Profile**: {ctx.risk_profile.title()} Risk
- **Intended User**: {ctx.intended_user}
- **Use Environment**: {ctx.environment}

## 2. Current Regulatory Issues & Convergence Challenges
The rapid evolution of Software as a Medical Device (SaMD) and connected medical hardware has created a complex regulatory web. For the {ctx.name}, the following specific convergence issues apply:
- **Cybersecurity vs. Agility**: FDA's 2023 Cybersecurity in Medical Devices guidance requires continuous monitoring, Software Bill of Materials (SBOMs), and coordinated vulnerability disclosure. This conflicts with traditional, slow-moving ISO 13485 Design Control change processes.
- **EU MDR Post-Market Surveillance (PMS)**: EU MDR requires aggressive, proactive PMS (Article 83) and Periodic Safety Update Reports (PSUR). Integrating ISO 14971:2019 post-production risk updates with MDR vigilance timelines is a current industry pain point.
- **Data Privacy & Security (GDPR/HIPAA vs. ISO 27001)**: The {ctx.environment} implies the processing of Sensitive Personal Health Information (PHI). Compliance requires cross-mapping ISO 13485 with ISO/IEC 27001 (Information Security Management Systems) and ISO 27799 (Health informatics).

## 3. Advanced Requirements & Recent Changes
### 3.1 FDA Refuse to Accept (RTA) Policy for Cybersecurity
The FDA now actively refuses premarket submissions (510(k), PMA, De Novo) under section 524B of the FD&C Act if the application lacks a comprehensive cybersecurity plan, including:
- An SBOM formatted in CycloneDX or SPDX.
- A plan for issuing out-of-band security updates (patches) without requiring a new FDA submission.
- Threat modeling using STRIDE or similar methodologies.

### 3.2 IEC 81001-5-1 Transition
The transition from IEC 62304 to incorporating IEC 81001-5-1 (Health software and health IT systems safety, effectiveness and security) is critical. For the {ctx.name}, secure product development framework (SPDF) processes must be integrated into the QMS.

### 3.3 EU MDR Transition Extensions
While EU MDR transition deadlines have been extended, devices must not undergo "significant changes" in design or intended purpose to benefit from the extension. Implementing security patches without triggering a "significant change" review requires a highly robust, pre-approved change management procedure under ISO 13485 §7.3.9.

## 4. Required Fixes & Compliance Strategies (Absolute & Accurate Implementation)
To achieve absolute compliance, the manufacturer of the {ctx.name} must implement the following structural QMS changes:

1. **Integrated QMS/ISMS**: Merge ISO 13485 QMS processes with ISO/IEC 27001 ISMS. Corrective Action (CAPA) boards must now include the Chief Information Security Officer (CISO) for security incident handling.
2. **Dynamic Risk Management (ISO 14971 + TIR57/TIR97)**: Risk management files must be dynamic. Implement automated vulnerability scanning in the CI/CD pipeline (for software components) that flags Common Vulnerabilities and Exposures (CVEs). Any CVE with a CVSS score > 7.0 must trigger a real-time risk evaluation per ISO 14971 §10.
3. **Automated Regulatory Traceability**: Adopt ALM (Application Lifecycle Management) tools to maintain bidirectional traceability from User Needs (IEC 62366-1) -> System Requirements -> Software Items (IEC 62304) -> Threat Models (FDA Cyber) -> Test Cases.
4. **Patch Management SOP**: Create a specific SOP for "Cybersecurity Patch Deployment" that bypasses standard lengthy Design Review for zero-day vulnerabilities, leveraging the "routine update" exception under FDA guidance, provided the update does not affect the clinical functionality of the {ctx.name}.

## 5. Conclusion
Failure to adapt to the overlapping requirements of EU MDR, FDA Cybersecurity provisions, and ISO security standards will result in market access delays. The {ctx.name} lifecycle must transition from a static waterfall compliance model to a continuous, secure-by-design, and risk-based agile framework.
"""
    return instruction, target

# ---------------------------------------------------------------------------
# Artifact: Clause-level analysis (short-form)
# ---------------------------------------------------------------------------

def clause_mapping(ctx: DeviceContext) -> tuple[str, str]:
    instruction = (
        f"Map the device described below to the most relevant ISO 13485:2016 and "
        f"21 CFR Part 820 clauses, with a one-sentence rationale per clause."
    )
    target = f"""# Clause Mapping — {ctx.name}

## Device summary
- **Class**: {ctx.device_class}
- **Risk**: {ctx.risk_profile.title()}
- **Intended User**: {ctx.intended_user}
- **Environment**: {ctx.environment}

## Primary clauses

| Clause                         | Why it applies                                                                                     |
|-------------------------------|----------------------------------------------------------------------------------------------------|
| ISO 13485 §7.1                | Planning of product realization for a {ctx.risk_profile}-risk device requires documented planning. |
| ISO 13485 §7.3.2              | Design and development planning is mandatory before any design output is produced.                 |
| ISO 13485 §7.3.3              | Design inputs must capture the IFU, intended user ({ctx.intended_user}), and use environment.     |
| ISO 13485 §7.3.7              | Design validation is required to confirm performance for {ctx.intended_user}.                     |
| ISO 13485 §8.2.2              | Complaint handling — directly applicable once on market.                                            |
| ISO 13485 §8.5.2              | Corrective action triggered by nonconformities or complaints.                                       |
| 21 CFR 820.30                 | Design Controls; applicable to all {ctx.device_class} devices except 820.30(a)(2) exemptions.       |
| 21 CFR 820.100                | CAPA — required regardless of class.                                                               |
| 21 CFR 820.198                | Complaint Files — establishes the formal Complaint Handling Unit.                                   |
| 21 CFR 820.181                | Device Master Record — the single source of truth for the device's specs.                          |

## Secondary considerations

- **ISO 14971** for risk management (referenced from ISO 13485 §7.1).
- **IEC 62366-1** for usability engineering, given the {ctx.intended_user}.
- **21 CFR Part 803** for Medical Device Reporting once the device is on market.
"""
    return instruction, target


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

ARTIFACT_BUILDERS = [
    sop_design_controls,
    sop_capa,
    sop_risk_management,
    advanced_regulatory_scenario,  # <-- Added advanced scenario
    clause_mapping,
]


def build_examples(rng: random.Random, target_count: int) -> list[dict]:
    """Generate ``target_count`` JSONL-ready records."""
    out: list[dict] = []
    contexts = list(iter_contexts(rng, limit=max(target_count, 60)))
    rng.shuffle(contexts)

    # Round-robin across artifact types to keep the dataset balanced.
    builder_cycle = itertools.cycle(ARTIFACT_BUILDERS)
    for ctx in contexts:
        if len(out) >= target_count:
            break
        builder = next(builder_cycle)
        instruction, target = builder(ctx)
        out.append({
            "device_context": ctx.render(),
            "instruction": instruction,
            "target": target,
        })

    # If we still don't have enough, double back through builders on existing
    # contexts so each device gets multiple artifact types.
    if len(out) < target_count:
        for ctx in contexts:
            for builder in ARTIFACT_BUILDERS:
                if len(out) >= target_count:
                    break
                instruction, target = builder(ctx)
                rec = {
                    "device_context": ctx.render(),
                    "instruction": instruction,
                    "target": target,
                }
                if rec not in out:
                    out.append(rec)
            if len(out) >= target_count:
                break

    return out


def write_split(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    logger.info("Wrote %d records → %s", len(records), path)

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="data/synthetic")
    parser.add_argument("--total", type=int, default=540,
                        help="Total examples to generate (spec target: 500+).")
    parser.add_argument("--train-eval-split", type=float, default=0.9)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    records = build_examples(rng, args.total)
    rng.shuffle(records)

    split = int(len(records) * args.train_eval_split)
    train, eval_ = records[:split], records[split:]

    out_dir = Path(args.output_dir)
    write_split(train, out_dir / "train.jsonl")
    write_split(eval_, out_dir / "eval.jsonl")


if __name__ == "__main__":
    main()