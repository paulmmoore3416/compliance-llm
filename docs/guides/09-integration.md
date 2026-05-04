# Integration Guide

Welcome to the **Compliance-LLM Integration Guide**. This document explains how to connect your running Compliance-LLM model to your existing enterprise software, specifically your **Quality Management System (QMS)**.

By integrating the AI directly into your QMS, you can automate workflows like drafting Standard Operating Procedures (SOPs) or analyzing Nonconformance Reports (NCRs)—all while keeping your data secure.

---

## 1. The MedTech LLM Integration Suite

To make integration as seamless as possible, we provide the **MedTech LLM Integration Suite** (located in the `medtech-llm-integration/` folder). 

Think of this suite as a **Gateway** or **Bridge**. 
- Your QMS speaks its own language.
- Compliance-LLM speaks the language of AI prompts.
- The **Gateway** sits in the middle, translating requests from your QMS into well-structured prompts for the AI, and then securely returning the AI's answers back to your QMS.

---

## 2. How the Integration Works

Here is a simplified view of the integration flow:

1. **User Action:** A user clicks "Draft SOP" inside your QMS.
2. **QMS Request:** Your QMS sends a secure API request containing device context to the Gateway.
3. **Gateway Processing:** The Gateway formats this data into a specific prompt optimized for compliance.
4. **AI Generation:** The Gateway asks Compliance-LLM to generate the SOP.
5. **Response:** The Gateway receives the SOP, formats it correctly, and pushes it back into your QMS as a new draft document.

---

## 3. Step-by-Step Integration

### Step A: Start the API Gateway
First, you need to get the Gateway running.

1. Navigate to the integration folder:
   ```bash
   cd medtech-llm-integration
   ```
2. Start the Gateway using Docker Compose:
   ```bash
   docker-compose up -d
   ```
3. The Gateway is now listening for requests, typically on `http://localhost:8080`. You can view the interactive API documentation by visiting `http://localhost:8080/docs` in your browser.

### Step B: Configure Your QMS
You will need to configure your QMS to send webhooks or API calls to the Gateway. 

Depending on your QMS (e.g., Veeva, Greenlight Guru, Qualio, or a custom build), you will configure it to point to specific Gateway endpoints.

### Step C: Understand the Core Endpoints
The Gateway provides specific "endpoints" (URLs) designed for MedTech workflows. Here are the most common ones you will integrate with:

* **Generate an SOP (`/api/v1/qms/generate-sop`)**
  * **Use Case:** Automatically draft procedures that cite ISO 13485 clauses.
  * **How to use:** Send your device context (e.g., "Class II software device") to this endpoint.

* **Triage an NCR (`/api/v1/ncr/triage`)**
  * **Use Case:** Evaluate Nonconformance Reports to determine if a Corrective and Preventive Action (CAPA) is required.
  * **How to use:** Send the raw text of a defect report to this endpoint for an automated risk assessment.

* **Analyze Risk (`/api/v1/risk/analyze-hazard`)**
  * **Use Case:** Map failure modes to risk scores according to ISO 14971.

---

## 4. Example: Triaging an NCR

Let's look at a practical example of how your QMS would communicate with the Gateway to triage an NCR.

Your QMS sends a piece of data (a `POST` request) to the Gateway:
```json
{
  "ncr_id": "NCR-2024-001",
  "description": "The battery on the portable monitor drained twice as fast as expected during normal operation.",
  "device_class": "Class II"
}
```

The Gateway processes this, consults Compliance-LLM, and returns a structured response to your QMS:
```json
{
  "capa_recommended": true,
  "severity": "High",
  "iso_13485_clause": "8.3.1 - Control of nonconforming product",
  "rationale": "Unexpected rapid battery drain impacts device availability and poses a potential risk to continuous patient monitoring, requiring immediate investigation and a CAPA."
}
```
Your QMS can then use this data to automatically flag the NCR for review or open a draft CAPA!

---

## Conclusion

By using the MedTech LLM Integration Suite, you can securely build AI-powered workflows into your existing quality systems. If you need help modifying the Gateway for a specific, proprietary QMS, please consult the developer documentation inside the `medtech-llm-integration` folder.