// src/hooks/useAgentStream.ts
/**
 * Custom hook that connects to the EWARS SSE stream endpoint.
 * Returns real agent stage state + log entries.
 *
 * Usage:
 *   const { stages, logs, tier, running, connect } = useAgentStream();
 *   connect({ regionId: "guangdong-cn", demoTag: "sars_replay", demoWeek: 1 });
 */

import { useState, useCallback, useRef } from "react";
import type { ThreatTier } from "@/lib/types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080/ewars";

// ── Types ─────────────────────────────────────────────────────────────────────
export type AgentStatus = "pending" | "running" | "done" | "error";

export interface AgentStage {
  name: string;
  label: string;
  model: string;
  status: AgentStatus;
  parallel: boolean;
  toolCalls: ToolCallEntry[];
  errorMessage?: string;
  startedAt?: number;
  finishedAt?: number;
}

export interface ToolCallEntry {
  tool: string;
  collection: string;
  filterPreview: string;
  resultPreview?: string;
  docCount?: number | null;
  isError?: boolean;
  timestamp: number;
}

export interface LogEntry {
  id: string;
  type: string;
  agent: string;
  label: string;
  message: string;
  isError: boolean;
  timestamp: number;
  raw?: Record<string, unknown>;
}

export interface StreamState {
  stages: AgentStage[];
  logs: LogEntry[];
  tier: ThreatTier | null;
  score: number;
  sitrepId: string | null;
  sessionId: string | null;
  running: boolean;
  error: string | null;
}

// Initial pipeline stages — parallel flag marks concurrent agents
const INITIAL_STAGES: AgentStage[] = [
  { name: "signal_collector",  label: "Signal Collector",  model: "Flash", status: "pending", parallel: false, toolCalls: [] },
  { name: "syndromic_analyst", label: "Syndromic Analyst", model: "Pro",   status: "pending", parallel: true,  toolCalls: [] },
  { name: "geo_cluster",       label: "Geo-Cluster",       model: "Flash", status: "pending", parallel: true,  toolCalls: [] },
  { name: "environmental",     label: "Environmental",     model: "Flash", status: "pending", parallel: false, toolCalls: [] },
  { name: "risk_escalation",   label: "Risk Escalation",   model: "Pro",   status: "pending", parallel: false, toolCalls: [] },
  { name: "alert_synthesis",   label: "Alert Synthesis",   model: "Pro",   status: "pending", parallel: false, toolCalls: [] },
];

function resetStages(): AgentStage[] {
  return INITIAL_STAGES.map((s) => ({ ...s, status: "pending", toolCalls: [], errorMessage: undefined }));
}

function makeLog(event: Record<string, unknown>): LogEntry {
  const type = String(event.type || "unknown");
  const agent = String(event.agent || "pipeline");
  const label = String(event.label || agent);
  const ts = Date.now();

  let message = "";
  let isError = false;

  switch (type) {
    case "pipeline_start":
      message = `Pipeline started · session ${String(event.session_id || "").slice(0, 20)}…`;
      break;
    case "agent_start":
      message = `${label} started (gemini-2.5-${String(event.model || "").toLowerCase()})`;
      break;
    case "tool_call":
      message = `→ ${String(event.tool || "")} on '${String(event.collection || "")}' ${event.filter_preview ? `· filter: ${String(event.filter_preview).slice(0, 80)}` : ""}`;
      break;
    case "tool_result":
      if (event.is_error) {
        message = `✗ ${String(event.tool || "")} error: ${String(event.result_preview || "").slice(0, 120)}`;
        isError = true;
      } else {
        message = `← ${String(event.tool || "")} returned ${event.doc_count != null ? `${event.doc_count} docs` : "result"} ${event.result_preview ? `· ${String(event.result_preview).slice(0, 80)}` : ""}`;
      }
      break;
    case "thinking":
      message = `⋯ ${String(event.fragment || "").slice(0, 120)}`;
      break;
    case "agent_done":
      message = `${label} completed${event.output_preview ? ` · ${String(event.output_preview).slice(0, 100)}` : ""}`;
      break;
    case "error":
      message = `✗ ${String(event.error_code || "ERROR")}: ${String(event.message || "").slice(0, 200)}${event.hint ? ` — ${String(event.hint)}` : ""}`;
      isError = true;
      break;
    case "fatal_error":
      message = `✗ Fatal: ${String(event.message || "").slice(0, 300)}`;
      isError = true;
      break;
    case "pipeline_done":
      message = `Pipeline complete · tier=${String(event.threat_tier)} · score=${String(event.composite_score ?? 0)} · ${String(event.duration_seconds ?? 0)}s`;
      break;
    default:
      message = JSON.stringify(event).slice(0, 150);
  }

  return { id: `${ts}-${Math.random()}`, type, agent, label, message, isError, timestamp: ts, raw: event };
}


export function useAgentStream() {
  const [state, setState] = useState<StreamState>({
    stages: resetStages(),
    logs: [],
    tier: null,
    score: 0,
    sitrepId: null,
    sessionId: null,
    running: false,
    error: null,
  });

  const esRef = useRef<EventSource | null>(null);

  const connect = useCallback((params: {
    regionId: string;
    demoTag?: string | null;
    demoWeek?: number | null;
  }) => {
    // Close existing connection
    esRef.current?.close();

    // Reset state
    setState({
      stages: resetStages(),
      logs: [],
      tier: null,
      score: 0,
      sitrepId: null,
      sessionId: null,
      running: true,
      error: null,
    });

    // Build SSE URL
    const url = new URL(`${API}/run/stream`);
    url.searchParams.set("region_id", params.regionId);
    if (params.demoTag)  url.searchParams.set("demo_tag",  params.demoTag);
    if (params.demoWeek) url.searchParams.set("demo_week", String(params.demoWeek));

    const es = new EventSource(url.toString());
    esRef.current = es;

    es.onmessage = (e) => {
      let event: Record<string, unknown>;
      try {
        event = JSON.parse(e.data);
      } catch {
        return;
      }

      const log = makeLog(event);
      const type = event.type as string;

      setState((prev) => {
        let stages = [...prev.stages];
        const logs = [...prev.logs, log];

        // Keep log at max 200 entries to avoid memory bloat
        const trimmedLogs = logs.slice(-200);

        const updateStage = (name: string, patch: Partial<AgentStage>) => {
          stages = stages.map((s) =>
            s.name === name ? { ...s, ...patch } : s
          );
        };

        const addToolCall = (name: string, entry: ToolCallEntry) => {
          stages = stages.map((s) =>
            s.name === name
              ? { ...s, toolCalls: [...s.toolCalls, entry] }
              : s
          );
        };

        switch (type) {
          case "agent_start":
            updateStage(String(event.agent), {
              status: "running",
              startedAt: Date.now(),
            });
            break;

          case "tool_call":
            addToolCall(String(event.agent), {
              tool:          String(event.tool || ""),
              collection:    String(event.collection || ""),
              filterPreview: String(event.filter_preview || ""),
              timestamp:     Date.now(),
            });
            break;

          case "tool_result":
            // Update the most recent tool call for this agent with its result
            stages = stages.map((s) => {
              if (s.name !== String(event.agent)) return s;
              const calls = [...s.toolCalls];
              if (calls.length > 0) {
                calls[calls.length - 1] = {
                  ...calls[calls.length - 1],
                  resultPreview: String(event.result_preview || ""),
                  docCount:      event.doc_count as number | null,
                  isError:       Boolean(event.is_error),
                };
              }
              return { ...s, toolCalls: calls };
            });
            break;

          case "agent_done":
            updateStage(String(event.agent), {
              status:     "done",
              finishedAt: Date.now(),
            });
            break;

          case "error":
            updateStage(String(event.agent), {
              status:       "error",
              errorMessage: String(event.message || ""),
            });
            break;

          case "pipeline_done":
            es.close();
            return {
              ...prev,
              stages,
              logs: trimmedLogs,
              tier:      String(event.threat_tier) as ThreatTier,
              score:     Number(event.composite_score || 0),
              sitrepId:  event.sitrep_id as string | null,
              sessionId: event.session_id as string | null,
              running:   false,
            };

          case "fatal_error":
            es.close();
            return {
              ...prev,
              stages,
              logs: trimmedLogs,
              running: false,
              error:   String(event.message || "Unknown error"),
            };
        }

        return { ...prev, stages, logs: trimmedLogs };
      });
    };

    es.onerror = () => {
      es.close();
      setState((prev) => ({
        ...prev,
        running: false,
        error: "SSE connection lost",
      }));
    };
  }, []);

  const disconnect = useCallback(() => {
    esRef.current?.close();
    setState((prev) => ({ ...prev, running: false }));
  }, []);

  return { ...state, connect, disconnect };
}