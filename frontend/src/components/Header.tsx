import { useEffect, useState } from "react";
import { checkHealth } from "../lib/api";

export function Header() {
  const [status, setStatus] = useState<"loading" | "ok" | "degraded" | "down">("loading");
  const [model, setModel] = useState<string>("");

  useEffect(() => {
    let live = true;
    const tick = async () => {
      try {
        const h = await checkHealth();
        if (!live) return;
        setStatus(h.status === "ok" ? "ok" : "degraded");
        setModel(h.fine_tuned_model);
      } catch {
        if (live) setStatus("down");
      }
    };
    tick();
    const id = setInterval(tick, 15000);
    return () => {
      live = false;
      clearInterval(id);
    };
  }, []);

  const dot =
    status === "ok"
      ? "bg-green-500"
      : status === "degraded"
      ? "bg-yellow-500"
      : status === "down"
      ? "bg-red-500"
      : "bg-amd-muted";

  return (
    <header className="border-b border-amd-border bg-amd-surface px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <img src="/favicon.svg" alt="Compliance-Llama Logo" className="w-8 h-8 rounded" />
        <div>
          <div className="font-semibold text-amd-text leading-tight">Compliance-Llama</div>
          <div className="text-xs text-amd-muted leading-tight">
            Llama 3.1 70B · QLoRA fine-tune · AMD Instinct MI300X · ROCm 6.2 · FP8
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2 text-xs text-amd-muted">
        <span className={`inline-block w-2 h-2 rounded-full ${dot}`} />
        <span>{status === "loading" ? "checking…" : status}</span>
        {model && <span className="ml-2 px-2 py-0.5 rounded bg-amd-panel border border-amd-border">{model}</span>}
      </div>
    </header>
  );
}
