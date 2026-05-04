# API Reference

Base URL: `http://localhost:8080` (default `docker-compose` mapping).

All POST endpoints accept and return `application/json` unless noted. The streaming endpoint returns `text/event-stream`.

---

## `GET /health`

Liveness + vLLM reachability probe.

**Response 200**

```json
{
  "status": "ok",
  "vllm_reachable": true,
  "fine_tuned_model": "compliance-llama-70b"
}
```

`status` is `"degraded"` if the gateway is up but cannot reach vLLM.

---

## `POST /v1/generate`

Single-shot generation. Returns the full SOP as one JSON payload.

**Request**

```json
{
  "device": {
    "name": "Continuous Glucose Monitor",
    "device_class": "Class II",
    "indication_for_use": "Continuous interstitial glucose monitoring for patients with diabetes mellitus to support insulin dosing decisions.",
    "risk_profile": "moderate",
    "intended_user": "diabetes self-management patients aged 14+",
    "use_environment": "patient home",
    "additional_notes": "Software classified as IEC 62304 Class B."
  },
  "artifact": "design_controls_sop",
  "custom_instruction": null,
  "temperature": 0.2,
  "max_tokens": 2048,
  "compare_with_base": false
}
```

**Field reference**

| Field                      | Type    | Required | Notes                                                                       |
|----------------------------|---------|----------|-----------------------------------------------------------------------------|
| `device.name`              | str     | yes      | Free text.                                                                  |
| `device.device_class`      | enum    | yes      | One of `"Class I"`, `"Class II"`, `"Class III"`.                            |
| `device.indication_for_use` | str    | yes      | Min 20 chars. Patient-facing labeling language.                             |
| `device.risk_profile`      | enum    | yes      | `"low"` / `"moderate"` / `"high"`.                                          |
| `device.intended_user`     | str     | yes      | Min 3 chars.                                                                |
| `device.use_environment`   | str     | yes      | Min 3 chars.                                                                |
| `device.additional_notes`  | str?    | no       | Free text.                                                                  |
| `artifact`                 | enum    | yes      | See [Artifact types](#artifact-types).                                      |
| `custom_instruction`       | str?    | conditional | Required iff `artifact == "custom"`. Free-form prompt.                  |
| `temperature`              | float   | yes      | 0.0 – 2.0. Default 0.2. Regulatory text doesn't want creativity.            |
| `max_tokens`               | int     | yes      | 64 – 8192. Capped server-side at `MAX_OUTPUT_TOKENS`.                      |
| `compare_with_base`        | bool    | no       | Hint only — the dedicated `/v1/compare` endpoint is what actually runs both. |

**Response 200**

```json
{
  "artifact": "design_controls_sop",
  "model": "compliance-llama-70b",
  "content": "# SOP-DC-001: Design and Development Planning ...",
  "output_tokens": 1247,
  "latency_ms": 8421
}
```

**Errors**

- `422` — input validation (e.g. `indication_for_use` too short).
- `502` — vLLM upstream returned an error.
- `503` — vLLM unreachable.

---

## `POST /v1/generate/stream`

Server-Sent Events streaming. Same request schema as `/v1/generate`.

**Response 200, `text/event-stream`**

```
event: token
data: # SOP

event: token
data: -DC-001

...

event: done
data: ok
```

Events:

- `token` — `data:` is the next text delta. Concatenate them.
- `done` — terminal success. Close the connection.
- `error` — terminal failure. `data:` is a human-readable message.

The frontend's [`streamGenerate`](../../frontend/src/lib/api.ts) is a reference parser. EventSource is intentionally not used — it doesn't support POST bodies.

---

## `POST /v1/compare`

Same request as `/v1/generate`. Runs both models and returns paired payloads. Requires `BASE_LLAMA_URL` to be set on the API container.

**Response 200**

```json
{
  "fine_tuned": {
    "artifact": "design_controls_sop",
    "model": "compliance-llama-70b",
    "content": "# SOP-DC-001 ...",
    "output_tokens": 1247,
    "latency_ms": 8421
  },
  "base": {
    "artifact": "design_controls_sop",
    "model": "llama-3.1-70b-instruct",
    "content": "Sure! Here's a Design Controls SOP ...",
    "output_tokens": 980,
    "latency_ms": 7311
  }
}
```

**Errors**

- `503` — base endpoint not configured (`BASE_LLAMA_URL` is empty).

---

## `POST /v1/export/pdf`

Renders a previously generated SOP (or any Markdown) to a styled PDF.

**Request**

```json
{
  "content": "# SOP-DC-001\n\n...",
  "device_name": "Continuous Glucose Monitor",
  "artifact": "design_controls_sop"
}
```

**Response 200, `application/pdf`** — the file. `Content-Disposition: attachment; filename=...` is set; browsers will download directly.

---

## Artifact types

| Value                       | Spec basis                                | Output shape                                 |
|----------------------------|-------------------------------------------|---------------------------------------------|
| `design_controls_sop`       | ISO 13485 §7.3, 21 CFR 820.30             | Full SOP, 8 sections, citations throughout. |
| `capa_sop`                  | ISO 13485 §8.5.2/§8.5.3, 21 CFR 820.100   | CAPA workflow with effectiveness criteria.  |
| `risk_management_sop`       | ISO 14971, ISO 13485 §7.1                 | Lifecycle risk management procedure.        |
| `complaint_handling_sop`    | ISO 13485 §8.2.2, 21 CFR 820.198, 21 CFR 803 | Complaint workflow w/ MDR matrix.        |
| `document_control_sop`      | ISO 13485 §4.2.4, 21 CFR 820.40           | Doc control + retention.                    |
| `clause_mapping`            | derived                                   | Short-form clause-by-clause table.          |
| `custom`                    | user-provided                             | Whatever the model produces.                |

---

## OpenAPI / Swagger

The FastAPI app auto-generates an OpenAPI spec. Browse it at:

- `http://localhost:8080/docs` — Swagger UI (interactive).
- `http://localhost:8080/redoc` — ReDoc (read-only).
- `http://localhost:8080/openapi.json` — raw spec for codegen.

---

## Example: Python client

```python
import httpx

req = {
    "device": {
        "name": "Insulin Infusion Pump",
        "device_class": "Class II",
        "indication_for_use": "Continuous subcutaneous insulin infusion for patients with diabetes requiring insulin therapy.",
        "risk_profile": "high",
        "intended_user": "home-care patients with manufacturer training",
        "use_environment": "patient home",
    },
    "artifact": "capa_sop",
    "temperature": 0.2,
    "max_tokens": 2048,
}

resp = httpx.post("http://localhost:8080/v1/generate", json=req, timeout=120)
resp.raise_for_status()
print(resp.json()["content"])
```

## Example: cURL streaming

```bash
curl -N -H "Content-Type: application/json" \
    -d '{"device":{"name":"AED","device_class":"Class III","indication_for_use":"Automated external defibrillation for sudden cardiac arrest in adults and children.","risk_profile":"high","intended_user":"EMS first responders","use_environment":"ambulance"},"artifact":"risk_management_sop","temperature":0.2,"max_tokens":1024}' \
    http://localhost:8080/v1/generate/stream
```
