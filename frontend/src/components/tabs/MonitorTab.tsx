// src/components/tabs/MonitorTab.tsx
"use client";

import { useEffect, useState, useCallback } from "react";
import type { ThreatTier } from "@/lib/types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080/ewars";

const TIER_COLORS: Record<string, string> = {
  WATCH:     "#eab308",
  ALERT:     "#f97316",
  EMERGENCY: "#ef4444",
  NORMAL:    "#6b7280",
};

const EVENT_LABELS: Record<string, { name: string; description: string }> = {
  sars_replay:       { name: "SARS 2002/03",       description: "Guangdong Province, China"  },
  ebola_replay:      { name: "Ebola 2013/14",       description: "Guéckédou, Guinea"          },
  cholera_scenario:  { name: "Cholera outbreak",    description: "Lagos, Nigeria"             },
  dengue_scenario:   { name: "Dengue cluster",      description: "Jakarta, Indonesia"         },
};

interface AvailableEvent {
  demo_tag:          string | null;
  region_id:         string;
  available_weeks:   number[];
  total_cases:       number;
  signal_count:      number;
  first_signal_date: string;
  type?:             string;
}

interface RunResult {
  tier:       ThreatTier;
  score:      number;
  duration:   number;
  session_id: string;
  sitrep_id?: string;
}

interface MonitorTabProps {
  onTierChange:       (tier: ThreatTier, score: number, sitrepId?: string) => void;
  onPipelineStart:    () => void;
  onPipelineComplete: () => void;
}

// ── Assessment Detail Component ─────────────────────────────────────────
function AssessmentDetail({ assessment, onClose }: { assessment: any; onClose: () => void }) {
  if (!assessment) return null;
  const tier = assessment.threat_tier || "WATCH";
  const color = TIER_COLORS[tier] || "#6b7280";

  return (
    <div className="bg-gray-800/80 border border-gray-700 rounded-xl p-4 space-y-3 relative">
      <button onClick={onClose} className="absolute top-2 right-2 text-gray-500 hover:text-white text-lg">×</button>
      <h3 className="text-sm font-semibold text-gray-200 flex items-center gap-2">
        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
        Threat Assessment Detail
      </h3>
      <div className="grid grid-cols-2 gap-3 text-xs">
        <div>
          <span className="text-gray-500">Tier:</span>
          <span className="ml-2 font-bold" style={{ color }}>{tier}</span>
        </div>
        <div>
          <span className="text-gray-500">Score:</span>
          <span className="ml-2 text-gray-200">{assessment.composite_score ?? "—"}</span>
        </div>
        <div>
          <span className="text-gray-500">Syndromic:</span>
          <span className="ml-2 text-gray-200">{assessment.syndromic_score ?? "—"}</span>
        </div>
        <div>
          <span className="text-gray-500">Geo:</span>
          <span className="ml-2 text-gray-200">{assessment.geo_score ?? "—"}</span>
        </div>
        <div>
          <span className="text-gray-500">Environmental:</span>
          <span className="ml-2 text-gray-200">{assessment.environmental_score ?? "—"}</span>
        </div>
        <div>
          <span className="text-gray-500">Confidence:</span>
          <span className="ml-2 text-gray-200">{assessment.confidence ?? "—"}</span>
        </div>
      </div>
      {assessment.escalation_rationale && (
        <div className="text-xs text-gray-400 border-t border-gray-700 pt-2 mt-1">
          <div className="text-gray-500 mb-1">Rationale:</div>
          {assessment.escalation_rationale.slice(0, 400)}
        </div>
      )}
      {assessment.recommended_actions?.length > 0 && (
        <div className="text-xs border-t border-gray-700 pt-2 mt-1">
          <div className="text-gray-500 mb-1">Actions:</div>
          {assessment.recommended_actions.slice(0, 3).map((a: string, i: number) => (
            <div key={i} className="text-gray-400 ml-2">• {a}</div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main MonitorTab ─────────────────────────────────────────────────────
export default function MonitorTab({
  onTierChange,
  onPipelineStart,
  onPipelineComplete,
}: MonitorTabProps) {
  const [events, setEvents]       = useState<AvailableEvent[]>([]);
  const [loading, setLoading]     = useState(true);
  const [runningKey, setRunningKey] = useState<string | null>(null);
  const [results, setResults]     = useState<Record<string, RunResult>>({});
  const [error, setError]         = useState<string | null>(null);
  const [selectedAssessment, setSelectedAssessment] = useState<any | null>(null);
  const [assessments, setAssessments] = useState<any[]>([]);

  // ── Fetch available events from MongoDB ───────────────────────────────────
  const fetchEvents = useCallback(async () => {
    try {
      const res = await fetch(`${API}/events`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setEvents(data.events || []);
      setError(null);
    } catch (e: any) {
      setError("Could not load events from MongoDB");
    } finally {
      setLoading(false);
    }
  }, []);

  // ── Fetch assessments from MongoDB ────────────────────────────────────────
  const fetchAssessments = useCallback(async () => {
    try {
      const res = await fetch(`${API}/assessments`);
      if (!res.ok) return;
      const data = await res.json();
      setAssessments(data.assessments || []);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    fetchEvents();
    fetchAssessments();
    const interval = setInterval(() => {
      fetchEvents();
      fetchAssessments();
    }, 30_000);
    return () => clearInterval(interval);
  }, [fetchEvents, fetchAssessments]);

  // ── Run a pipeline week via POST (no SSE — always uses the working API) ──
  const runEvent = useCallback(async (event: AvailableEvent, week?: number) => {
    const key = `${event.demo_tag ?? event.region_id}-${week ?? "live"}`;
    if (runningKey) return;

    setRunningKey(key);
    onPipelineStart();
    setError(null);

    try {
      const res = await fetch(`${API}/run`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          region_id:    event.region_id,
          trigger_type: "demo",
          demo_tag:     event.demo_tag ?? undefined,
          demo_week:    week ?? undefined,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const tier = data.threat_tier as ThreatTier;
      setResults((prev) => ({
        ...prev,
        [key]: {
          tier,
          score:      data.composite_score ?? 0,
          duration:   data.duration_seconds ?? 0,
          session_id: data.session_id,
          sitrep_id:  data.sitrep_id,
        },
      }));
      onTierChange(tier, data.composite_score ?? 0, data.sitrep_id);
      // Refresh assessments after pipeline run
      setTimeout(fetchAssessments, 1000);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRunningKey(null);
      onPipelineComplete();
    }
  }, [runningKey, onPipelineStart, onPipelineComplete, onTierChange, fetchAssessments]);

  if (loading) {
    return (
      <div className="bg-gray-900 rounded-xl border border-gray-700 p-4
                      text-center text-gray-500 text-sm animate-pulse">
        Loading events from MongoDB…
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div className="bg-gray-900 rounded-xl border border-gray-700 p-4
                      text-center text-gray-500 text-sm space-y-2">
        <div>No events in MongoDB yet.</div>
        <div className="text-xs text-gray-600">
          Run <code className="bg-gray-800 px-1 rounded">python3 scripts/load_sars_demo.py</code>{" "}
          to load demo data, or use the Ingest tab.
        </div>
        <button onClick={fetchEvents} className="text-xs text-blue-400 hover:text-blue-300 mt-1">
          ↻ Retry
        </button>
      </div>
    );
  }

  const grouped: Record<string, AvailableEvent[]> = {};
  for (const e of events) {
    const key = e.demo_tag ?? "live";
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(e);
  }

  const sarsRunCount = Object.keys(results).filter((k) => k.startsWith("sars_replay-")).length;

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-700 p-4 space-y-4">

      {/* Assessment detail overlay */}
      {selectedAssessment && (
        <AssessmentDetail
          assessment={selectedAssessment}
          onClose={() => setSelectedAssessment(null)}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-200">Event Monitor</h3>
        <div className="flex items-center gap-2">
          <button onClick={() => { fetchEvents(); fetchAssessments(); }}
            className="text-xs text-gray-500 hover:text-gray-300">
            ↻ Refresh
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="text-xs text-red-400 bg-red-400/10 border border-red-400/20
                        rounded-lg px-3 py-2 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-500 ml-2">×</button>
        </div>
      )}

      {/* Recent assessments from MongoDB */}
      {assessments.length > 0 && (
        <div className="border border-gray-800 rounded-xl overflow-hidden">
          <div className="bg-gray-800/50 px-3 py-2 border-b border-gray-800">
            <div className="text-sm font-medium text-gray-200">Recent Assessments</div>
          </div>
          <div className="divide-y divide-gray-800 max-h-48 overflow-y-auto">
            {assessments.slice(0, 10).map((a: any, i: number) => {
              const ac = TIER_COLORS[a.threat_tier] || "#6b7280";
              return (
                <div key={i}
                  className="flex items-center gap-3 px-3 py-2 hover:bg-gray-800/50 cursor-pointer"
                  onClick={() => setSelectedAssessment(a)}
                >
                  <div className="w-2 h-2 rounded-full" style={{ backgroundColor: ac }} />
                  <span className="text-xs font-bold" style={{ color: ac }}>
                    {a.threat_tier}
                  </span>
                  <span className="text-xs text-gray-500">
                    score {a.composite_score ?? "?"}
                  </span>
                  <span className="text-[10px] text-gray-700 ml-auto truncate">
                    {a.escalation_rationale?.slice(0, 60) || "—"}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Event groups */}
      {Object.entries(grouped).map(([tag, tagEvents]) => {
        const meta    = EVENT_LABELS[tag] ?? { name: tag.replace(/_/g, " "), description: "" };
        const isSeries = (tagEvents[0]?.available_weeks?.length ?? 0) > 0;
        const isLive   = tag === "live";

        return (
          <div key={tag} className="border border-gray-800 rounded-xl overflow-hidden">
            <div className="bg-gray-800/50 px-3 py-2.5 border-b border-gray-800
                            flex items-center justify-between">
              <div>
                <div className="text-sm font-medium text-gray-200">{meta.name}</div>
                <div className="text-xs text-gray-500 mt-0.5">
                  {meta.description || tagEvents[0]?.region_id}
                  {isLive && <span className="ml-2 text-green-500/70">● live data</span>}
                </div>
              </div>
              <div className="text-xs text-gray-700 text-right">
                <div>{tagEvents[0]?.signal_count ?? 0} signals</div>
                <div>{(tagEvents[0]?.total_cases ?? 0).toLocaleString()} cases</div>
              </div>
            </div>

            <div className="p-3 space-y-2">
              {isSeries ? (
                tagEvents[0].available_weeks
                  .slice().sort((a, b) => a - b)
                  .map((week) => {
                    const key      = `${tag}-${week}`;
                    const result   = results[key];
                    const isRunning = runningKey === key;
                    const color     = result ? TIER_COLORS[result.tier] : undefined;

                    return (
                      <div key={week}
                        className={`flex items-center gap-3 rounded-lg px-3 py-2 transition-all duration-200 ${
                          isRunning ? "bg-blue-500/10 border border-blue-500/30"
                            : result ? "bg-gray-800/40 border border-gray-800"
                            : "border border-transparent"
                        }`}>

                        <div className="w-9 h-9 rounded-full border-2 flex items-center
                                        justify-center text-xs font-bold flex-shrink-0 transition-all duration-300"
                          style={{
                            borderColor: color ?? "#374151",
                            backgroundColor: color ? color + "22" : "transparent",
                            color: color ?? "#6b7280",
                          }}>
                          W{week}
                        </div>

                        <div className="flex-1 min-w-0">
                          {isRunning ? (
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 border-2 border-blue-400/30 border-t-blue-400 rounded-full animate-spin" />
                              <span className="text-xs text-blue-400">Running pipeline…</span>
                            </div>
                          ) : result ? (
                            <div className="space-y-0.5">
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-bold" style={{ color: TIER_COLORS[result.tier] }}>
                                  {result.tier}
                                </span>
                                <span className="text-xs text-gray-500">score {Math.round(result.score)}</span>
                                <span className="text-xs text-gray-700">{result.duration}s</span>
                                {/* Detail button — links to assessments */}
                                <button onClick={() => {
                                  const a = assessments.find((ad: any) =>
                                    ad.agent_session_id && ad.agent_session_id.includes(result.session_id)
                                  );
                                  if (a) setSelectedAssessment(a);
                                }}
                                  className="text-[10px] text-indigo-400 hover:text-indigo-300 ml-1">
                                  Details
                                </button>
                              </div>
                              {result.sitrep_id && (
                                <div className="text-[10px] text-indigo-400">SitRep generated ↗</div>
                              )}
                            </div>
                          ) : (
                            <span className="text-xs text-gray-600">Week {week} — not yet analysed</span>
                          )}
                        </div>

                        {!result && !isRunning && (
                          <button onClick={() => runEvent(tagEvents[0], week)}
                            disabled={!!runningKey}
                            className="text-xs px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500
                                       text-white flex-shrink-0 disabled:opacity-40 disabled:cursor-not-allowed">
                            Run →
                          </button>
                        )}

                        {result && (
                          <button onClick={() => { setResults((p) => { const n = {...p}; delete n[key]; return n; }); runEvent(tagEvents[0], week); }}
                            disabled={!!runningKey}
                            className="text-[10px] px-2 py-1 rounded-lg border border-gray-700
                                       text-gray-600 hover:text-gray-400 flex-shrink-0 disabled:opacity-40">
                            ↻
                          </button>
                        )}
                      </div>
                    );
                  })
              ) : (
                tagEvents.map((event) => {
                  const key       = `${event.region_id}-live`;
                  const result    = results[key];
                  const isRunning = runningKey === key;

                  return (
                    <div key={event.region_id}
                      className={`flex items-center justify-between rounded-lg px-3 py-2.5 transition-all ${
                        isRunning ? "bg-blue-500/10 border border-blue-500/30" : "border border-transparent"
                      }`}>
                      <div className="min-w-0 mr-3">
                        <div className="text-sm text-gray-300 font-medium">{event.region_id}</div>
                        <div className="text-xs text-gray-600 mt-0.5">
                          {event.signal_count} signals · {event.total_cases.toLocaleString()} cases
                        </div>
                        {result && (
                          <div className="text-xs font-bold mt-1" style={{ color: TIER_COLORS[result.tier] }}>
                            {result.tier} · score {Math.round(result.score)}
                          </div>
                        )}
                      </div>
                      <button onClick={() => runEvent(event)}
                        disabled={!!runningKey}
                        className="text-xs px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500
                                   text-white flex-shrink-0 disabled:opacity-40 disabled:cursor-not-allowed
                                   flex items-center gap-1.5">
                        {isRunning ? (
                          <><div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />Running…</>
                        ) : "Analyse"}
                      </button>
                    </div>
                  );
                })
              )}
            </div>

            {tag === "sars_replay" && sarsRunCount >= 3 && (
              <div className="mx-3 mb-3 p-3 bg-green-500/8 border border-green-500/25 rounded-xl space-y-1">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-green-400 rounded-full" />
                  <p className="text-xs text-green-300 font-semibold">EWARS detected EMERGENCY on Jan 20, 2003</p>
                </div>
                <p className="text-xs text-green-500/60 pl-4">
                  WHO declared SARS a global threat on March 15, 2003 — <strong className="text-green-400/80">54 days later</strong>
                </p>
              </div>
            )}

            {tag === "sars_replay" && sarsRunCount > 0 && sarsRunCount < 3 && (
              <div className="mx-3 mb-3 px-3 py-2 text-xs text-gray-600">
                {3 - sarsRunCount} week{3 - sarsRunCount !== 1 ? "s" : ""} remaining
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}