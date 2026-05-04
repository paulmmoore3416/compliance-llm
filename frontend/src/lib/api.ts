import type {
  CompareResponse,
  GenerateRequest,
  GenerateResponse,
  HealthResponse,
} from "../types/api";

const BASE = (import.meta.env.VITE_API_BASE_URL as string) ?? "http://localhost:8080";

export async function checkHealth(): Promise<HealthResponse> {
  const r = await fetch(`${BASE}/health`);
  if (!r.ok) throw new Error(`Health check failed: ${r.status}`);
  return r.json();
}

export async function generate(req: GenerateRequest): Promise<GenerateResponse> {
  const r = await fetch(`${BASE}/v1/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(`Generate failed (${r.status}): ${text}`);
  }
  return r.json();
}

export async function compare(req: GenerateRequest): Promise<CompareResponse> {
  const r = await fetch(`${BASE}/v1/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...req, compare_with_base: true }),
  });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(`Compare failed (${r.status}): ${text}`);
  }
  return r.json();
}

/**
 * Stream generation tokens via SSE.
 * Manually parses Server-Sent Events because the browser EventSource API does
 * not support POST bodies, which we need to send the GenerateRequest payload.
 */
export async function streamGenerate(
  req: GenerateRequest,
  onToken: (delta: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const resp = await fetch(`${BASE}/v1/generate/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(req),
    signal,
  });
  if (!resp.ok || !resp.body) {
    throw new Error(`Stream failed (${resp.status})`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE messages are separated by a blank line ("\n\n")
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);

      let event = "message";
      let data = "";
      for (const line of raw.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trimStart();
      }
      if (event === "token" && data) onToken(data);
      if (event === "done") return;
      if (event === "error") throw new Error(data || "Unknown stream error");
    }
  }
}

export async function exportPdf(content: string, deviceName: string, artifact: string): Promise<Blob> {
  const r = await fetch(`${BASE}/v1/export/pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, device_name: deviceName, artifact }),
  });
  if (!r.ok) throw new Error(`PDF export failed (${r.status})`);
  return r.blob();
}
