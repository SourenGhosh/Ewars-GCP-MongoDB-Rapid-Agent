"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import Map, {
  Marker,
  Popup,
  NavigationControl,
  ScaleControl,
} from "react-map-gl/maplibre";         // ← maplibre import, not mapbox
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css"; // ← maplibre CSS, not mapbox
import { getActiveClusters } from "@/lib/api";
import type { ThreatTier } from "@/lib/types";

// ── Free tile style — CARTO Dark Matter, no API key ──────────────────────────
const MAP_STYLE =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

// Fallback: OpenFreeMap liberty (also free)
// const MAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";

// ── Tier colour coding ────────────────────────────────────────────────────────
const TIER_COLORS: Record<string, string> = {
  EMERGENCY: "#ef4444",
  ALERT:     "#f97316",
  WATCH:     "#eab308",
  LOW:       "#22c55e",
};

const TIER_GLOW: Record<string, boolean> = {
  EMERGENCY: true,
  ALERT:     true,
  WATCH:     false,
  LOW:       false,
};

interface ClusterMarker {
  cluster_id:        string;
  coordinates:       [number, number];   // [lon, lat]
  tier:              string;
  syndrome:          string;
  total_cases:       number;
  radius_km:         number;
  r_estimate:        number | null;
  cross_border_risk: boolean;
}

function deriveTier(cluster: any): string {
  if (cluster.r_estimate && cluster.r_estimate > 2.0) return "EMERGENCY";
  if (cluster.r_estimate && cluster.r_estimate > 1.2) return "ALERT";
  const total = cluster.case_counts?.total ?? cluster.total_cases ?? 0;
  if (total > 100) return "ALERT";
  if (total > 20)  return "WATCH";
  return "LOW";
}

export default function ThreatMap() {
  const [clusters, setClusters]   = useState<ClusterMarker[]>([]);
  const [selected, setSelected]   = useState<ClusterMarker | null>(null);
  const [loading, setLoading]     = useState(true);
  const [mapError, setMapError]   = useState<string | null>(null);

  const fetchClusters = useCallback(async () => {
    try {
      const { clusters: raw } = await getActiveClusters();
      const parsed: ClusterMarker[] = raw
        .filter((c: any) => c.centroid?.coordinates)
        .map((c: any) => ({
          cluster_id:        c.cluster_id,
          coordinates:       c.centroid.coordinates as [number, number],
          tier:              deriveTier(c),
          syndrome:          c.syndrome_profile?.primary ?? "Unknown",
          total_cases:       c.case_counts?.total ?? 0,
          radius_km:         c.radius_km ?? 25,
          r_estimate:        c.r_estimate ?? null,
          cross_border_risk: c.cross_border_risk ?? false,
        }));
      setClusters(parsed);
    } catch (e) {
      console.error("Failed to fetch clusters:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchClusters();
    const interval = setInterval(fetchClusters, 30_000);
    return () => clearInterval(interval);
  }, [fetchClusters]);

  // Marker size scales with case count
  const markerSize = (cases: number) =>
    Math.max(18, Math.min(52, 18 + Math.log10(cases + 1) * 14));

  return (
    <div className="relative w-full h-full rounded-xl overflow-hidden border border-gray-700">

      {/* Pulse animation for EMERGENCY / ALERT markers */}
      <style>{`
        @keyframes ewars-pulse {
          0%   { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
          70%  { box-shadow: 0 0 0 16px rgba(239, 68, 68, 0); }
          100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
        }
        .ewars-pulse { animation: ewars-pulse 1.8s ease-out infinite; }

        /* Override MapLibre attribution for dark theme */
        .maplibregl-ctrl-attrib {
          background: rgba(17,24,39,0.8) !important;
          color: #6b7280 !important;
          font-size: 10px !important;
        }
        .maplibregl-ctrl-attrib a { color: #4b5563 !important; }
      `}</style>

      {/* Map — no token prop needed for MapLibre */}
      <Map
        initialViewState={{
          longitude: 105.0,
          latitude:  15.0,
          zoom:      3.5,
        }}
        style={{ width: "100%", height: "100%" }}
        mapStyle={MAP_STYLE}
        mapLib={maplibregl}                 // ← tells react-map-gl to use maplibre
        onError={(e) => setMapError(String(e))}
      >
        <NavigationControl position="top-right" />
        <ScaleControl position="bottom-right" />

        {/* Cluster markers */}
        {clusters.map((cluster) => {
          const color = TIER_COLORS[cluster.tier] ?? TIER_COLORS.LOW;
          const size  = markerSize(cluster.total_cases);
          const glow  = TIER_GLOW[cluster.tier];

          return (
            <Marker
              key={cluster.cluster_id}
              longitude={cluster.coordinates[0]}
              latitude={cluster.coordinates[1]}
              anchor="center"
              onClick={(e) => {
                e.originalEvent.stopPropagation();
                setSelected(cluster);
              }}
            >
              <div
                title={`${cluster.tier} — ${cluster.syndrome} — ${cluster.total_cases} cases`}
                className={glow ? "ewars-pulse" : ""}
                style={{
                  width:           `${size}px`,
                  height:          `${size}px`,
                  borderRadius:    "50%",
                  backgroundColor: color + "cc",
                  border:          `3px solid ${color}`,
                  cursor:          "pointer",
                  transition:      "transform 0.15s ease",
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLDivElement).style.transform =
                    "scale(1.2)";
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLDivElement).style.transform =
                    "scale(1)";
                }}
              />
            </Marker>
          );
        })}

        {/* Detail popup */}
        {selected && (
          <Popup
            longitude={selected.coordinates[0]}
            latitude={selected.coordinates[1]}
            anchor="bottom"
            offset={[0, -10] as [number, number]}
            onClose={() => setSelected(null)}
            closeButton={true}
            closeOnClick={false}
            style={{ zIndex: 10 }}
          >
            <div
              style={{
                background:   "rgb(17 24 39)",
                border:       "1px solid rgb(55 65 81)",
                borderRadius: "10px",
                padding:      "12px 14px",
                minWidth:     "220px",
                color:        "white",
              }}
            >
              {/* Tier badge */}
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "10px" }}>
                <span
                  style={{
                    fontSize:        "12px",
                    fontWeight:      700,
                    padding:         "2px 10px",
                    borderRadius:    "20px",
                    backgroundColor: (TIER_COLORS[selected.tier] ?? "#6b7280") + "33",
                    color:           TIER_COLORS[selected.tier] ?? "#9ca3af",
                    border:          `1px solid ${(TIER_COLORS[selected.tier] ?? "#6b7280")}55`,
                  }}
                >
                  {selected.tier}
                </span>
                <span style={{ fontSize: "11px", color: "#6b7280" }}>
                  {selected.syndrome}
                </span>
              </div>

              {/* Stats */}
              <div style={{ fontSize: "13px", color: "#d1d5db", display: "grid", gap: "5px" }}>
                <div>
                  <span style={{ color: "#6b7280" }}>Cases: </span>
                  {selected.total_cases.toLocaleString()}
                </div>
                <div>
                  <span style={{ color: "#6b7280" }}>Radius: </span>
                  {selected.radius_km} km
                </div>
                {selected.r_estimate !== null && (
                  <div>
                    <span style={{ color: "#6b7280" }}>R estimate: </span>
                    <span
                      style={{
                        color: selected.r_estimate > 2
                          ? "#ef4444"
                          : selected.r_estimate > 1.2
                          ? "#f97316"
                          : "#22c55e",
                        fontWeight: 600,
                      }}
                    >
                      {selected.r_estimate.toFixed(2)}
                    </span>
                  </div>
                )}
                {selected.cross_border_risk && (
                  <div style={{ color: "#f97316", fontWeight: 600 }}>
                    ⚠ Cross-border risk
                  </div>
                )}
              </div>

              <div
                style={{ fontSize: "10px", color: "#374151", marginTop: "8px", wordBreak: "break-all" }}
              >
                {selected.cluster_id.slice(0, 16)}…
              </div>
            </div>
          </Popup>
        )}
      </Map>

      {/* Loading overlay */}
      {loading && (
        <div
          style={{
            position:        "absolute",
            inset:           0,
            background:      "rgba(3,7,18,0.8)",
            display:         "flex",
            alignItems:      "center",
            justifyContent:  "center",
            fontSize:        "13px",
            color:           "#9ca3af",
          }}
        >
          Loading surveillance data…
        </div>
      )}

      {/* Tile load error fallback */}
      {mapError && (
        <div
          style={{
            position:    "absolute",
            top:         8,
            left:        "50%",
            transform:   "translateX(-50%)",
            background:  "rgba(239,68,68,0.2)",
            border:      "1px solid #ef4444",
            borderRadius: "8px",
            padding:     "4px 12px",
            fontSize:    "11px",
            color:       "#fca5a5",
          }}
        >
          Map tiles unavailable — check internet connection
        </div>
      )}

      {/* Legend */}
      <div
        style={{
          position:     "absolute",
          top:          12,
          left:         12,
          background:   "rgba(17,24,39,0.92)",
          border:       "1px solid rgb(55,65,81)",
          borderRadius: "10px",
          padding:      "10px 14px",
          fontSize:     "11px",
        }}
      >
        <div style={{ color: "#9ca3af", fontWeight: 600, marginBottom: "8px" }}>
          Threat Tier
        </div>
        {Object.entries(TIER_COLORS).map(([tier, color]) => (
          <div
            key={tier}
            style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "5px" }}
          >
            <div
              style={{
                width:        "10px",
                height:       "10px",
                borderRadius: "50%",
                backgroundColor: color,
              }}
            />
            <span style={{ color: "#e5e7eb" }}>{tier}</span>
          </div>
        ))}
        <div
          style={{
            borderTop:  "1px solid rgb(55,65,81)",
            marginTop:  "8px",
            paddingTop: "6px",
            color:      "#6b7280",
          }}
        >
          {clusters.length} active cluster{clusters.length !== 1 ? "s" : ""}
        </div>
      </div>
    </div>
  );
}