import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { exportPdf } from "../lib/api";

interface Props {
  title: string;
  subtitle?: string;
  content: string;
  metadata?: { model?: string; tokens?: number; latencyMs?: number };
  deviceName: string;
  artifact: string;
  isStreaming?: boolean;
  empty?: string;
}

export function OutputPanel({
  title, subtitle, content, metadata, deviceName, artifact, isStreaming, empty,
}: Props) {
  const onCopy = async () => {
    await navigator.clipboard.writeText(content);
  };

  const onExport = async () => {
    const blob = await exportPdf(content, deviceName || "Device", artifact);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `compliance-llama-${artifact}-${(deviceName || "device").replace(/\s+/g, "_")}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="bg-amd-surface border border-amd-border rounded-lg flex flex-col h-full">
      <div className="border-b border-amd-border px-5 py-3 flex items-center justify-between gap-3">
        <div>
          <div className="font-semibold text-sm flex items-center gap-2">
            <span>{title}</span>
            {isStreaming && (
              <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wide text-amd-red">
                <span className="w-1.5 h-1.5 rounded-full bg-amd-red animate-pulse" />
                streaming
              </span>
            )}
          </div>
          {subtitle && <div className="text-xs text-amd-muted">{subtitle}</div>}
        </div>
        <div className="flex items-center gap-2">
          {metadata && (metadata.tokens || metadata.latencyMs) && (
            <span className="text-xs text-amd-muted font-mono">
              {metadata.tokens ?? 0} tok · {((metadata.latencyMs ?? 0) / 1000).toFixed(2)}s
            </span>
          )}
          <button
            onClick={onCopy}
            disabled={!content}
            className="text-xs px-2 py-1 rounded border border-amd-border hover:border-amd-red/60 text-amd-muted disabled:opacity-40"
          >
            Copy
          </button>
          <button
            onClick={onExport}
            disabled={!content}
            className="text-xs px-2 py-1 rounded border border-amd-border hover:border-amd-red/60 text-amd-muted disabled:opacity-40"
          >
            Export PDF
          </button>
        </div>
      </div>

      <div className="overflow-y-auto p-5 flex-1 prose-cl">
        {content ? (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        ) : (
          <p className="text-amd-muted text-sm italic">{empty ?? "Output will appear here."}</p>
        )}
      </div>
    </div>
  );
}
