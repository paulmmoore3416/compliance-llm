import type { ArtifactType, DeviceContext } from "../types/api";

interface Props {
  device: DeviceContext;
  setDevice: (d: DeviceContext) => void;
  artifact: ArtifactType;
  setArtifact: (a: ArtifactType) => void;
  customInstruction: string;
  setCustomInstruction: (s: string) => void;
  temperature: number;
  setTemperature: (n: number) => void;
  maxTokens: number;
  setMaxTokens: (n: number) => void;
  onGenerate: () => void;
  onCompare: () => void;
  isGenerating: boolean;
  comparisonAvailable: boolean;
}

const ARTIFACT_LABELS: Record<ArtifactType, string> = {
  design_controls_sop: "Design Controls SOP (ISO 13485 §7.3 / 21 CFR 820.30)",
  capa_sop: "CAPA SOP (ISO 13485 §8.5.2 / 21 CFR 820.100)",
  risk_management_sop: "Risk Management SOP (ISO 14971)",
  complaint_handling_sop: "Complaint Handling SOP (21 CFR 820.198)",
  document_control_sop: "Document Control SOP (21 CFR 820.40)",
  clause_mapping: "Clause Mapping (rationale per clause)",
  custom: "Custom instruction",
};

function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs uppercase tracking-wide text-amd-muted">{label}</span>
      {children}
      {hint && <span className="text-[11px] text-amd-muted">{hint}</span>}
    </label>
  );
}

const inputCls =
  "bg-amd-panel border border-amd-border rounded px-3 py-2 text-sm text-amd-text " +
  "focus:outline-none focus:ring-2 focus:ring-amd-red/40 focus:border-amd-red/40";

export function DeviceContextPanel(props: Props) {
  const { device, setDevice, artifact, setArtifact, onGenerate, onCompare, isGenerating } = props;

  const update = <K extends keyof DeviceContext>(key: K, value: DeviceContext[K]) =>
    setDevice({ ...device, [key]: value });

  return (
    <div className="bg-amd-surface border border-amd-border rounded-lg p-5 flex flex-col gap-4">
      <div>
        <h2 className="font-semibold text-amd-text">Context Window</h2>
        <p className="text-xs text-amd-muted mt-0.5">
          Describe the device. Compliance-Llama uses these inputs to scope clauses, controls, and language.
        </p>
      </div>

      <Field label="Device name">
        <input
          className={inputCls}
          value={device.name}
          onChange={(e) => update("name", e.target.value)}
          placeholder="e.g. Continuous Glucose Monitor"
        />
      </Field>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Device class">
          <select
            className={inputCls}
            value={device.device_class}
            onChange={(e) => update("device_class", e.target.value as DeviceContext["device_class"])}
          >
            <option>Class I</option>
            <option>Class II</option>
            <option>Class III</option>
          </select>
        </Field>
        <Field label="Risk profile">
          <select
            className={inputCls}
            value={device.risk_profile}
            onChange={(e) => update("risk_profile", e.target.value as DeviceContext["risk_profile"])}
          >
            <option value="low">Low</option>
            <option value="moderate">Moderate</option>
            <option value="high">High</option>
          </select>
        </Field>
      </div>

      <Field label="Indication for use" hint="The labeled clinical purpose, in patient-facing language.">
        <textarea
          className={inputCls + " min-h-[72px] resize-y"}
          value={device.indication_for_use}
          onChange={(e) => update("indication_for_use", e.target.value)}
          placeholder="e.g. Continuous interstitial glucose monitoring in patients with diabetes mellitus to support insulin dosing decisions."
        />
      </Field>

      <Field label="Intended user">
        <input
          className={inputCls}
          value={device.intended_user}
          onChange={(e) => update("intended_user", e.target.value)}
          placeholder="e.g. diabetes self-management patients aged 14+"
        />
      </Field>

      <Field label="Use environment">
        <input
          className={inputCls}
          value={device.use_environment}
          onChange={(e) => update("use_environment", e.target.value)}
          placeholder="e.g. patient home"
        />
      </Field>

      <Field label="Additional notes" hint="Optional. Software class, materials, etc.">
        <textarea
          className={inputCls + " min-h-[60px] resize-y"}
          value={device.additional_notes ?? ""}
          onChange={(e) => update("additional_notes", e.target.value)}
        />
      </Field>

      <hr className="border-amd-border" />

      <Field label="Artifact to generate">
        <select
          className={inputCls}
          value={artifact}
          onChange={(e) => setArtifact(e.target.value as ArtifactType)}
        >
          {Object.entries(ARTIFACT_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
      </Field>

      {artifact === "custom" && (
        <Field label="Custom instruction">
          <textarea
            className={inputCls + " min-h-[80px] resize-y"}
            value={props.customInstruction}
            onChange={(e) => props.setCustomInstruction(e.target.value)}
            placeholder="e.g. Draft a Sterilization Validation SOP per ISO 11135 referenced from ISO 13485 §7.5.7"
          />
        </Field>
      )}

      <div className="grid grid-cols-2 gap-3">
        <Field label={`Temperature: ${props.temperature.toFixed(2)}`}>
          <input
            type="range" min={0} max={1.5} step={0.05}
            value={props.temperature}
            onChange={(e) => props.setTemperature(parseFloat(e.target.value))}
            className="accent-amd-red"
          />
        </Field>
        <Field label={`Max tokens: ${props.maxTokens}`}>
          <input
            type="range" min={256} max={4096} step={64}
            value={props.maxTokens}
            onChange={(e) => props.setMaxTokens(parseInt(e.target.value))}
            className="accent-amd-red"
          />
        </Field>
      </div>

      <div className="flex flex-col gap-2 pt-2">
        <button
          onClick={onGenerate}
          disabled={isGenerating}
          className="bg-amd-red hover:bg-amd-red/90 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium px-4 py-2.5 rounded transition"
        >
          {isGenerating ? "Generating…" : "Generate (streaming)"}
        </button>
        <button
          onClick={onCompare}
          disabled={isGenerating || !props.comparisonAvailable}
          className="bg-amd-panel border border-amd-border hover:border-amd-red/60 disabled:opacity-50 disabled:cursor-not-allowed text-amd-text font-medium px-4 py-2 rounded transition text-sm"
          title={props.comparisonAvailable ? "Run base Llama vs Compliance-Llama side-by-side" : "Set BASE_LLAMA_URL on the API to enable"}
        >
          Compare with base Llama 3.1
        </button>
      </div>
    </div>
  );
}
