// src/components/EpidemicTimeline.tsx
"use client";

import { useEffect, useState, useCallback } from "react";
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ReferenceArea, Legend,
  ResponsiveContainer, Dot,
} from "recharts";
import type { ThreatTier } from "@/lib/types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080/ewars";

// ── Colour constants ──────────────────────────────────────────────────────────
const TIER_COLOR: Record<string, string> = {
  WATCH:     "#eab308",
  ALERT:     "#f97316",
  EMERGENCY: "#ef4444",
  NORMAL:    "#374151",
};
const TIER_BG: Record<string, string> = {
  WATCH:     "#eab30808",
  ALERT:     "#f9731608",
  EMERGENCY: "#ef444410",
};
const MILESTONE_COLOR: Record<string, string> = {
  official_report: "#6366f1",
  who_alert:       "#f97316",
  pheic:           "#ef4444",
  contained:       "#22c55e",
};

// ── Types ─────────────────────────────────────────────────────────────────────
interface WeekData {
  week: number;
  date: string;
  actual_cases: number;
  syndromes: string[];
  source_types: string[];
  assessment?: {
    assessment_id: string;
    threat_tier: string;
    composite_score: number;
    syndromic_score: number;
    geo_score: number;
    r_estimate: number | null;
  };
  sitrep?: {
    sitrep_id: string;
    executive_summary: string;
    recommended_actions: string[];
    status: string;
  };
  has_run: boolean;
}

interface Prediction {
  model_used: string;
  r_estimate: number;
  doubling_time_days: number | null;
  peak_week: number | null;
  peak_cases: number | null;
  weeks_forecast: Array<{
    week_number: number;
    predicted_cases: number;
    lower_bound: number;
    upper_bound: number;
    predicted_tier: string;
  }>;
  without_intervention: Array<{
    week_number: number;
    predicted_cases: number;
    lower_bound: number;
    upper_bound: number;
  }>;
  narrative: string;
  confidence_level: string;
  assumptions: string[];
}

interface TimelineData {
  region_id: string;
  demo_tag: string | null;
  weeks: WeekData[];
  total_cases: number;
  prediction: { prediction: Prediction } | null;
  who_milestones: Array<{
    week_offset: number;
    date: string;
    label: string;
    type: string;
    color: string;
  }>;
}

interface AvailableEvent {
  demo_tag: string | null;
  region_id: string;
  available_weeks: number[];
  total_cases: number;
  signal_count: number;
  first_signal_date: string;
}

// ── Custom tooltip ────────────────────────────────────────────────────────────
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const weekData: WeekData = payload[0]?.payload?._weekData;
  const tier = weekData?.assessment?.threat_tier;
  const color = tier ? TIER_COLOR[tier] : "#9ca3af";

  return (
    <div style={{
      background: "rgb(17 24 39)", border: "1px solid rgb(55 65 81)",
      borderRadius: "10px", padding: "12px 14px", minWidth: "200px",
    }}>
      <div style={{ fontSize: "12px", color: "#9ca3af", marginBottom: "8px" }}>
        Week {label}
        {weekData?.date && (
          <span style={{ marginLeft: "8px" }}>
            {new Date(weekData.date).toLocaleDateString("en-GB",
              { day: "2-digit", month: "short", year: "numeric" })}
          </span>
        )}
      </div>

      {payload.map((p: any) => p.value != null && (
        <div key={p.name} style={{
          display: "flex", justifyContent: "space-between",
          gap: "16px", fontSize: "12px", marginBottom: "4px",
        }}>
          <span style={{ color: p.color ?? "#9ca3af" }}>{p.name}</span>
          <span style={{ color: "white", fontWeight: 600 }}>
            {typeof p.value === "number" ? Math.round(p.value).toLocaleString() : p.value}
          </span>
        </div>
      ))}

      {tier && (
        <div style={{
          marginTop: "8px", paddingTop: "8px",
          borderTop: "1px solid #1f2937", fontSize: "11px",
          fontWeight: 700, color,
        }}>
          {tier} {weekData?.assessment?.composite_score != null
            ? `· score ${Math.round(weekData.assessment.composite_score)}`
            : ""}
        </div>
      )}

      {weekData?.sitrep && (
        <div style={{ marginTop: "6px", fontSize: "10px", color: "#6366f1" }}>
          SitRep available ↗
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
interface EpidemicTimelineProps {
  onRunWeek: (regionId: string, demoTag: string | null, demoWeek: number) => Promise<void>;
  onSitRepSelect: (sitrepId: string) => void;
  runningWeek: number | null;
}

export default function EpidemicTimeline({
  onRunWeek,
  onSitRepSelect,
  runningWeek,
}: EpidemicTimelineProps) {
  const [events, setEvents]           = useState<AvailableEvent[]>([]);
  const [selectedEvent, setSelected]  = useState<AvailableEvent | null>(null);
  const [timeline, setTimeline]       = useState<TimelineData | null>(null);
  const [prediction, setPrediction]   = useState<Prediction | null>(null);
  const [predicting, setPredicting]   = useState(false);
  const [loading, setLoading]         = useState(false);
  const [selectedWeek, setSelectedWk] = useState<WeekData | null>(null);
  const [showPrediction, setShowPred] = useState(false);
  const [showNoIntervention, setShowNoInt] = useState(false);

  // ── Fetch event list ────────────────────────────────────────────────────────
  useEffect(() => {
    fetch(`${API}/events`)
      .then((r) => r.json())
      .then((d) => {
        setEvents(d.events || []);
        if (d.events?.length > 0 && !selectedEvent) {
          setSelected(d.events[0]);
        }
      })
      .catch(console.error);
  }, []);

  // ── Fetch timeline for selected event ──────────────────────────────────────
  const fetchTimeline = useCallback(async (event: AvailableEvent) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ region_id: event.region_id });
      if (event.demo_tag) params.set("demo_tag", event.demo_tag);
      const res = await fetch(`${API}/timeline/full?${params}`);
      const data: TimelineData = await res.json();
      setTimeline(data);
      if (data.prediction) {
        setPrediction(data.prediction.prediction);
        setShowPred(true);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedEvent) fetchTimeline(selectedEvent);
  }, [selectedEvent, fetchTimeline]);

  // ── Run prediction ──────────────────────────────────────────────────────────
  const runPrediction = async () => {
    if (!timeline || !selectedEvent) return;
    setPredicting(true);
    try {
      const weeksObserved = timeline.weeks
        .filter((w) => w.actual_cases > 0)
        .map((w) => ({ week: w.week, cases: w.actual_cases }));

      const primarySyndrome = timeline.weeks
        .flatMap((w) => w.syndromes)[0] || "SARI";

      const res = await fetch(`${API}/timeline/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          region_id: selectedEvent.region_id,
          demo_tag: selectedEvent.demo_tag,
          weeks_observed: weeksObserved,
          syndrome: primarySyndrome,
          population: 10_000_000,
        }),
      });
      const pred: Prediction = await res.json();
      setPrediction(pred);
      setShowPred(true);
      setShowNoInt(false);
      // Refresh timeline to get stored prediction
      await fetchTimeline(selectedEvent);
    } catch (e) {
      console.error(e);
    } finally {
      setPredicting(false);
    }
  };

  // ── Handle week run ─────────────────────────────────────────────────────────
  const handleRunWeek = async (week: number) => {
    if (!selectedEvent) return;
    await onRunWeek(selectedEvent.region_id, selectedEvent.demo_tag, week);
    await fetchTimeline(selectedEvent);
  };

  // ── Build chart data ────────────────────────────────────────────────────────
  const chartData = (() => {
    if (!timeline) return [];

    const points: Record<number, any> = {};

    // Actual weeks
    for (const w of timeline.weeks) {
      points[w.week] = {
        week: w.week,
        actual: w.actual_cases || null,
        _weekData: w,
      };
    }

    // Prediction weeks
    if (showPrediction && prediction?.weeks_forecast) {
      for (const p of prediction.weeks_forecast) {
        if (!points[p.week_number]) {
          points[p.week_number] = { week: p.week_number };
        }
        points[p.week_number].predicted = p.predicted_cases;
        points[p.week_number].lower = p.lower_bound;
        points[p.week_number].upper = p.upper_bound;
        points[p.week_number].predicted_tier = p.predicted_tier;
      }
    }

    // Without-intervention curve
    if (showNoIntervention && prediction?.without_intervention) {
      for (const p of prediction.without_intervention) {
        if (!points[p.week_number]) {
          points[p.week_number] = { week: p.week_number };
        }
        points[p.week_number].no_intervention = p.predicted_cases;
      }
    }

    return Object.values(points).sort((a: any, b: any) => a.week - b.week);
  })();

  // Background bands for tier changes
  const tierBands = (() => {
    if (!timeline) return [];
    const bands: Array<{ x1: number; x2: number; tier: string }> = [];
    let currentTier = "NORMAL";
    let bandStart = 1;

    for (const w of timeline.weeks) {
      const tier = w.assessment?.threat_tier || "NORMAL";
      if (tier !== currentTier) {
        if (currentTier !== "NORMAL") {
          bands.push({ x1: bandStart, x2: w.week, tier: currentTier });
        }
        currentTier = tier;
        bandStart = w.week;
      }
    }
    if (currentTier !== "NORMAL" && timeline.weeks.length > 0) {
      bands.push({
        x1: bandStart,
        x2: timeline.weeks[timeline.weeks.length - 1].week + 1,
        tier: currentTier,
      });
    }
    return bands;
  })();

  const runWeeks = timeline?.weeks.filter(w => !w.has_run && w.actual_cases > 0) || [];
  const hasObservedData = timeline?.weeks.some(w => w.actual_cases > 0);
  const canPredict = hasObservedData && !predicting;

  return (
    <div className="flex flex-col h-full bg-gray-900 rounded-xl border border-gray-700 overflow-hidden">

      {/* ── Header ── */}
      <div className="px-4 pt-3 pb-2 border-b border-gray-800 flex-shrink-0">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-gray-200">Disease Timeline</h3>

          {/* Event selector */}
          <select
            value={selectedEvent ? `${selectedEvent.demo_tag ?? ""}__${selectedEvent.region_id}` : ""}
            onChange={(e) => {
              const [tag, region] = e.target.value.split("__");
              const ev = events.find(
                (ev) => (ev.demo_tag ?? "") === tag && ev.region_id === region
              );
              if (ev) { setSelected(ev); setPrediction(null); setShowPred(false); }
            }}
            className="text-xs bg-gray-800 text-gray-300 border border-gray-700
                       rounded-lg px-2 py-1.5 max-w-48">
            {events.map((ev) => (
              <option
                key={`${ev.demo_tag ?? ""}__${ev.region_id}`}
                value={`${ev.demo_tag ?? ""}__${ev.region_id}`}>
                {ev.demo_tag
                  ? `${ev.demo_tag.replace("_replay", "").replace("_", " ")} — ${ev.region_id}`
                  : `Live: ${ev.region_id}`
                }
              </option>
            ))}
          </select>
        </div>

        {/* Stats row */}
        {timeline && (
          <div className="flex gap-4 mt-2 text-xs text-gray-500">
            <span>{timeline.total_cases.toLocaleString()} total cases</span>
            <span>{timeline.total_weeks} weeks of data</span>
            {prediction && (
              <>
                <span className="text-purple-400">
                  R={prediction.r_estimate?.toFixed(2)}
                </span>
                <span className="text-purple-400">
                  Model: {prediction.model_used}
                </span>
              </>
            )}
          </div>
        )}
      </div>

      {/* ── Chart ── */}
      <div className="flex-1 min-h-0 px-2 py-3">
        {loading ? (
          <div className="h-full flex items-center justify-center text-gray-600 text-sm animate-pulse">
            Loading timeline…
          </div>
        ) : !timeline || chartData.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-gray-600 text-sm text-center px-6 gap-2">
            <div className="text-2xl">📊</div>
            <div>No signal data yet for this event.</div>
            <div className="text-xs text-gray-700">
              Run a pipeline week to generate data, or ingest signals first.
            </div>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 4, right: 12, left: 0, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis
                dataKey="week"
                tick={{ fill: "#6b7280", fontSize: 11 }}
                label={{ value: "Week", position: "insideBottomRight",
                         offset: -4, fill: "#4b5563", fontSize: 10 }}
              />
              <YAxis
                tick={{ fill: "#6b7280", fontSize: 11 }}
                width={50}
                tickFormatter={(v) => v >= 1000 ? `${(v/1000).toFixed(1)}k` : v}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend
                wrapperStyle={{ fontSize: "11px", paddingTop: "8px" }}
                formatter={(value) => (
                  <span style={{ color: "#9ca3af" }}>{value}</span>
                )}
              />

              {/* Tier background bands */}
              {tierBands.map((band, i) => (
                <ReferenceArea
                  key={i}
                  x1={band.x1} x2={band.x2}
                  fill={TIER_BG[band.tier] || "transparent"}
                  fillOpacity={1}
                />
              ))}

              {/* WHO milestone vertical lines */}
              {timeline.who_milestones.map((m, i) => (
                <ReferenceLine
                  key={i}
                  x={m.week_offset}
                  stroke={m.color}
                  strokeDasharray="4 2"
                  strokeWidth={1.5}
                  label={{
                    value: m.label,
                    position: "insideTopRight",
                    fill: m.color,
                    fontSize: 9,
                    angle: -90,
                    dy: -4,
                  }}
                />
              ))}

              {/* Prediction confidence band */}
              {showPrediction && prediction && (
                <Area
                  dataKey="upper"
                  fill="#a855f720"
                  stroke="none"
                  name="Confidence band"
                  legendType="none"
                  activeDot={false}
                />
              )}
              {showPrediction && prediction && (
                <Area
                  dataKey="lower"
                  fill="#a855f720"
                  stroke="none"
                  fillOpacity={0}
                  name="_lower"
                  legendType="none"
                  activeDot={false}
                />
              )}

              {/* Without-intervention counterfactual */}
              {showNoIntervention && (
                <Line
                  type="monotone"
                  dataKey="no_intervention"
                  stroke="#ef4444"
                  strokeWidth={1.5}
                  strokeDasharray="2 4"
                  dot={false}
                  name="Without intervention"
                />
              )}

              {/* Predicted line */}
              {showPrediction && (
                <Line
                  type="monotone"
                  dataKey="predicted"
                  stroke="#a855f7"
                  strokeWidth={2}
                  strokeDasharray="6 3"
                  dot={(props: any) => props.payload?.predicted != null
                    ? <Dot {...props} r={3} fill="#a855f7" />
                    : <g key={props.key} />
                  }
                  name="Predicted"
                />
              )}

              {/* Actual cases — solid, primary line */}
              <Line
                type="monotone"
                dataKey="actual"
                stroke="#60a5fa"
                strokeWidth={2.5}
                dot={(props: any) => {
                  if (props.payload?.actual == null) return <g key={props.key} />;
                  const tier = props.payload?._weekData?.assessment?.threat_tier;
                  const color = tier ? TIER_COLOR[tier] : "#60a5fa";
                  return (
                    <Dot
                      {...props}
                      r={5}
                      fill={color}
                      stroke="rgb(17 24 39)"
                      strokeWidth={2}
                      style={{ cursor: "pointer" }}
                      onClick={() => setSelectedWk(props.payload?._weekData)}
                    />
                  );
                }}
                activeDot={{
                  r: 7,
                  fill: "#60a5fa",
                  stroke: "white",
                  strokeWidth: 2,
                  onClick: (_: any, payload: any) => setSelectedWk(payload?.payload?._weekData),
                }}
                name="Actual cases"
              />
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* ── Controls ── */}
      <div className="px-4 pb-3 flex-shrink-0 border-t border-gray-800 pt-3 space-y-3">

        {/* Chart toggles */}
        {prediction && (
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => setShowPred((v) => !v)}
              className={`text-xs px-3 py-1.5 rounded-lg border transition-all ${
                showPrediction
                  ? "bg-purple-500/20 border-purple-500/40 text-purple-300"
                  : "bg-gray-800 border-gray-700 text-gray-500"
              }`}>
              {showPrediction ? "▼" : "▶"} Show prediction
            </button>
            <button
              onClick={() => setShowNoInt((v) => !v)}
              className={`text-xs px-3 py-1.5 rounded-lg border transition-all ${
                showNoIntervention
                  ? "bg-red-500/20 border-red-500/40 text-red-300"
                  : "bg-gray-800 border-gray-700 text-gray-500"
              }`}>
              {showNoIntervention ? "▼" : "▶"} Without intervention
            </button>
          </div>
        )}

        {/* Run pipeline buttons for unrun weeks */}
        {runWeeks.length > 0 && (
          <div className="flex gap-2 flex-wrap">
            {runWeeks.map((w) => (
              <button
                key={w.week}
                onClick={() => handleRunWeek(w.week)}
                disabled={runningWeek !== null}
                className="text-xs px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500
                           text-white disabled:opacity-40 flex items-center gap-1.5">
                {runningWeek === w.week ? (
                  <>
                    <div className="w-3 h-3 border-2 border-white/30 border-t-white
                                    rounded-full animate-spin" />
                    Running…
                  </>
                ) : (
                  `Run Week ${w.week} →`
                )}
              </button>
            ))}
          </div>
        )}

        {/* Predict button */}
        {canPredict && (
          <button
            onClick={runPrediction}
            disabled={predicting}
            className="w-full py-2 text-xs font-medium rounded-lg border transition-all
                       border-purple-500/40 bg-purple-500/10 hover:bg-purple-500/20
                       text-purple-300 disabled:opacity-40 flex items-center justify-center gap-2">
            {predicting ? (
              <>
                <div className="w-3 h-3 border-2 border-purple-400/30 border-t-purple-400
                                rounded-full animate-spin" />
                Fitting epidemic model…
              </>
            ) : (
              <>
                ◆ Predict trajectory
                <span className="text-purple-500">
                  ({prediction ? "update" : "SIR / exponential"})
                </span>
              </>
            )}
          </button>
        )}
      </div>

      {/* ── Selected week drawer ── */}
      {selectedWeek && (
        <WeekDrawer
          week={selectedWeek}
          prediction={prediction}
          onSitRepClick={onSitRepSelect}
          onClose={() => setSelectedWk(null)}
        />
      )}

      {/* ── Prediction narrative card ── */}
      {prediction && showPrediction && (
        <div className="mx-4 mb-3 p-3 bg-purple-500/5 border border-purple-500/20
                        rounded-xl flex-shrink-0">
          <div className="flex items-start justify-between gap-2 mb-2">
            <span className="text-xs font-medium text-purple-300">
              AI Forecast · {prediction.model_used} model
            </span>
            <span className={`text-xs px-2 py-0.5 rounded ${
              prediction.confidence_level === "HIGH"
                ? "bg-green-500/20 text-green-400"
                : prediction.confidence_level === "MEDIUM"
                ? "bg-yellow-500/20 text-yellow-400"
                : "bg-red-500/20 text-red-400"
            }`}>
              {prediction.confidence_level} confidence
            </span>
          </div>
          <p className="text-xs text-gray-400 leading-relaxed">
            {prediction.narrative}
          </p>
          {prediction.peak_week && (
            <div className="mt-2 text-xs text-purple-400">
              Predicted peak: Week {prediction.peak_week}
              {prediction.peak_cases && ` · ~${Math.round(prediction.peak_cases).toLocaleString()} cases`}
            </div>
          )}
        </div>
      )}
    </div>
  );
}


// ── Week detail drawer ─────────────────────────────────────────────────────────
function WeekDrawer({
  week,
  prediction,
  onSitRepClick,
  onClose,
}: {
  week: WeekData;
  prediction: Prediction | null;
  onSitRepClick: (id: string) => void;
  onClose: () => void;
}) {
  const tier = week.assessment?.threat_tier;
  const color = tier ? TIER_COLOR[tier] : "#6b7280";

  // Find prediction for this week if available
  const weekPred = prediction?.weeks_forecast?.find(
    (p) => p.week_number === week.week
  );

  return (
    <div style={{
      position: "absolute", bottom: 0, left: 0, right: 0,
      background: "rgb(3 7 18)", borderTop: "1px solid rgb(55 65 81)",
      borderRadius: "12px 12px 0 0", padding: "16px",
      zIndex: 20, maxHeight: "65%", overflowY: "auto",
    }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between",
                    alignItems: "center", marginBottom: "12px" }}>
        <div>
          <span style={{ fontSize: "13px", fontWeight: 600, color: "white" }}>
            Week {week.week}
          </span>
          {week.date && (
            <span style={{ fontSize: "11px", color: "#6b7280", marginLeft: "8px" }}>
              {new Date(week.date).toLocaleDateString("en-GB",
                { day: "2-digit", month: "short", year: "numeric" })}
            </span>
          )}
        </div>
        <button onClick={onClose}
          style={{ color: "#6b7280", background: "none", border: "none",
                   cursor: "pointer", fontSize: "20px" }}>×</button>
      </div>

      {/* Stats */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr",
                    gap: "8px", marginBottom: "12px" }}>
        {[
          { label: "Actual cases", value: week.actual_cases.toLocaleString(), color: "#60a5fa" },
          { label: "Tier", value: tier || "Not run", color },
          { label: "Score", value: week.assessment?.composite_score != null
              ? Math.round(week.assessment.composite_score).toString() : "—",
            color: "#9ca3af" },
          { label: "Syndromes", value: week.syndromes.join(", ") || "—", color: "#9ca3af" },
          { label: "Sources", value: week.source_types.length.toString(), color: "#9ca3af" },
          { label: "R estimate", value: week.assessment?.r_estimate != null
              ? week.assessment.r_estimate.toFixed(2) : "—",
            color: "#9ca3af" },
        ].map((stat) => (
          <div key={stat.label} style={{
            background: "rgb(17 24 39)", borderRadius: "8px",
            padding: "8px 10px",
          }}>
            <div style={{ fontSize: "10px", color: "#6b7280", marginBottom: "2px" }}>
              {stat.label}
            </div>
            <div style={{ fontSize: "13px", fontWeight: 600, color: stat.color }}>
              {stat.value}
            </div>
          </div>
        ))}
      </div>

      {/* Prediction comparison */}
      {weekPred && (
        <div style={{
          background: "rgba(168,85,247,.08)", border: "1px solid rgba(168,85,247,.2)",
          borderRadius: "8px", padding: "10px 12px", marginBottom: "12px",
        }}>
          <div style={{ fontSize: "11px", color: "#a855f7",
                        fontWeight: 600, marginBottom: "6px" }}>
            AI Prediction for this week
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr",
                        gap: "8px", fontSize: "11px", color: "#d1d5db" }}>
            <div>
              <span style={{ color: "#6b7280" }}>Predicted: </span>
              {Math.round(weekPred.predicted_cases).toLocaleString()}
            </div>
            <div>
              <span style={{ color: "#6b7280" }}>Range: </span>
              {Math.round(weekPred.lower_bound).toLocaleString()}–
              {Math.round(weekPred.upper_bound).toLocaleString()}
            </div>
            <div>
              <span style={{ color: "#6b7280" }}>Pred. tier: </span>
              <span style={{ color: TIER_COLOR[weekPred.predicted_tier] }}>
                {weekPred.predicted_tier}
              </span>
            </div>
          </div>
          {week.actual_cases > 0 && (
            <div style={{ marginTop: "6px", fontSize: "10px", color: "#9ca3af" }}>
              Prediction accuracy: {Math.round(
                100 - Math.abs(weekPred.predicted_cases - week.actual_cases)
                  / Math.max(week.actual_cases, 1) * 100
              )}%
            </div>
          )}
        </div>
      )}

      {/* SitRep */}
      {week.sitrep && (
        <div style={{ borderTop: "1px solid #1f2937", paddingTop: "12px" }}>
          <div style={{ fontSize: "11px", color: "#6b7280", marginBottom: "6px" }}>
            Situation Report
          </div>
          <p style={{ fontSize: "12px", color: "#9ca3af", lineHeight: "1.5",
                      marginBottom: "8px" }}>
            {week.sitrep.executive_summary}
          </p>
          <button
            onClick={() => onSitRepClick(week.sitrep!.sitrep_id)}
            style={{
              width: "100%", padding: "8px",
              background: color + "22",
              border: `1px solid ${color}44`,
              borderRadius: "8px", color,
              fontSize: "12px", fontWeight: 600, cursor: "pointer",
            }}>
            View Full SitRep →
          </button>
        </div>
      )}

      {!week.has_run && (
        <div style={{ fontSize: "11px", color: "#6b7280",
                      borderTop: "1px solid #1f2937", paddingTop: "10px" }}>
          This week has not been analysed yet. Click "Run Week {week.week} →" to analyse.
        </div>
      )}
    </div>
  );
}