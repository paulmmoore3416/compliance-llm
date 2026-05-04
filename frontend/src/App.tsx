import { useCallback, useEffect, useRef, useState } from "react";
import { Header } from "./components/Header";
import { DeviceContextPanel } from "./components/DeviceContextPanel";
import { OutputPanel } from "./components/OutputPanel";
import { compare, streamGenerate, checkHealth } from "./lib/api";
import type {
  ArtifactType,
  CompareResponse,
  DeviceContext,
  GenerateRequest,
} from "./types/api";

const DEFAULT_DEVICE: DeviceContext = {
  name: "Continuous Glucose Monitor",
  device_class: "Class II",
  risk_profile: "moderate",
  indication_for_use:
    "Continuous interstitial glucose monitoring for patients with diabetes mellitus to support insulin dosing decisions.",
  intended_user: "diabetes self-management patients aged 14+",
  use_environment: "patient home",
  additional_notes: "",
};

export default function App() {
  const [device, setDevice] = useState<DeviceContext>(DEFAULT_DEVICE);
  const [artifact, setArtifact] = useState<ArtifactType>("design_controls_sop");
  const [customInstruction, setCustomInstruction] = useState("");
  const [temperature, setTemperature] = useState(0.2);
  const [maxTokens, setMaxTokens] = useState(2048);

  const [output, setOutput] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [comparison, setComparison] = useState<CompareResponse | null>(null);
  const [streamStartedAt, setStreamStartedAt] = useState<number | null>(null);
  const [streamMs, setStreamMs] = useState<number | null>(null);
  const [tokensSeen, setTokensSeen] = useState(0);
  const [comparisonAvailable, setComparisonAvailable] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    // Probe whether the comparison endpoint is wired up; the backend returns
    // 503 when BASE_LLAMA_URL is unset. We do this opportunistically.
    checkHealth().then(() => setComparisonAvailable(true)).catch(() => setComparisonAvailable(false));
  }, []);

  const buildRequest = useCallback((): GenerateRequest => ({
    device,
    artifact,
    custom_instruction: artifact === "custom" ? customInstruction : undefined,
    temperature,
    max_tokens: maxTokens,
  }), [device, artifact, customInstruction, temperature, maxTokens]);

  const onGenerate = useCallback(async () => {
    setError(null);
    setComparison(null);
    setOutput("");
    setTokensSeen(0);
    setStreamMs(null);
    setIsGenerating(true);
    setStreamStartedAt(performance.now());

    abortRef.current?.abort();
    abortRef.current = new AbortController();

    try {
      await streamGenerate(
        buildRequest(),
        (delta) => {
          setOutput((prev) => prev + delta);
          setTokensSeen((t) => t + 1);
        },
        abortRef.current.signal,
      );
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      if (msg !== "AbortError") setError(msg);
    } finally {
      setIsGenerating(false);
      setStreamMs(streamStartedAt ? performance.now() - streamStartedAt : null);
    }
  }, [buildRequest, streamStartedAt]);

  const onCompare = useCallback(async () => {
    setError(null);
    setOutput("");
    setComparison(null);
    setIsGenerating(true);
    try {
      const result = await compare(buildRequest());
      setComparison(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setIsGenerating(false);
    }
  }, [buildRequest]);

  return (
    <div className="min-h-screen flex flex-col">
      <Header />

      <main className="flex-1 grid grid-cols-12 gap-5 p-5 overflow-hidden">
        <aside className="col-span-12 lg:col-span-4 xl:col-span-3 overflow-y-auto pr-1">
          <DeviceContextPanel
            device={device}
            setDevice={setDevice}
            artifact={artifact}
            setArtifact={setArtifact}
            customInstruction={customInstruction}
            setCustomInstruction={setCustomInstruction}
            temperature={temperature}
            setTemperature={setTemperature}
            maxTokens={maxTokens}
            setMaxTokens={setMaxTokens}
            onGenerate={onGenerate}
            onCompare={onCompare}
            isGenerating={isGenerating}
            comparisonAvailable={comparisonAvailable}
          />
        </aside>

        <section className="col-span-12 lg:col-span-8 xl:col-span-9 flex flex-col gap-3 overflow-hidden">
          {error && (
            <div className="bg-red-950/40 border border-red-700/40 text-red-200 text-sm rounded p-3">
              {error}
            </div>
          )}

          {comparison ? (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-3 flex-1 overflow-hidden">
              <OutputPanel
                title="Base Llama 3.1 70B"
                subtitle="No fine-tuning. Generic instruct model."
                content={comparison.base.content}
                metadata={{ model: comparison.base.model, tokens: comparison.base.output_tokens, latencyMs: comparison.base.latency_ms }}
                deviceName={device.name}
                artifact={artifact}
              />
              <OutputPanel
                title="Compliance-Llama"
                subtitle="QLoRA fine-tune on ISO 13485 + 21 CFR 820."
                content={comparison.fine_tuned.content}
                metadata={{ model: comparison.fine_tuned.model, tokens: comparison.fine_tuned.output_tokens, latencyMs: comparison.fine_tuned.latency_ms }}
                deviceName={device.name}
                artifact={artifact}
              />
            </div>
          ) : (
            <div className="flex-1 overflow-hidden">
              <OutputPanel
                title="Generated Document"
                subtitle="Audit-ready draft. Human review required before release."
                content={output}
                metadata={{ tokens: tokensSeen, latencyMs: streamMs ?? undefined }}
                deviceName={device.name}
                artifact={artifact}
                isStreaming={isGenerating}
                empty="Fill in the device context and click Generate. Output streams live as the MI300X produces tokens."
              />
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
