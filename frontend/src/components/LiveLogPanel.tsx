// src/components/LiveLogPanel.tsx
/**
 * Collapsible real-time log panel.
 * Shows every agent interaction: tool calls, results, errors, thinking.
 * Judges and experts can see exactly what each agent is doing.
 */
"use client";

import { useEffect, useRef, useState } from "react";
import type { LogEntry } from "@/hooks/useAgentStream";

const TYPE_COLOR: Record<string, string> = {
  pipeline_start:  "#6b7280",
  agent_start:     "#60a5fa",
  tool_call:       "#a78bfa",
  tool_result:     "#34d399",
  thinking:        "#6b7280",
  agent_done:      "#60a5fa",
  error:           "#f87171",
  fatal_error:     "#ef4444",
  pipeline_done:   "#22c55e",
};

const TYPE_LABEL: Record<string, string> = {
  pipeline_start:  "START",
  agent_start:     "AGENT",
  tool_call:       "CALL",
  tool_result:     "RESULT",
  thinking:        "THINK",
  agent_done:      "DONE",
  error:           "ERROR",
  fatal_error:     "FATAL",
  pipeline_done:   "FINISH",
};

interface LiveLogPanelProps {
  logs: LogEntry[];
  running: boolean;
  defaultOpen?: boolean;
}

export default function LiveLogPanel({
  logs,
  running,
  defaultOpen = false,
}: LiveLogPanelProps) {
  const [open, setOpen]         = useState(defaultOpen);
  const [autoScroll, setScroll] = useState(true);
  const [filter, setFilter]     = useState<"all" | "errors" | "tools">("all");
  const bottomRef               = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && open && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, autoScroll, open]);

  const filtered = logs.filter((log) => {
    if (filter === "errors") return log.isError;
    if (filter === "tools")  return ["tool_call", "tool_result"].includes(log.type);
    return log.type !== "thinking";   // default: hide thinking fragments
  });

  const errorCount = logs.filter((l) => l.isError).length;

  return (
    <div className={`bg-gray-950 border-t border-gray-800 flex-shrink-0 transition-all ${
      open ? "h-56" : "h-9"
    }`}>
      {/* Header bar */}
      <div
        onClick={() => setOpen((v) => !v)}
        className="flex items-center justify-between px-4 h-9 cursor-pointer
                   hover:bg-gray-900/50 select-none"
      >
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono font-medium text-gray-400">
            Agent Logs
          </span>
          {running && (
            <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse" />
          )}
          {errorCount > 0 && (
            <span className="text-[10px] bg-red-500/20 text-red-400 px-1.5
                             py-0.5 rounded font-mono">
              {errorCount} error{errorCount !== 1 ? "s" : ""}
            </span>
          )}
          <span className="text-[10px] text-gray-700 font-mono">
            {logs.length} events
          </span>
        </div>

        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
          {open && (
            <>
              {/* Filter buttons */}
              {(["all", "tools", "errors"] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`text-[10px] px-2 py-0.5 rounded font-mono ${
                    filter === f
                      ? "bg-gray-700 text-gray-200"
                      : "text-gray-600 hover:text-gray-400"
                  }`}
                >
                  {f}
                </button>
              ))}

              {/* Auto-scroll toggle */}
              <button
                onClick={() => setScroll((v) => !v)}
                className={`text-[10px] px-2 py-0.5 rounded font-mono ${
                  autoScroll
                    ? "bg-blue-500/20 text-blue-400"
                    : "text-gray-600"
                }`}
              >
                {autoScroll ? "↓ scroll" : "scroll off"}
              </button>

              {/* Clear */}
              <button
                onClick={() => {/* logs are managed by parent state */}}
                className="text-[10px] text-gray-700 hover:text-gray-500 font-mono"
              >
                ↑ {open ? "hide" : "show"}
              </button>
            </>
          )}

          <span className="text-gray-700 text-xs">{open ? "▼" : "▲"}</span>
        </div>
      </div>

      {/* Log entries */}
      {open && (
        <div
          className="overflow-y-auto h-[calc(100%-2.25rem)] px-4 py-2
                     font-mono text-[11px] space-y-0.5"
          onScroll={(e) => {
            const el = e.currentTarget;
            const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 20;
            setScroll(atBottom);
          }}
        >
          {filtered.length === 0 && (
            <div className="text-gray-700 py-2">
              {running ? "Waiting for events…" : "No log entries yet."}
            </div>
          )}

          {filtered.map((log) => (
            <div key={log.id} className="flex gap-2 items-start group">
              {/* Timestamp */}
              <span className="text-gray-700 flex-shrink-0 w-14">
                {new Date(log.timestamp).toLocaleTimeString("en-GB", {
                  hour: "2-digit", minute: "2-digit", second: "2-digit",
                })}
              </span>

              {/* Type badge */}
              <span
                className="flex-shrink-0 w-14 text-center px-1 rounded"
                style={{
                  backgroundColor: (TYPE_COLOR[log.type] ?? "#6b7280") + "22",
                  color: TYPE_COLOR[log.type] ?? "#6b7280",
                }}
              >
                {TYPE_LABEL[log.type] ?? log.type.toUpperCase().slice(0, 6)}
              </span>

              {/* Agent */}
              <span className="text-gray-600 flex-shrink-0 w-20 truncate">
                {log.label.slice(0, 12)}
              </span>

              {/* Message */}
              <span
                className={`flex-1 min-w-0 break-words leading-relaxed ${
                  log.isError ? "text-red-400" : "text-gray-400"
                }`}
              >
                {log.message}
              </span>
            </div>
          ))}

          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
}