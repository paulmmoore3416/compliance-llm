export type DeviceClass = "Class I" | "Class II" | "Class III";
export type RiskProfile = "low" | "moderate" | "high";

export type ArtifactType =
  | "design_controls_sop"
  | "capa_sop"
  | "risk_management_sop"
  | "complaint_handling_sop"
  | "document_control_sop"
  | "clause_mapping"
  | "custom";

export interface DeviceContext {
  name: string;
  device_class: DeviceClass;
  indication_for_use: string;
  risk_profile: RiskProfile;
  intended_user: string;
  use_environment: string;
  additional_notes?: string;
}

export interface GenerateRequest {
  device: DeviceContext;
  artifact: ArtifactType;
  custom_instruction?: string;
  temperature: number;
  max_tokens: number;
  compare_with_base?: boolean;
}

export interface GenerateResponse {
  artifact: ArtifactType;
  model: string;
  content: string;
  output_tokens: number;
  latency_ms: number;
}

export interface CompareResponse {
  fine_tuned: GenerateResponse;
  base: GenerateResponse;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  vllm_reachable: boolean;
  fine_tuned_model: string;
}
