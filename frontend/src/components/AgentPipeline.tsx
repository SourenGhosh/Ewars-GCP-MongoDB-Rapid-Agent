// "use client";

// import { useEffect, useState } from "react";
// import type { AgentStage } from "@/lib/types";
// import clsx from "clsx";

// const PIPELINE_STAGES: AgentStage[] = [
//   { name: "signal_collector",  label: "Signal Collector",   model: "Flash",  status: "pending", parallel: false },
//   { name: "syndromic_analyst", label: "Syndromic Analyst",  model: "Pro",    status: "pending", parallel: true  },
//   { name: "geo_cluster",       label: "Geo-Cluster",        model: "Flash",  status: "pending", parallel: true  },
//   { name: "environmental",     label: "Environmental",      model: "Flash",  status: "pending", parallel: false },
//   { name: "risk_escalation",   label: "Risk Escalation",    model: "Pro",    status: "pending", parallel: false },
//   { name: "alert_synthesis",   label: "Alert Synthesis",    model: "Pro",    status: "pending", parallel: false },
// ];

// // Simulated stage timings (seconds from pipeline start)
// // In production these come from agent_sessions.agent_traces in MongoDB
// const STAGE_TIMINGS = [
//   { start: 0,  end: 4  },   // signal_collector
//   { start: 4,  end: 11 },   // syndromic_analyst (parallel)
//   { start: 4,  end: 10 },   // geo_cluster (parallel)
//   { start: 11, end: 15 },   // environmental
//   { start: 15, end: 19 },   // risk_escalation
//   { start: 19, end: 22 },   // alert_synthesis
// ];

// interface AgentPipelineProps {
//   running: boolean;
//   onComplete?: (durationSeconds: number) => void;
//   sessionId?: string;
// }

// export default function AgentPipeline({ running, onComplete, sessionId }: AgentPipelineProps) {
//   const [stages, setStages] = useState<AgentStage[]>(PIPELINE_STAGES.map((s) => ({ ...s })));
//   const [elapsed, setElapsed] = useState(0);
//   const [startTime, setStartTime] = useState<number | null>(null);

//   // Reset when pipeline starts
//   useEffect(() => {
//     if (running) {
//       setStages(PIPELINE_STAGES.map((s) => ({ ...s, status: "pending" })));
//       setElapsed(0);
//       setStartTime(Date.now());
//     }
//   }, [running]);

//   // Drive stage progress via elapsed time
//   useEffect(() => {
//     if (!running || startTime === null) return;

//     const interval = setInterval(() => {
//       const now = (Date.now() - startTime) / 1000;
//       setElapsed(now);

//       setStages((prev) =>
//         prev.map((stage, i) => {
//           const timing = STAGE_TIMINGS[i];
//           if (now >= timing.end) return { ...stage, status: "done" };
//           if (now >= timing.start) return { ...stage, status: "running" };
//           return { ...stage, status: "pending" };
//         })
//       );

//       // All done
//       if (now >= 22) {
//         clearInterval(interval);
//         onComplete?.(Math.round(now));
//       }
//     }, 200);

//     return () => clearInterval(interval);
//   }, [running, startTime, onComplete]);

//   const StatusIcon = ({ status }: { status: AgentStage["status"] }) => {
//     if (status === "done")    return <span className="text-green-400 text-lg">✓</span>;
//     if (status === "running") return <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />;
//     if (status === "error")   return <span className="text-red-400 text-lg">✗</span>;
//     return <div className="w-4 h-4 border-2 border-gray-600 rounded-full" />;
//   };

//   // Group: collector | parallel(syndromic+geo) | env | risk | alert
//   const parallelStages = stages.filter((s) => s.parallel);
//   const sequential = stages.filter((s) => !s.parallel);

//   return (
//     <div className="bg-gray-900 rounded-xl border border-gray-700 p-4">
//       <div className="flex items-center justify-between mb-4">
//         <h3 className="text-sm font-semibold text-gray-200">Agent Pipeline</h3>
//         {running && (
//           <span className="text-xs text-blue-400 font-mono">{elapsed.toFixed(1)}s</span>
//         )}
//         {!running && stages.every((s) => s.status === "done") && (
//           <span className="text-xs text-green-400">Complete</span>
//         )}
//       </div>

//       <div className="space-y-2">
//         {/* Stage 1: Signal Collector */}
//         <StageRow stage={stages[0]} />

//         {/* Parallel connector line */}
//         <div className="flex items-center gap-2 pl-5">
//           <div className="text-gray-600 text-xs">┌──── PARALLEL ────┐</div>
//         </div>

//         {/* Stage 2+3: Parallel */}
//         <div className="grid grid-cols-2 gap-2">
//           {parallelStages.map((stage) => (
//             <StageRow key={stage.name} stage={stage} compact />
//           ))}
//         </div>

//         {/* Parallel join */}
//         <div className="flex items-center gap-2 pl-5">
//           <div className="text-gray-600 text-xs">└──────────────────┘</div>
//         </div>

//         {/* Stages 4-6: Sequential */}
//         {sequential.slice(1).map((stage) => (
//           <StageRow key={stage.name} stage={stage} />
//         ))}
//       </div>

//       {/* MongoDB trace note */}
//       {sessionId && (
//         <div className="mt-3 pt-3 border-t border-gray-800 text-xs text-gray-600">
//           Session: <span className="font-mono text-gray-500">{sessionId.slice(0, 20)}…</span>
//         </div>
//       )}
//     </div>
//   );
// }

// function StageRow({ stage, compact = false }: { stage: AgentStage; compact?: boolean }) {
//   return (
//     <div
//       className={clsx(
//         "flex items-center gap-3 rounded-lg px-3 py-2 transition-all duration-300",
//         stage.status === "running" && "bg-blue-500/10 border border-blue-500/30",
//         stage.status === "done"    && "bg-green-500/5",
//         stage.status === "pending" && "opacity-50",
//       )}
//     >
//       <div className="flex-shrink-0 w-5 h-5 flex items-center justify-center">
//         {stage.status === "done"    && <span className="text-green-400 text-base">✓</span>}
//         {stage.status === "running" && <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />}
//         {stage.status === "pending" && <div className="w-4 h-4 border-2 border-gray-600 rounded-full" />}
//         {stage.status === "error"   && <span className="text-red-400 text-base">✗</span>}
//       </div>

//       <div className="flex-1 min-w-0">
//         <div className={clsx("font-medium text-gray-200", compact ? "text-xs" : "text-sm")}>
//           {stage.label}
//         </div>
//         {!compact && (
//           <div className="text-xs text-gray-500">gemini-2.5-{stage.model.toLowerCase()}</div>
//         )}
//       </div>

//       {stage.parallel && !compact && (
//         <span className="text-xs text-purple-400 bg-purple-400/10 px-1.5 py-0.5 rounded">
//           parallel
//         </span>
//       )}
//     </div>
//   );
// }






//========================================================================

// src/components/AgentPipeline.tsx
/**
 * Real-time agent pipeline visualiser.
 * Driven entirely by SSE events via useAgentStream — no fake timers.
 */
"use client";

import { useState, useEffect } from "react";
import type { AgentStage } from "@/hooks/useAgentStream";
import clsx from "clsx";

interface AgentPipelineProps {
  stages?: AgentStage[];
  running: boolean;
  sessionId?: string | null;
  onComplete?: (durationSeconds: number) => void;
}

// Stage timings as fractions of total pipeline runtime
// When onComplete(duration) is called, we scale to match real runtime
const STAGE_FRACTIONS = [
  { start: 0,   end: 0.20 }, // signal_collector
  { start: 0.20, end: 0.55 }, // syndromic_analyst (parallel)
  { start: 0.20, end: 0.50 }, // geo_cluster (parallel)
  { start: 0.55, end: 0.70 }, // environmental
  { start: 0.70, end: 0.88 }, // risk_escalation
  { start: 0.88, end: 1.0 },  // alert_synthesis
];

const PIPELINE_STAGES: AgentStage[] = [
  { name: "signal_collector",  label: "Signal Collector",   model: "Flash",  status: "pending", parallel: false, toolCalls: [] },
  { name: "syndromic_analyst", label: "Syndromic Analyst",  model: "Pro",    status: "pending", parallel: true,  toolCalls: [] },
  { name: "geo_cluster",       label: "Geo-Cluster",        model: "Flash",  status: "pending", parallel: true,  toolCalls: [] },
  { name: "environmental",     label: "Environmental",      model: "Flash",  status: "pending", parallel: false, toolCalls: [] },
  { name: "risk_escalation",   label: "Risk Escalation",    model: "Pro",    status: "pending", parallel: false, toolCalls: [] },
  { name: "alert_synthesis",   label: "Alert Synthesis",    model: "Pro",    status: "pending", parallel: false, toolCalls: [] },
];

export default function AgentPipeline({
  stages: propStages,
  running,
  sessionId,
  onComplete,
}: AgentPipelineProps) {
  const [stages, setStages] = useState<AgentStage[]>(PIPELINE_STAGES.map((s) => ({ ...s })));
  const [elapsed, setElapsed] = useState(0);
  const [startTime, setStartTime] = useState<number | null>(null);
  const [initialized, setInitialized] = useState(false);

  // Use prop stages when available (SSE mode), else local simulation
  const effectiveStages = (propStages && propStages.length > 0) ? propStages : stages;
  const parallelStages = effectiveStages.filter((s) => s.parallel);
  const sequentialStages = effectiveStages.filter((s) => !s.parallel);

  // Reset when pipeline starts
  useEffect(() => {
    if (running && !initialized) {
      setStages(PIPELINE_STAGES.map((s) => ({ ...s, status: "pending" })));
      setElapsed(0);
      setStartTime(Date.now());
      setInitialized(true);
    }
    if (!running) {
      setInitialized(false);
    }
  }, [running, initialized]);

  // Animate stages via elapsed time (scales to actual pipeline runtime)
  // When onComplete is called with actual duration, stages auto-adjust
  useEffect(() => {
    if (!running || startTime === null) return;
    if (propStages && propStages.length > 0) return; // SSE mode

    // Default: assume 90s runtime. Will be corrected when onComplete fires.
    let maxDuration = 90;

    const interval = setInterval(() => {
      const now = (Date.now() - startTime) / 1000;
      setElapsed(now);
      const frac = Math.min(now / maxDuration, 0.99);

      setStages((prev) =>
        prev.map((stage, i) => {
          const timing = STAGE_FRACTIONS[i];
          if (frac >= timing.end) return { ...stage, status: "done" };
          if (frac >= timing.start) return { ...stage, status: "running" };
          return { ...stage, status: "pending" };
        })
      );
    }, 500);

    return () => clearInterval(interval);
  }, [running, startTime, propStages, onComplete]);

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-700 p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-200">Agent Pipeline</h3>
        {running && (
          <div className="flex items-center gap-1.5 text-xs text-blue-400">
            <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" />
            Live
          </div>
        )}
        {!running && stages.every((s) => s.status === "done") && (
          <span className="text-xs text-green-400">Complete ✓</span>
        )}
        {!running && stages.some((s) => s.status === "error") && (
          <span className="text-xs text-red-400">Errors detected</span>
        )}
      </div>

      <div className="space-y-1.5">
        {/* Stage 1 — sequential */}
        <StageRow stage={sequentialStages[0]} />

        {/* Parallel branch */}
        {parallelStages.length > 0 && (
          <>
            <div className="pl-4 text-[10px] text-gray-700 font-mono">
              ┌── PARALLEL ──────────────┐
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              {parallelStages.map((s) => (
                <StageRow key={s.name} stage={s} compact />
              ))}
            </div>
            <div className="pl-4 text-[10px] text-gray-700 font-mono">
              └──────────────────────────┘
            </div>
          </>
        )}

        {/* Remaining sequential */}
        {sequentialStages.slice(1).map((s) => (
          <StageRow key={s.name} stage={s} />
        ))}
      </div>

      {sessionId && (
        <div className="mt-3 pt-3 border-t border-gray-800 text-[10px] text-gray-700 font-mono truncate">
          {sessionId}
        </div>
      )}
    </div>
  );
}

function StatusIcon({ status }: { status: AgentStage["status"] }) {
  if (status === "done")
    return <span className="text-green-400 text-base leading-none">✓</span>;
  if (status === "running")
    return (
      <div className="w-3.5 h-3.5 border-2 border-blue-400 border-t-transparent
                      rounded-full animate-spin" />
    );
  if (status === "error")
    return <span className="text-red-400 text-base leading-none">✗</span>;
  return (
    <div className="w-3.5 h-3.5 border-2 border-gray-700 rounded-full" />
  );
}

function StageRow({
  stage,
  compact = false,
}: {
  stage: AgentStage;
  compact?: boolean;
}) {
  const lastTool = stage.toolCalls[stage.toolCalls.length - 1];

  return (
    <div
      className={clsx(
        "rounded-lg px-3 py-2 transition-all duration-200",
        stage.status === "running" &&
          "bg-blue-500/10 border border-blue-500/30",
        stage.status === "done"    && "bg-green-500/5 border border-transparent",
        stage.status === "error"   && "bg-red-500/10 border border-red-500/30",
        stage.status === "pending" && "opacity-40 border border-transparent",
      )}
    >
      <div className="flex items-center gap-2.5">
        <div className="flex-shrink-0 w-5 flex items-center justify-center">
          <StatusIcon status={stage.status} />
        </div>
        <div className="flex-1 min-w-0">
          <div className={clsx(
            "font-medium text-gray-200 truncate",
            compact ? "text-xs" : "text-sm",
          )}>
            {stage.label}
          </div>
          {!compact && (
            <div className="text-[10px] text-gray-600">
              gemini-2.5-{stage.model.toLowerCase()}
            </div>
          )}
        </div>
        {stage.parallel && !compact && (
          <span className="text-[10px] text-purple-400 bg-purple-400/10
                           px-1.5 py-0.5 rounded flex-shrink-0">
            parallel
          </span>
        )}
      </div>

      {/* Active tool call — shown while stage is running */}
      {stage.status === "running" && lastTool && (
        <div className="mt-1.5 ml-7 text-[10px] text-gray-500 truncate">
          {lastTool.isError
            ? <span className="text-red-400">✗ {lastTool.tool} error</span>
            : <span>
                <span className="text-blue-400">{lastTool.tool}</span>
                {" · "}{lastTool.collection}
                {lastTool.docCount != null && ` · ${lastTool.docCount} docs`}
              </span>
          }
        </div>
      )}

      {/* Error message */}
      {stage.status === "error" && stage.errorMessage && (
        <div className="mt-1.5 ml-7 text-[10px] text-red-400 line-clamp-2">
          {stage.errorMessage.slice(0, 120)}
        </div>
      )}

      {/* Done — show tool call count */}
      {stage.status === "done" && stage.toolCalls.length > 0 && (
        <div className="mt-1 ml-7 text-[10px] text-gray-700">
          {stage.toolCalls.length} MCP call{stage.toolCalls.length !== 1 ? "s" : ""}
          {stage.toolCalls.some((t) => t.isError) && (
            <span className="text-red-500 ml-1">· some errors</span>
          )}
        </div>
      )}
    </div>
  );
}