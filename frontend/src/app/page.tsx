"use client";

import { useState, useCallback } from "react";
import dynamic from "next/dynamic";
import AgentPipeline    from "@/components/AgentPipeline";
import ThreatGauge      from "@/components/ThreatGauge";
import SitRepViewer     from "@/components/SitRepViewer";
import IngestTab        from "@/components/tabs/IngestTab";
import MonitorTab       from "@/components/tabs/MonitorTab";
import type { ThreatTier } from "@/lib/types";

const ThreatMap = dynamic(() => import("@/components/ThreatMap"), { ssr: false });
const EpidemicTimeline = dynamic(
  () => import("@/components/EpidemicTimeline"), { ssr: false }
);

type Tab = "monitor" | "timeline" | "ingest";

function tierColor(tier: string): string {
  const m: Record<string, string> = {
    EMERGENCY: "#ef4444", ALERT: "#f97316",
    WATCH: "#eab308", NORMAL: "#6b7280",
  };
  return m[tier] ?? "#6b7280";
}

export default function Dashboard() {
  const [tier, setTier]               = useState<ThreatTier>("NORMAL");
  const [score, setScore]             = useState(0);
  const [sitrepId, setSitrepId]       = useState<string | undefined>();
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [runningWeek, setRunningWeek] = useState<number | null>(null);
  const [tab, setTab]    = useState<Tab>("monitor");
  const [ingestCount, setIngestCount] = useState(0);

  const handleTierChange = useCallback(
    (newTier: ThreatTier, newScore: number, newSitrepId?: string) => {
      setTier(newTier);
      setScore(newScore);
      if (newSitrepId) {
        setSitrepId(newSitrepId);
        setTab("monitor");
      }
    }, []
  );

  const handleRunWeek = useCallback(
    async (regionId: string, demoTag: string | null, demoWeek: number) => {
      setRunningWeek(demoWeek);
      setPipelineRunning(true);
      try {
        const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080/ewars";
        const res = await fetch(`${API}/run`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            region_id: regionId,
            demo_tag: demoTag ?? undefined,
            demo_week: demoWeek,
            trigger_type: "demo",
          }),
        });
        if (!res.ok) throw new Error(`Pipeline HTTP ${res.status}`);
        const data = await res.json();
        handleTierChange(
          data.threat_tier as ThreatTier,
          data.composite_score ?? 0,
          data.sitrep_id ?? undefined,
        );
      } catch (e) {
        console.error("Pipeline run failed:", e);
      } finally {
        setPipelineRunning(false);
        setRunningWeek(null);
      }
    },
    [handleTierChange]
  );

  const TABS: { key: Tab; label: string }[] = [
    { key: "monitor",  label: "Monitor"  },
    { key: "timeline", label: "Timeline" },
    { key: "ingest",   label: "Ingest"   },
  ];

  return (
    <div className="min-h-screen bg-gray-950 text-white overflow-hidden flex flex-col">
      <header className="border-b border-gray-800 px-6 py-3 flex items-center
                         justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-red-500/20 border border-red-500/50 rounded-lg
                          flex items-center justify-center text-red-400 text-lg">⚕</div>
          <div>
            <h1 className="text-sm font-bold tracking-wide">EWARS</h1>
            <p className="text-xs text-gray-500">
              Epidemic Early Warning & Response System
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4 text-xs text-gray-500">
          {tier !== "NORMAL" && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full
                            border font-medium"
              style={{
                borderColor:     tierColor(tier) + "44",
                backgroundColor: tierColor(tier) + "15",
                color:           tierColor(tier),
              }}>
              <div className="w-1.5 h-1.5 rounded-full animate-pulse"
                style={{ backgroundColor: tierColor(tier) }} />
              {tier}
            </div>
          )}
          {pipelineRunning ? (
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 border-2 border-blue-400/30 border-t-blue-400
                              rounded-full animate-spin" />
              <span className="text-blue-400">Pipeline running…</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
              Live surveillance
            </div>
          )}
        </div>
      </header>

      {/* Pipeline timer display */}
      {pipelineRunning && (
        <div className="px-4 py-1 text-[10px] text-gray-600 text-center flex-shrink-0">
          Pipeline running — ~90s expected
        </div>
      )}

      <main className="flex-1 p-4 grid grid-cols-12 gap-4 min-h-0">
        {/* Left: Gauge + Pipeline */}
        <div className="col-span-3 flex flex-col gap-4 min-h-0">
          <div className="bg-gray-900 rounded-xl border border-gray-700 p-4 flex-shrink-0">
            <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
              Current Threat Level
            </h2>
            <ThreatGauge tier={tier} score={score} animating={pipelineRunning} />
          </div>
          <AgentPipeline
            running={pipelineRunning}
            onComplete={() => setPipelineRunning(false)}
          />
        </div>

        {/* Centre: Map */}
        <div className="col-span-5 min-h-0">
          <ThreatMap />
        </div>

        {/* Right: Tabs */}
        <div className="col-span-4 flex flex-col gap-3 min-h-0">
          <div className="flex gap-1 bg-gray-900 rounded-xl border border-gray-700
                          p-1 flex-shrink-0">
            {TABS.map(({ key, label }) => (
              <button key={key}
                onClick={() => {
                  setTab(key);
                  if (key === "ingest") setIngestCount(0);
                }}
                className={`relative flex-1 py-2 text-xs font-medium rounded-lg
                            transition-colors ${
                  tab === key
                    ? "bg-gray-700 text-white"
                    : "text-gray-500 hover:text-gray-300"
                }`}>
                {label}
                {key === "ingest" && ingestCount > 0 && tab !== "ingest" && (
                  <span className="absolute -top-1 -right-1 w-4 h-4 bg-blue-500
                                   text-white text-[9px] font-bold rounded-full
                                   flex items-center justify-center">
                    {ingestCount > 9 ? "9+" : ingestCount}
                  </span>
                )}
              </button>
            ))}
          </div>

          <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
            {tab === "monitor" && (
              <div className="flex flex-col gap-3 overflow-y-auto flex-1 min-h-0">
                <MonitorTab
                  onTierChange={handleTierChange}
                  onPipelineStart={() => setPipelineRunning(true)}
                  onPipelineComplete={() => setPipelineRunning(false)}
                />
                <SitRepViewer sitrepId={sitrepId} />
              </div>
            )}

            {tab === "timeline" && (
              <div className="flex-1 relative flex flex-col min-h-0
                              bg-gray-900 rounded-xl border border-gray-700 overflow-hidden">
                <EpidemicTimeline
                  onRunWeek={handleRunWeek}
                  onSitRepSelect={(id) => { setSitrepId(id); setTab("monitor"); }}
                  runningWeek={runningWeek}
                />
              </div>
            )}

            {tab === "ingest" && (
              <div className="flex-1 overflow-y-auto min-h-0">
                <IngestTab onIngestComplete={(n) => setIngestCount((c) => c + n)} />
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}