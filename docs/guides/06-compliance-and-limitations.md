# Compliance & Limitations

> **Read this carefully if you intend to use Compliance-Llama output for anything that touches a real Quality Management System.**

Compliance-Llama is a **drafting assistant**, not a regulatory affairs (RA) professional. This document describes what the system is and is not, what it can be relied upon for, and what mitigations are required before its output enters a controlled QMS.

---

## What this system is

A fine-tuned Llama 3.1 70B model that, given a structured device context, drafts SOPs and QMS artifacts in a format that **resembles** audit-ready output, with **citations** to specific clauses of:

- ISO 13485:2016 — Medical devices: Quality management systems
- FDA 21 CFR Part 820 — Quality System Regulation
- ISO 14971:2019 — Application of risk management to medical devices (referenced)
- IEC 62366-1, 62304, 60601 (referenced where relevant)

The model has been trained on synthetic examples that pair device contexts with structured SOP outputs. The clause numbers and structural patterns the model has learned reflect the public versions of these standards as of training-data cutoff.

## What this system is **not**

| Not                                      | Why it matters                                                                                  |
|------------------------------------------|--------------------------------------------------------------------------------------------------|
| A substitute for an RA professional      | Final responsibility for compliance rests with qualified humans. Always.                         |
| A real-time clause database              | Standards are updated. New revisions of ISO 13485 or 21 CFR 820 will not be reflected until retrain. |
| Jurisdictionally exhaustive              | The model is trained primarily on US (FDA) + global (ISO) frameworks. EU MDR specifics, MHRA, PMDA, NMPA, etc. are referenced but not fully covered. |
| A predicate-device search tool           | It will not tell you whether a 510(k) predicate exists; that is FDA database work.              |
| A clinical evaluation tool               | Clinical evidence assessments require domain expertise far beyond text generation.              |

## Known failure modes

### 1. Clause hallucination

The model can — and will, under sufficient distributional shift — output clause numbers that don't exist or that exist but say something different. We trained against this, but the failure mode is fundamental to LLMs.

**Mitigation:** every clause cited in output must be cross-checked against the canonical text of the standard before it is used. The "References" section of every generated SOP makes this auditable; treat it as a checklist for your RA reviewer, not as ground truth.

### 2. Revision drift

Standards change. ISO 13485:2016 supersedes ISO 13485:2003; if a future ISO 13485:202x is released, this model has no way to know about it.

**Mitigation:** check the version stamp on every clause cited. If your QMS targets a different revision than what the model assumes, re-fine-tune or post-process.

### 3. Risk classification confusion

The model takes the user-provided device class as ground truth. If you tell it a Class III device is Class I, it will produce Class-I-shaped output.

**Mitigation:** classification is itself a regulatory determination. The user filling in the form must be qualified to make that call.

### 4. Format-over-substance bias

Because the training set rewards the SOP shape (Purpose / Scope / Responsibilities / …), the model will produce a complete-looking SOP even when it has nothing concrete to say. Empty-but-confident sections are a known artifact.

**Mitigation:** review every section for content density, not just presence.

### 5. Jurisdictional conflation

The model knows ISO 13485 and 21 CFR 820 are different documents but related. It can occasionally cite a clause from one as if it were from the other, or apply EU MDR vocabulary inside a US-focused SOP.

**Mitigation:** specify the target jurisdiction explicitly in `additional_notes` and verify consistency in the output.

---

## Required workflow when using output for real QMS

1. **Generate** the artifact via Compliance-Llama with an accurate device context.
2. **Review** every clause citation against the canonical source (paid or controlled copies of ISO 13485 / 21 CFR 820 in your organization's library).
3. **Edit** for organizational specifics: actual role names, cross-references to other internal SOPs, your own document numbering scheme.
4. **Sign off** through your existing document control workflow. The generated artifact is a draft input to that workflow, not its output.
5. **Record** the model version and prompt used. Treat them as the equivalent of a contract author identity for traceability. (The exported PDF embeds this metadata.)

---

## What we explicitly do NOT claim

- **No regulatory accuracy guarantee.** Outputs are best-effort approximations.
- **No fitness for any specific purpose** beyond drafting assistance.
- **No conformance** to ISO 13485:2016 §4.1.6 (validation of computer software used in the QMS) on this tool's behalf — if you intend to *use this tool inside a regulated QMS process*, that validation is your responsibility and likely substantial.
- **No legal advice.** Compliance is fundamentally a legal/regulatory determination.

---

## Privacy & data handling

- Compliance-Llama is **self-hosted**. No device context, generated SOP, or other user data leaves the AMD MI300X instance unless you explicitly export it.
- The training data shipped in this repo is **fully synthetic** — no real device disclosures, no proprietary RA documents.
- Logs (the FastAPI gateway's request log) include the device-context payload by default. Disable structured request logging (`CL_LOG_LEVEL=WARNING`) if your environment requires it.
- The PDF export embeds a generation timestamp but no other PII.

---

## Reporting issues

If the model produces output that is materially wrong (e.g. a clause that doesn't exist, a clearly wrong jurisdiction binding), please report it. For the hackathon submission this is informal; for any production deployment you should establish a CAPA-aligned issue tracker for the model itself — yes, the irony is intentional.
