# Comprehensive Project Overview & Use Documentation: Compliance-Llama

## Introduction

**Compliance-Llama** is an advanced, audit-ready Standard Operating Procedure (SOP) generator designed specifically for medical-device regulatory compliance. It leverages a fine-tuned Large Language Model (LLM) to transform basic device descriptions into structured, clause-cited QMS artifacts. 

**Special Acknowledgement:** This entire project, including advanced synthetic data generation, codebase structuring, and comprehensive documentation, was rapidly developed and architected using the powerful **Gemini 3 Pro CLI**. The intelligence and speed of Google's Gemini models enabled the seamless integration of complex regulatory frameworks into a functional, end-to-end application.

## Core Capabilities & Advanced Regulatory Scenarios

Compliance-Llama goes beyond basic compliance drafting. Thanks to its enhanced synthetic dataset, the model handles highly complex, real-world regulatory convergence scenarios, including:

*   **ISO 13485:2016 & 21 CFR Part 820**: Foundational QMS requirements, Design Controls, CAPA, and Document Control.
*   **ISO 14971:2019**: Advanced Risk Management integration for medical devices.
*   **Software as a Medical Device (SaMD) & Cybersecurity**: Deep integration of the **FDA 2023 Cybersecurity Guidance**, highlighting Software Bill of Materials (SBOM) requirements, vulnerability disclosure, and secure-by-design principles.
*   **Data Security & Privacy**: Handling the intersection of **ISO/IEC 27001**, **HIPAA**, and **GDPR** for cloud-connected and AI-enabled medical devices.
*   **IEC 62304 / IEC 81001-5-1**: Software lifecycle processes and the transition to Secure Product Development Frameworks (SPDF).

## Architecture

The system is built on a modern, high-performance stack:
1.  **Frontend**: React + TypeScript + Tailwind CSS, offering a real-time, token-streaming Context Window UI with side-by-side comparisons and PDF export capabilities.
2.  **Backend**: A FastAPI gateway handling SSE (Server-Sent Events) stream multiplexing, input validation, and PDF rendering.
3.  **Inference Engine**: vLLM running on AMD Instinct MI300X (192 GB HBM3), utilizing FP8 quantization for interactive latency at scale.
4.  **Training Pipeline**: QLoRA fine-tuning using `bitsandbytes` (ROCm fork) and AMD Quark for FP8 export.

## How to Use Compliance-Llama

### 1. Generating an SOP
1.  Navigate to the Frontend UI (`http://localhost:5173`).
2.  In the **Device Context Panel**, input the details of your medical device:
    *   **Device Name** (e.g., "AI-Enabled Radiology Triage Software")
    *   **Device Class** (e.g., "SaMD Class II")
    *   **Risk Profile** (e.g., "Moderate")
    *   **Intended User** (e.g., "Radiologists supervising AI-assisted reads")
    *   **Use Environment** (e.g., "Hospital IT Network")
    *   **Indication for Use**
3.  Select the desired artifact type (e.g., *Design Controls*, *CAPA*, *Advanced Regulatory Scenario*).
4.  Click **Generate**. The system will stream back a highly detailed, clause-cited document.

### 2. Handling Advanced Cybersecurity Scenarios
To generate an impact analysis for modern connected devices:
1.  Provide the context for a connected or AI-enabled device (e.g., "Cloud-Based Clinical Decision Support").
2.  Select the **Advanced Regulatory Scenario** prompt.
3.  The model will output a comprehensive analysis detailing the required fixes for FDA Refuse to Accept (RTA) cybersecurity policies, EU MDR transitions, and ISO 27001 integrations.

### 3. Review and Export
1.  Use the **Output Panel** to review the generated markdown.
2.  Verify the citations (e.g., ISO 13485 §7.3.3, 21 CFR 820.30(c)).
3.  Click **Export to PDF** to download the audit-ready document.

## Disclaimer & Compliance Notice
Compliance-Llama is a highly advanced drafting aid, built with the power of Gemini 3 Pro. However, it does not replace a certified Regulatory Affairs (RA) professional. All generated outputs must be thoroughly reviewed and validated against current laws before formal submission to regulatory bodies like the FDA or Notified Bodies.

---
## Project Repositories
*   [Quality and Compliance App](https://github.com/paulmmoore3416/qualityandcomplianceapp)
*   [Compliance LLM](https://github.com/paulmmoore3416/compliance-llm)

*Built with ❤️ and the intelligence of the Gemini 3 Pro CLI. #Google #Gemini #Gemini3Pro*