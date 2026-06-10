// src/components/ThreatTimeline.tsx
"use client";

import { useEffect, useState, useCallback } from "react";
import Map, { Marker, Popup, NavigationControl } from "react-map-gl/maplibre";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { ThreatTier } from "@/lib/types";

const MAP_STYLE =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080/ewars";

const TIER_COLOR: Record<string, string> = {
  EMERGENCY: "#ef4444",
  ALERT:     "#f97316",
  WATCH:     "#eab308",
};

const TIER_GLOW: Record<string, boolean> = {
  EMERGENCY: true, ALERT: true, WATCH: false,
};

interface Assessment {
  assessment_id: string;
  cluster_id: string;
  threat_tier: string;
  composite_score: number;
  assessed_at: string;
  region_id: string;
  escalation_rationale: string;
  recommended_actions: string[];
  has_sitrep: boolean;
  sitrep_id: string | null;
  sitrep_summary: string | null;
  sitrep_status: string | null;
  coordinates: [number, number] | null;
  cluster_radius_km: number | null;
  total_cases: number;
  r_estimate: number | null;
  syndrome_primary: string | null;
  duration_seconds: number | null;
  trigger_type: string | null;
}

interface ThreatTimelineProps {
  onSitRepSelect?: (sitrepId: string) => void;
}

export default function ThreatTimeline({ onSitRepSelect }: ThreatTimelineProps) {
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [selected, setSelected]       = useState<Assessment | null>(null);
  const [loading, setLoading]         = useState(true);
  const [filterTier, setFilterTier]   = useState<string>("ALL");
  const [tab, setTab]                 = useState<"map" | "list">("map");

  const fetchTimeline = useCallback(async () => {
    try {
      const res = await fetch(`${API}/timeline`);
      const data = await res.json();
      setAssessments(data.assessments || []);
    } catch (e) {
      console.error("Timeline fetch failed:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTimeline();
    const interval = setInterval(fetchTimeline, 30_000);
    return () => clearInterval(interval);
  }, [fetchTimeline]);

  const filtered = assessments.filter(
    (a) => filterTier === "ALL" || a.threat_tier === filterTier
  );

  const withCoords = filtered.filter((a) => a.coordinates);

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString("en-GB", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });

  return (
    <div className="flex flex-col h-full">
      {/* Header + controls */}
      <div className="flex items-center justify-between px-4 pt-3 pb-2 gap-3">
        <div className="flex gap-1">
          {(["map", "list"] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`text-xs px-3 py-1.5 rounded-lg font-medium ${
                tab === t
                  ? "bg-gray-700 text-white"
                  : "text-gray-500 hover:text-gray-300"
              }`}>
              {t === "map" ? "Map" : "List"}
            </button>
          ))}
        </div>

        {/* Tier filter */}
        <div className="flex gap-1">
          {["ALL", "EMERGENCY", "ALERT", "WATCH"].map((tier) => (
            <button key={tier} onClick={() => setFilterTier(tier)}
              className={`text-xs px-2.5 py-1 rounded-lg transition-all ${
                filterTier === tier
                  ? "font-bold opacity-100"
                  : "opacity-50 hover:opacity-75"
              }`}
              style={{
                backgroundColor: tier === "ALL"
                  ? filterTier === "ALL" ? "rgb(55 65 81)" : "transparent"
                  : (TIER_COLOR[tier] ?? "#6b7280") + "22",
                color: tier === "ALL" ? "white" : TIER_COLOR[tier] ?? "#9ca3af",
                border: `1px solid ${tier === "ALL" ? "rgb(75 85 99)" : (TIER_COLOR[tier] ?? "#6b7280") + "44"}`,
              }}>
              {tier}
            </button>
          ))}
        </div>

        <div className="text-xs text-gray-600 flex-shrink-0">
          {filtered.length} event{filtered.length !== 1 ? "s" : ""}
        </div>
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center text-gray-600 text-sm animate-pulse">
          Loading timeline from MongoDB…
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-gray-600 text-sm text-center px-4">
          No events yet.{" "}
          <span className="text-gray-700 ml-1">
            Run the pipeline to generate threat assessments.
          </span>
        </div>
      ) : tab === "map" ? (
        /* ── MAP VIEW ── */
        <div className="flex-1 relative">
          <style>{`
            @keyframes ewars-pulse {
              0%   { box-shadow: 0 0 0 0 rgba(239,68,68,.7); }
              70%  { box-shadow: 0 0 0 14px rgba(239,68,68,0); }
              100% { box-shadow: 0 0 0 0 rgba(239,68,68,0); }
            }
            .ewars-pulse { animation: ewars-pulse 1.8s ease-out infinite; }
            .maplibregl-ctrl-attrib { font-size:9px !important; }
          `}</style>

          <Map
            initialViewState={{ longitude: 90, latitude: 15, zoom: 2.5 }}
            style={{ width: "100%", height: "100%" }}
            mapStyle={MAP_STYLE}
            mapLib={maplibregl}
          >
            <NavigationControl position="top-right" />

            {withCoords.map((a) => {
              const color = TIER_COLOR[a.threat_tier] ?? "#6b7280";
              const size = Math.max(18, Math.min(44,
                18 + (a.composite_score / 100) * 26));
              return (
                <Marker key={a.assessment_id}
                  longitude={a.coordinates![0]}
                  latitude={a.coordinates![1]}
                  anchor="center"
                  onClick={(e) => {
                    e.originalEvent.stopPropagation();
                    setSelected(a);
                  }}>
                  <div
                    className={TIER_GLOW[a.threat_tier] ? "ewars-pulse" : ""}
                    style={{
                      width: `${size}px`, height: `${size}px`,
                      borderRadius: "50%",
                      backgroundColor: color + "bb",
                      border: `2.5px solid ${color}`,
                      cursor: "pointer",
                      transition: "transform .15s ease",
                    }}
                    onMouseEnter={(e) =>
                      ((e.currentTarget as HTMLDivElement).style.transform = "scale(1.25)")}
                    onMouseLeave={(e) =>
                      ((e.currentTarget as HTMLDivElement).style.transform = "scale(1)")}
                  />
                </Marker>
              );
            })}

            {selected && selected.coordinates && (
              <Popup
                longitude={selected.coordinates[0]}
                latitude={selected.coordinates[1]}
                anchor="bottom"
                offset={[0, -12] as [number, number]}
                onClose={() => setSelected(null)}
                closeOnClick={false}>
                <AssessmentCard
                  a={selected}
                  onSitRepClick={onSitRepSelect}
                  onClose={() => setSelected(null)}
                />
              </Popup>
            )}
          </Map>

          {/* Events without coordinates — small badge */}
          {filtered.filter(a => !a.coordinates).length > 0 && (
            <div className="absolute bottom-3 left-3 bg-gray-900/90 border border-gray-700
                            rounded-lg px-3 py-2 text-xs text-gray-500">
              {filtered.filter(a => !a.coordinates).length} event
              {filtered.filter(a => !a.coordinates).length !== 1 ? "s" : ""} without location
            </div>
          )}
        </div>
      ) : (
        /* ── LIST VIEW ── */
        <div className="flex-1 overflow-y-auto px-4 pb-4 space-y-2">
          {filtered.map((a) => (
            <button key={a.assessment_id}
              onClick={() => setSelected(selected?.assessment_id === a.assessment_id ? null : a)}
              className="w-full text-left">
              <div className={`rounded-xl border p-3 transition-all ${
                selected?.assessment_id === a.assessment_id
                  ? "border-blue-500/40 bg-blue-500/5"
                  : "border-gray-800 hover:border-gray-700"
              }`}>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-bold"
                    style={{ color: TIER_COLOR[a.threat_tier] }}>
                    {a.threat_tier}
                  </span>
                  <span className="text-xs text-gray-600">{formatDate(a.assessed_at)}</span>
                </div>
                <div className="text-xs text-gray-400">{a.region_id}</div>
                {a.syndrome_primary && (
                  <div className="text-xs text-gray-600 mt-0.5">
                    {a.syndrome_primary} · {a.total_cases.toLocaleString()} cases
                    {a.r_estimate && ` · R=${a.r_estimate.toFixed(2)}`}
                  </div>
                )}
              </div>

              {/* Expanded detail */}
              {selected?.assessment_id === a.assessment_id && (
                <div className="mt-1">
                  <AssessmentCard a={a} onSitRepClick={onSitRepSelect} />
                </div>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}


function AssessmentCard({
  a,
  onSitRepClick,
  onClose,
}: {
  a: Assessment;
  onSitRepClick?: (id: string) => void;
  onClose?: () => void;
}) {
  const color = TIER_COLOR[a.threat_tier] ?? "#6b7280";
  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString("en-GB", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });

  return (
    <div style={{
      background: "rgb(17 24 39)",
      border: "1px solid rgb(55 65 81)",
      borderRadius: "12px", padding: "14px",
      minWidth: "280px", maxWidth: "340px",
      color: "white",
    }}>
      {/* Tier + close */}
      <div style={{ display: "flex", justifyContent: "space-between",
                    alignItems: "center", marginBottom: "10px" }}>
        <span style={{
          fontSize: "12px", fontWeight: 700, padding: "2px 10px",
          borderRadius: "20px", color,
          backgroundColor: color + "22",
          border: `1px solid ${color}44`,
        }}>
          {a.threat_tier}
        </span>
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <span style={{ fontSize: "10px", color: "#6b7280" }}>
            {formatDate(a.assessed_at)}
          </span>
          {onClose && (
            <button onClick={onClose}
              style={{ color: "#6b7280", background: "none",
                       border: "none", cursor: "pointer", fontSize: "16px" }}>
              ×
            </button>
          )}
        </div>
      </div>

      {/* Stats grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr",
                    gap: "6px", fontSize: "12px", color: "#d1d5db",
                    marginBottom: "10px" }}>
        <div><span style={{ color: "#6b7280" }}>Region: </span>{a.region_id}</div>
        <div>
          <span style={{ color: "#6b7280" }}>Score: </span>
          <span style={{ color, fontWeight: 600 }}>
            {Math.round(a.composite_score ?? 0)}
          </span>
        </div>
        {a.syndrome_primary && (
          <div><span style={{ color: "#6b7280" }}>Syndrome: </span>{a.syndrome_primary}</div>
        )}
        <div><span style={{ color: "#6b7280" }}>Cases: </span>{(a.total_cases ?? 0).toLocaleString()}</div>
        {a.r_estimate != null && (
          <div>
            <span style={{ color: "#6b7280" }}>R: </span>
            <span style={{
              color: a.r_estimate > 2 ? "#ef4444" :
                     a.r_estimate > 1.2 ? "#f97316" : "#22c55e",
              fontWeight: 600,
            }}>
              {a.r_estimate.toFixed(2)}
            </span>
          </div>
        )}
        {a.duration_seconds != null && (
          <div>
            <span style={{ color: "#6b7280" }}>Pipeline: </span>
            {a.duration_seconds}s
          </div>
        )}
      </div>

      {/* Rationale */}
      {a.escalation_rationale && (
        <div style={{ fontSize: "11px", color: "#9ca3af",
                      borderTop: "1px solid #1f2937",
                      paddingTop: "8px", marginBottom: "10px",
                      lineHeight: "1.5" }}>
          {a.escalation_rationale.slice(0, 200)}
          {a.escalation_rationale.length > 200 ? "…" : ""}
        </div>
      )}

      {/* SitRep button */}
      {a.has_sitrep && a.sitrep_id && (
        <div style={{ borderTop: "1px solid #1f2937", paddingTop: "8px" }}>
          {a.sitrep_summary && (
            <p style={{ fontSize: "11px", color: "#9ca3af",
                        marginBottom: "8px", lineHeight: "1.5" }}>
              {a.sitrep_summary.slice(0, 150)}…
            </p>
          )}
          <button
            onClick={() => onSitRepClick?.(a.sitrep_id!)}
            style={{
              width: "100%", padding: "6px",
              background: color + "22",
              border: `1px solid ${color}44`,
              borderRadius: "8px", color, fontSize: "12px",
              fontWeight: 600, cursor: "pointer",
            }}>
            View Full SitRep ({a.sitrep_status})
          </button>
        </div>
      )}

      {!a.has_sitrep && a.threat_tier === "WATCH" && (
        <div style={{ fontSize: "11px", color: "#6b7280",
                      borderTop: "1px solid #1f2937", paddingTop: "8px" }}>
          WATCH tier — no SitRep generated
        </div>
      )}
    </div>
  );
}